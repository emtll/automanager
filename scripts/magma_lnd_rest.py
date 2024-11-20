import base64
import json
import configparser
import requests
import logging
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.abspath(os.path.join(script_dir, '..', 'logs'))

logging.basicConfig(
    filename=os.path.join(logs_dir, "magmaflow.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'automator.conf'))
config = configparser.ConfigParser()
config.read(config_file_path)

def expand_path(path):
    if not os.path.isabs(path):
        return os.path.join(os.path.expanduser("~"), path)
    return os.path.expanduser(path)

def get_expanded_path(key):
    relative_path = config['lnd'][key]
    return os.path.expanduser(os.path.join("~", relative_path))

LND_REST_URL = config['lnd']['LND_REST_URL']
LND_MACAROON_PATH = expand_path(config['lnd']['LND_MACAROON_PATH'])
LND_CERT_PATH = expand_path(config['lnd']['LND_CERT_PATH'])
API_MEMPOOL = 'https://mempool.space/api/v1/fees/recommended'
limit_cost = 0.7

def get_lnd_headers():
    with open(LND_MACAROON_PATH, 'rb') as f:
        macaroon = f.read().hex()
    headers = {
        'Grpc-Metadata-macaroon': macaroon,
        'Content-Type': 'application/json'
    }
    return headers

def get_fastest_fee():
    response = requests.get(API_MEMPOOL)
    data = response.json()
    if data:
        fast_fee = data['fastestFee']
        return fast_fee
    else:
        return None

def create_invoice(amt, memo, expiry):
    url = f"{LND_REST_URL}/v1/invoices"
    headers = get_lnd_headers()
    payload = {
        "value": amt,
        "memo": memo,
        "expiry": expiry
    }

    try:
        response = requests.post(url, headers=headers, json=payload, verify=LND_CERT_PATH)
        response.raise_for_status()
        response_json = response.json()
        r_hash = response_json.get("r_hash", "")
        payment_request = response_json.get("payment_request", "")
        return r_hash, payment_request

    except requests.exceptions.RequestException as e:
        logging.error(f"Error executing LND REST API addinvoice: {e}")
        return f"Error executing LND REST API addinvoice: {e}", None

    except json.JSONDecodeError as json_error:
        logging.error(f"Error decoding JSON from LND REST API: {json_error}")
        return f"Error decoding JSON: {json_error}", None
    
def connect_to_node(node_key_address):
    url = f"{LND_REST_URL}/v1/peers"
    headers = get_lnd_headers()

    try:
        pubkey, host = node_key_address.split("@")
    except ValueError:
        logging.error("Invalid node_key_address format. It should be in the format 'pubkey@host:port'.")
        return f"Invalid node_key_address format: {node_key_address}"
    payload = {
        "addr": {
            "pubkey": pubkey,
            "host": host
        },
        "perm": False
    }

    try:
        response = requests.post(url, headers=headers, json=payload, verify=LND_CERT_PATH)
        response.raise_for_status()
        logging.info(f"Successfully connected to node {node_key_address}")
        print(f"Successfully connected to node {node_key_address}")
        return 0

    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to node {node_key_address}: {e}")
        print(f"Error connecting to node {node_key_address}: {e}")
        return -1

def open_channel(pubkey, size, invoice):
    # Get the fastest fee rate
    print("Getting fastest fee...")
    fee_rate = get_fastest_fee()

    if fee_rate:
        print(f"Fastest Fee: {fee_rate} sat/vB")
       
        # Retrieve UTXOs and calculate fees and required outpoints
        print("Getting UTXOs, Fee Cost and Outpoints to open the channel")
        utxos_needed, fee_cost, related_outpoints = calculate_utxos_required_and_fees(size, fee_rate)
       
        # Check if there are enough UTXOs
        if utxos_needed == -1:
            msg_open = f"There isn't enough confirmed Balance to open a {size} SATS channel"
            print(msg_open)
            return -1, msg_open 
        
        # Check if the fee cost is less than the invoice amount
        if fee_cost >= float(invoice):
            msg_open = f"Can't open this channel now, the fee {fee_cost} is bigger or equal to {limit_cost*100}% of the Invoice paid by customer"
            print(msg_open)
            return -2, msg_open
        
        # Format outpoints into the required structure for the API
        formatted_outpoints = [{'txid_str': outpoint.split(':')[0], 'output_index': int(outpoint.split(':')[1])} for outpoint in related_outpoints]

        # Attempt to open the channel
        print(f"Opening Channel: {pubkey}")
        funding_tx = execute_lnd_rest(pubkey, fee_rate, formatted_outpoints, size)
        if funding_tx is None:
            msg_open = f"Problem executing the REST API to open the channel. Please check the Log Files"
            print(msg_open)
            return -3, msg_open
        msg_open = f"Channel opened with funding transaction: {funding_tx}"
        print(msg_open)
        return funding_tx, msg_open       

    else:
        print("Failed to retrieve the fastest fee.")
        return None
    
def execute_lnd_rest(node_pub_key, fee_per_vbyte, formatted_outpoints, input_amount):
    url = f"https://{LND_REST_URL}/v1/channels/stream"
    headers = get_lnd_headers()
    data = {
        'sat_per_vbyte': fee_per_vbyte,
        'node_pubkey': base64.b64encode(node_pub_key.encode()).decode(),
        'local_funding_amount': input_amount,
        'outpoints': formatted_outpoints,
    }

    try:
        print(f"Sending request to LND REST API with data: {json.dumps(data, indent=2)}")
        response = requests.post(url, headers=headers, json=data, verify=LND_CERT_PATH, stream=True)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return None

        for raw_response in response.iter_lines():
            json_response = json.loads(raw_response)
            if 'chan_open' in json_response:
                return json_response['chan_open']['funding_txid']
        
    except requests.RequestException as e:
        print(f"Error executing REST API request: {e}")
        log_content = f"Error: {e}\n"
        log_file_path = "amboss_open_rest.log"
        with open(log_file_path, "w") as log_file:
            log_file.write(log_content)

    return None
    
def get_channel_point(hash_to_find):
    url = f"{LND_REST_URL}/v1/channels/pending"
    headers = get_lnd_headers()

    try:
        response = requests.get(url, headers=headers, verify=LND_CERT_PATH)
        response.raise_for_status()
        data = response.json()
        pending_open_channels = data.get("pending_open_channels", [])

        for channel_info in pending_open_channels:
            channel_point = channel_info.get("channel", {}).get("channel_point", "")
            channel_hash = channel_point.split(":")[0]

            if channel_hash == hash_to_find:
                return channel_point

        logging.info(f"Hash {hash_to_find} not found in pending channels.")
        return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching pending channels: {e}")
        print(f"Error fetching pending channels: {e}")
        return None

    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from pending channels response: {e}")
        print(f"Error decoding JSON from pending channels response: {e}")
        return None

def get_utxos():
    url = f"{LND_REST_URL}/v1/utxos"
    headers = get_lnd_headers()
    params = {
        "min_confs": 3,
        "max_confs": 9999999
    }

    try:
        response = requests.get(url, headers=headers, params=params, verify=LND_CERT_PATH)
        response.raise_for_status()
        data = response.json()
        utxos = data.get("utxos", [])
        utxos = sorted(utxos, key=lambda x: x.get("amount_sat", 0), reverse=True)
        logging.info(f"Fetched and sorted UTXOs: {utxos}")
        print(f"UTXOs: {utxos}")
        return utxos

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching UTXOs: {e}")
        print(f"Error fetching UTXOs: {e}")
        return []

    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from UTXOs response: {e}")
        print(f"Error decoding JSON from UTXOs response: {e}")
        return []

def calculate_utxos_required_and_fees(amount_input, fee_per_vbyte):
    utxos_data = get_utxos()
    channel_size = float(amount_input)
    total = sum(utxo["amount_sat"] for utxo in utxos_data)
    utxos_needed = 0
    amount_with_fees = channel_size
    related_outpoints = []

    if total < channel_size:
        print(f"There are not enough UTXOs to open a channel of {channel_size} sats. Total UTXOs: {total} sats.")
        return -1, 0, None
    
    for utxo in utxos_data:
        utxos_needed += 1
        transaction_size = calculate_transaction_size(utxos_needed)
        fee_cost = transaction_size * fee_per_vbyte
        amount_with_fees = channel_size + fee_cost

        related_outpoints.append(utxo['outpoint'])

        if utxo['amount_sat'] >= amount_with_fees:
            break
        channel_size -= utxo['amount_sat']

    return utxos_needed, fee_cost, related_outpoints if related_outpoints else None

def calculate_transaction_size(utxos_needed):
    inputs_size = utxos_needed * 57.5
    outputs_size = 2 * 43
    overhead_size = 10.5
    total_size = inputs_size + outputs_size + overhead_size
    return total_size
