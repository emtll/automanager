import concurrent.futures
import os
import time
import subprocess
import requests
import json
import configparser
import sqlite3
import logging

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.abspath(os.path.join(script_dir, '..', 'logs'))

if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

logging.basicConfig(
    filename=os.path.join(logs_dir, "swap_out.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logging.info("Logging configured and ready to use.")

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'automator.conf'))
config = configparser.ConfigParser()
config.read(config_file_path)

def expand_path(path):
    if not os.path.isabs(path):
        return os.path.join(os.path.expanduser("~"), path)
    return os.path.expanduser(path)

LNDG_DB_PATH = expand_path(config['Paths']['lndg_db_path'])
DB_PATH = expand_path(config['Paths']['db_path'])
BOS_PATH = expand_path(config['Paths']['bos_path'])
EXCLUSION_FILE_PATH = expand_path(config['Paths']['excluded_peers_path'])
STRIKE_API_KEY = config['Swap_out']['strike_api_key']
OUTBOUND_THRESHOLD = float(config['Swap_out']['outbound_threshold'])
ONCHAIN_TARGET = int(config['Swap_out']['onchain_target'])
WITHDRAW_AMOUNT_SATOSHIS = int(config['Swap_out']['withdraw_amount_satoshis'])
CHECK_INTERVAL_SECONDS = int(config['Swap_out']['check_interval_seconds'])
MAX_RETRIES = int(config['Swap_out']['max_retries'])
LN_ADDRESS = config['Swap_out']['strike_ln_address']
MAX_FEE_RATE = int(config['Swap_out']['max_fee_rate'])
PAYMENT_AMOUNT = int(config['Swap_out']['payment_amount'])
MIN_STRIKE_WITHDRAWAL = int(config['Swap_out']['min_strike_withdrawal'])
PERIOD = int(config['Get_channels_data']['PERIOD'])

def connect_lndg_db():
    return sqlite3.connect(LNDG_DB_PATH, timeout=30)

def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def create_table_if_not_exists():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strike_onchain_withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_quote_id TEXT UNIQUE,
            amount TEXT,
            currency TEXT,
            state TEXT,
            btc_address TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        ALTER TABLE strike_onchain_withdrawals ADD COLUMN btc_address TEXT;
    ''')
    conn.commit()
    conn.close()

def insert_quote(payment_quote_id, amount, currency, state, btc_address):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO strike_onchain_withdrawals (payment_quote_id, amount, currency, state, btc_address)
        VALUES (?, ?, ?, ?, ?)
    ''', (payment_quote_id, amount, currency, state, btc_address))
    conn.commit()
    conn.close()

def update_quote_state(payment_quote_id, new_state, payment_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE strike_onchain_withdrawals
        SET state = ?, payment_quote_id = ?
        WHERE payment_quote_id = ?
    ''', (new_state, payment_id, payment_quote_id))
    conn.commit()
    conn.close()

def update_payment_state(payment_id, new_state):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE strike_onchain_withdrawals
        SET state = ?
        WHERE payment_quote_id = ?
    ''', (new_state, payment_id))
    conn.commit()
    conn.close()

