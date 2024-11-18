import requests
import configparser
import logging
import os
import math
import json

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

def get_expanded_path(key):
    relative_path = config['lnd'][key]
    return os.path.expanduser(os.path.join("~", relative_path))

API_KEY = config['Magmaflow']['API_KEY']
MAGMA_API_URL = config['Magmaflow']['MAGMA_API_URL']
PUBKEY = config['lnd']['PUBKEY']
ONCHAIN_MULTIPLIER = int(config['Magmaflow']['ONCHAIN_MULTIPLIER'])
ONCHAIN_PRIORITY = config['Magmaflow']['ONCHAIN_PRIORITY']
BASE_FEE = int(config['Magmaflow']['BASE_FEE'])
LND_REST_URL = config['lnd']['LND_REST_URL']
LND_MACAROON_PATH = get_expanded_path('LND_MACAROON_PATH')
LND_CERT_PATH = get_expanded_path('LND_CERT_PATH')

def get_lnd_headers():
    try:
        with open(LND_MACAROON_PATH, 'rb') as f:
            macaroon = f.read().hex()
        headers = {
            'Grpc-Metadata-macaroon': macaroon,
            'Content-Type': 'application/json'
        }
        logging.debug("LND headers successfully created.")
        return headers
    except Exception as e:
        logging.error(f"Failed to create LND headers: {e}")
        raise

def get_onchain_balance():
    headers = get_lnd_headers()
    url = f"{LND_REST_URL}/v2/wallet/utxos"
    data = {
        "min_confs": 1,
        "max_confs": 9999999
    }
    try:
        response = requests.post(url, headers=headers, json=data, verify=LND_CERT_PATH)
        response.raise_for_status()
        utxos = response.json().get('utxos', [])
        total_balance = sum(int(utxo['amount_sat']) for utxo in utxos)
        onchain_balance = math.floor(total_balance / 1_000_000) * 1_000_000
        logging.info(f"On-chain balance: {onchain_balance} satoshis")
        return onchain_balance
    except requests.exceptions.RequestException as e:
        logging.error(f"Error obtaining on-chain balance: {e}")
        return None

def orders(pubkey, api_key):
    url = 'https://api.amboss.space/graphql'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    payload = {
        'query': '''
        query GetOffers($pubkey: String) {
          getOffers(pubkey: $pubkey) {
            list {
              id
              amboss_fee_rate
              fee_rate
              max_size
              min_size
              offer_type
              status
              total_size
              min_block_length
              side
              onchain_multiplier
              onchain_priority
              base_fee
              base_fee_cap
              fee_rate_cap
              fee_rate
            }
          }
        }
        ''',
        'variables': {
            'pubkey': pubkey
        }
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logging.info("Successfully fetched orders from Magma.")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching orders: {e}")
        return None

def get_locked_size(offer_id):
    url = 'https://api.amboss.space/graphql'
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        'query': '''
        query GetOffer($getOfferId: String!) {
          getOffer(id: $getOfferId) {
            orders {
              locked_size
            }
          }
        }
        ''',
        'variables': {
            'getOfferId': offer_id
        }
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        orders = data.get('data', {}).get('getOffer', {}).get('orders', {})
        if isinstance(orders, dict):
            locked_size = int(orders.get('locked_size', 0))
            logging.info(f"Locked size for offer {offer_id}: {locked_size} satoshis")
            return locked_size
        else:
            logging.warning(f"Unexpected 'orders' structure for offer {offer_id}: {orders}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error obtaining locked size for offer {offer_id}: {e}")
        return None

def update_offer(
    offer_id, 
    total_size, 
    onchain_multiplier=None, 
    onchain_priority=None, 
    base_fee=None, 
    max_size=None, 
    min_block_length=None, 
    base_fee_cap=None, 
    fee_rate_cap=None, 
    fee_rate=None
):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    input_data = {
        "offer": offer_id,
        "total_size": total_size,
        "min_block_length": min_block_length,
        "base_fee_cap": base_fee_cap,
        "fee_rate_cap": fee_rate_cap,
        "fee_rate": fee_rate,
        "max_size": max_size,
    }
    
    if onchain_priority and onchain_multiplier:
        input_data["onchain_priority"] = onchain_priority
        input_data["onchain_multiplier"] = onchain_multiplier
    elif base_fee is not None:
        input_data["base_fee"] = base_fee

    payload = {
        "query": '''
        mutation UpdateOffer($input: UpdateOffer!) {
          updateOffer(input: $input)
        }
        ''',
        "variables": {"input": input_data},
    }

    logging.debug(f"Final Payload Being Sent:\n{json.dumps(payload, indent=4)}")

    try:
        response = requests.post(MAGMA_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            logging.error(f"Error updating offer {offer_id}: {data['errors']}")
        else:
            logging.info(f"Offer {offer_id} updated successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error while updating offer {offer_id}: {e}")

def main():
    onchain_balance = get_onchain_balance()
    if onchain_balance is None:
        logging.error("Failed to obtain on-chain balance. Exiting.")
        return

    result = orders(PUBKEY, API_KEY)
    if not result:
        logging.error("Failed to fetch orders. Exiting.")
        return

    offers = result.get('data', {}).get('getOffers', {}).get('list', [])
    if not offers:
        logging.warning("No offers found. Exiting.")
        return

    for offer in offers:
        offer_id = offer['id']
        locked_size = get_locked_size(offer_id)

        if locked_size is None:
            logging.warning(f"Skipping offer {offer_id} due to missing locked size.")
            continue

        onchain_multiplier = int(offer.get('onchain_multiplier', ONCHAIN_MULTIPLIER))
        onchain_priority = offer.get('onchain_priority', ONCHAIN_PRIORITY)
        base_fee = int(offer.get('base_fee', BASE_FEE))
        min_block_length = int(offer.get('min_block_length', 12960))
        base_fee_cap = int(offer.get('base_fee_cap', 1))
        fee_rate_cap = int(offer.get('fee_rate_cap', 2500))
        fee_rate = int(offer.get('fee_rate', 3000))

        current_total_size = int(offer['total_size'])
        current_max_size = int(offer['max_size'])
        new_total_size = onchain_balance + locked_size
        new_max_size = onchain_balance

        if new_total_size != current_total_size or new_max_size != current_max_size:
            logging.info(
                f"Updating offer {offer_id} with total size {new_total_size}, "
                f"max size {new_max_size}, onchain_multiplier {onchain_multiplier}, "
                f"onchain_priority {onchain_priority}, base_fee {base_fee}, "
                f"min_block_length {min_block_length}, base_fee_cap {base_fee_cap}, "
                f"fee_rate_cap {fee_rate_cap}, fee_rate {fee_rate}."
            )
            update_offer(
                offer_id=offer_id,
                total_size=new_total_size,
                onchain_multiplier=onchain_multiplier,
                onchain_priority=onchain_priority,
                base_fee=base_fee,
                max_size=new_max_size,
                min_block_length=min_block_length,
                base_fee_cap=base_fee_cap,
                fee_rate_cap=fee_rate_cap,
                fee_rate=fee_rate
            )
        else:
            logging.info(f"Offer {offer_id} is up to date.")

if __name__ == "__main__":
    main()