def get_pending_quote_amounts():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT amount FROM strike_onchain_withdrawals WHERE state = 'PENDING'
    ''')
    pending_quotes = cursor.fetchall()
    conn.close()

    total_pending_amount = 0
    for quote in pending_quotes:
        total_pending_amount += int(float(quote["amount"]) * 100_000_000)
    return total_pending_amount

def is_excluded(pubkey, exclusion_list):
    return pubkey in [entry['pubkey'] for entry in exclusion_list]

def get_onchain_balance():
    result = subprocess.run(['lncli', 'listunspent'], capture_output=True, text=True)
    if result.returncode == 0:
        utxos = json.loads(result.stdout).get("utxos", [])
        total_onchain = sum(int(utxo["amount_sat"]) for utxo in utxos)
        return total_onchain
    return 0

def get_payment_status(payment_id):
    url = f"https://api.strike.me/v1/payments/{payment_id}"
    
    headers = {
        'Authorization': f'Bearer {STRIKE_API_KEY}',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        logging.info(f"API response for payment {payment_id}: {data}")
        
        payment_state = data.get('state', 'UNKNOWN')
        
        return payment_state
    
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error while checking payment status: {http_err}")
    except Exception as err:
        logging.error(f"Error while checking payment status: {err}")

    return 'UNKNOWN'

def get_pending_onchain_withdrawals():
    headers = {
        'Authorization': f'Bearer {STRIKE_API_KEY}',
        'Accept': 'application/json',
    }

    pending_quotes = []

    try:
        response = requests.get('https://api.strike.me/v1/payments', headers=headers)
        response.raise_for_status()
        payments = response.json()

        for payment in payments:
            state = payment.get('state', 'UNKNOWN')
            if state == "PENDING":
                payment_type = payment.get('type', '').lower()
                payment_id = payment.get('paymentId', 'UNKNOWN')

                if payment_type == 'onchain':
                    payment_quote_id = payment.get('paymentQuoteId', None)

                    if payment_quote_id:
                        pending_quotes.append(payment_quote_id)
                        logging.info(f"Found pending onchain payment quote: {payment_quote_id}")
                    else:
                        logging.warning(f"No paymentQuoteId found for payment ID: {payment_id}")

        return pending_quotes

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error while retrieving pending onchain withdrawals: {http_err}")
    except Exception as err:
        logging.error(f"Error while retrieving pending onchain withdrawals: {err}")

    return []

def get_source_channels():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT chan_id, outbound_liquidity, pubkey, alias FROM opened_channels_{PERIOD}d WHERE tag = 'source'")
    channels = cursor.fetchall()
    conn.close()
    return channels

def send_payment_via_bos(ln_address, amount, fee_rate, peer_pubkey, alias):
    command = f"{BOS_PATH} send {ln_address} --amount {amount} --max-fee-rate {fee_rate} --out {peer_pubkey}"
    logging.info(f"Executing command: {command}")
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        logging.info(f"Payment of {amount} sats successfully sent via BOS through channel {alias}. STDOUT: {result.stdout}")
        return True
    else:
        logging.error(f"Error sending payment via BOS through channel {alias}. STDOUT: {result.stdout}, STDERR: {result.stderr}")
        return False

def create_invoice(amount_sats):
    result = subprocess.run(['lncli', 'addinvoice', '--amt', str(amount_sats)], capture_output=True, text=True)
    if result.returncode == 0:
        invoice_data = json.loads(result.stdout)
        return invoice_data['payment_request']
    return None

def get_strike_balance():
    headers = {
        'Authorization': f'Bearer {STRIKE_API_KEY}',
        'Accept': 'application/json',
    }

    url = 'https://api.strike.me/v1/balances'
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        balance_satoshis = 0
        for balance in data:
            if balance['currency'] == 'BTC':
                balance_satoshis = int(float(balance['available']) * 100_000_000)
                logging.info(f"Available Strike balance: {balance_satoshis} satoshis")
                break

        return balance_satoshis

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error retrieving balance: {http_err}")
    except Exception as err:
        logging.error(f"Error retrieving balance: {err}")
    return 0

def create_lightning_payment_quote(invoice):
    headers = {
        'Authorization': f'Bearer {STRIKE_API_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    payload = {
        'lnInvoice': invoice,
        'sourceCurrency': 'BTC',
    }

    try:
        response = requests.post('https://api.strike.me/v1/payment-quotes/lightning', json=payload, headers=headers)
        response.raise_for_status()
        quote_data = response.json()
        payment_quote_id = quote_data['paymentQuoteId']
        logging.info(f"Payment quote created successfully. ID: {payment_quote_id}")
        return payment_quote_id
    except requests.exceptions.HTTPError as e:
        logging.error(f"Error creating payment quote via Strike: {e}")
        return None

def execute_payment_quote(payment_quote_id):
    headers = {
        'Authorization': f'Bearer {STRIKE_API_KEY}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.patch(f'https://api.strike.me/v1/payment-quotes/{payment_quote_id}/execute', headers=headers)
        response.raise_for_status()
        execute_data = response.json()
        
        payment_id = execute_data.get('paymentId', payment_quote_id)
        logging.info(f"Payment executed successfully for quote {payment_quote_id}. Payment ID: {payment_id}")
        
        if payment_id and payment_id != payment_quote_id:
            update_quote_state(payment_id, 'PENDING', payment_id)
        else:
            logging.error(f"Error while updating payment_id in database: {e}")

        return True
    except requests.exceptions.HTTPError as e:
        logging.error(f"Error executing payment via Strike: {e}")
        return False

def generate_new_btc_address():
    try:
        result = subprocess.run(['lncli', 'newaddress', 'p2tr'], capture_output=True, text=True)
        if result.returncode == 0:
            address_data = json.loads(result.stdout)
            address = address_data['address']
            logging.info(f"New Taproot address generated: {address}")
            return address
        else:
            logging.error(f"Error generating address: {result.stderr}")
            return None
    except Exception as e:
        logging.error(f"Exception generating address: {str(e)}")
        return None

def withdraw_to_btc_address(btc_address, amount):
    headers = {
        'Authorization': f'Bearer {STRIKE_API_KEY}',
        'Content-Type': 'application/json',
    }

    payload = {
        'btcAddress': btc_address,
        'amount': {
            'amount': amount / 100_000_000,
            'currency': 'BTC'
        },
        'onchainTierId': 'tier_free'
    }

    try:
        response = requests.post('https://api.strike.me/v1/payment-quotes/onchain', json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        payment_quote_id = data['paymentQuoteId']
        amount_str = data['totalAmount']['amount']
        currency_str = data['totalAmount']['currency']

        logging.info(f"Onchain quote generated successfully: {payment_quote_id}")

        insert_quote(payment_quote_id, amount_str, currency_str, 'CREATED', btc_address)

        execute_payment_url = f'https://api.strike.me/v1/payment-quotes/{payment_quote_id}/execute'
        execute_response = requests.patch(execute_payment_url, headers=headers)
        execute_response.raise_for_status()

        execute_data = execute_response.json()
        payment_id = execute_data.get('paymentId')

        if payment_id:
            logging.info(f"Payment executed successfully. Payment ID: {payment_id}")
            update_quote_state(payment_quote_id, 'PENDING', payment_id)
            logging.info(f"State updated in the database to PENDING with paymentId {payment_id}.")
        else:
            logging.error(f"Could not retrieve paymentId for quote {payment_quote_id}.")

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error during withdrawal: {http_err}")
    except Exception as err:
        logging.error(f"Error during withdrawal: {err}")

def process_pending_withdrawals():
    logging.info("Checking status of pending withdrawals...")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT payment_quote_id FROM strike_onchain_withdrawals WHERE state = 'PENDING'")
    pending_quotes = cursor.fetchall()
    conn.close()

    for quote in pending_quotes:
        try:
            payment_id = quote["payment_quote_id"]
            payment_state = get_payment_status(payment_id)
            if payment_state in ['COMPLETED', 'FAILED']:
                update_payment_state(payment_id, payment_state)
                logging.info(f"Payment {payment_id} marked as {payment_state}.")
            else:
                logging.info(f"Payment {payment_id} is still pending.")
        except KeyError as e:
            logging.error(f"Error accessing column in row: {dict(quote)}, error: {e}")

def withdraw_onchain(amount):
    btc_address = generate_new_btc_address()
    if btc_address:
        withdraw_to_btc_address(btc_address, amount)
        logging.info(f"Successfully withdrew {amount} satoshis to BTC address {btc_address}.")
    else:
        logging.error("Failed to generate BTC address for withdrawal.")

def check_and_withdraw_onchain():
    current_balance = get_onchain_balance()
    pending_withdrawals = get_pending_quote_amounts()
    strike_balance = get_strike_balance()
    total_balance = current_balance + pending_withdrawals + strike_balance
    needed_amount = ONCHAIN_TARGET - total_balance
    logging.info(f"Pending Withdrawals: {pending_withdrawals} satoshis")
    logging.info(f"Total onchain balance: {total_balance}, needed to target: {needed_amount}.")

    if total_balance < ONCHAIN_TARGET:
        if needed_amount >= MIN_STRIKE_WITHDRAWAL and strike_balance >= needed_amount:
            withdraw_onchain(needed_amount)
        elif strike_balance >= WITHDRAW_AMOUNT_SATOSHIS:
            withdraw_onchain(WITHDRAW_AMOUNT_SATOSHIS)
        else:
            logging.info("Insufficient Strike balance for withdrawal.")
    else:
        logging.info("Onchain target reached. Checking for LN withdrawals...")
        process_strike_ln_withdrawal(strike_balance)

def process_strike_ln_withdrawal(strike_balance):
    if strike_balance > 0:
        invoice = create_invoice(strike_balance)
        if invoice and (payment_quote_id := create_lightning_payment_quote(invoice)):
            if execute_payment_quote(payment_quote_id):
                logging.info(f"Withdrawn {strike_balance} sats from Strike to LN.")
            else:
                logging.error("Error executing Strike payment quote.")

def process_bos_payments(exclusion_list):
    source_channels = get_source_channels()
    channels = [channel for channel in source_channels if channel[1] > OUTBOUND_THRESHOLD]

    logging.info(f"Starting BOS payments for {len(channels)} channels.")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(channels)) as executor:
        futures = {}
        for channel in channels:
            pubkey, alias = channel[2], channel[3]
            if is_excluded(pubkey, exclusion_list):
                logging.info(f"Channel {alias} excluded. Skipping...")
                continue
            futures[executor.submit(process_channel, pubkey, alias)] = alias

        for future in concurrent.futures.as_completed(futures):
            alias = futures[future]
            try:
                future.result()
            except Exception as e:
                logging.error(f"Error processing BOS payment for channel {alias}: {e}")

def process_channel(pubkey, alias):
    retries = 0
    while retries < MAX_RETRIES:
        logging.info(f"Attempting BOS payment via {alias}. Retry {retries + 1}.")
        if send_payment_via_bos(LN_ADDRESS, PAYMENT_AMOUNT, MAX_FEE_RATE, pubkey, alias):
            logging.info(f"Payment sent successfully via channel {alias}.")
            return
        retries += 1
        time.sleep(CHECK_INTERVAL_SECONDS)
    logging.error(f"Channel {alias} failed after {MAX_RETRIES} retries.")

def main():
    create_table_if_not_exists()
    while True:
        process_pending_withdrawals()

        with open(EXCLUSION_FILE_PATH, 'r') as f:
            exclusion_list = json.load(f).get('EXCLUSION_LIST', [])

        check_and_withdraw_onchain()

        current_balance = get_onchain_balance()
        if current_balance < ONCHAIN_TARGET:
            process_bos_payments(exclusion_list)
        else:
            logging.info("Onchain target achieved. Pausing checks.")

        logging.info(f"Pausing for {CHECK_INTERVAL_SECONDS} seconds.")
        time.sleep(CHECK_INTERVAL_SECONDS)
        
if __name__ == "__main__":
    main()
