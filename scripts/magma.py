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

AMBOSS_TOKEN = config['Magmaflow']['API_KEY']

def check_offers():
    url = 'https://api.amboss.space/graphql'
    headers = {
        'content-type': 'application/json',
        'Authorization': f'Bearer {AMBOSS_TOKEN}',
    }
    payload = {
        "query": "query List {\n  getUser {\n    market {\n      offer_orders {\n        list {\n          id\n          seller_invoice_amount\n          status\n        }\n      }\n    }\n  }\n}"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json().get('data', {})
        market = data.get('getUser', {}).get('market', {})
        offer_orders = market.get('offer_orders', {}).get('list', [])
        print("All Offers:", offer_orders)
        valid_channel_opening_offer = next((offer for offer in offer_orders if offer.get('status') == "WAITING_FOR_SELLER_APPROVAL"), None)
        print("Found Offer:", valid_channel_opening_offer)

        if not valid_channel_opening_offer:
            print("No orders with status 'WAITING_FOR_SELLER_APPROVAL' waiting for approval.")
            return None

        return valid_channel_opening_offer

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while processing the request: {str(e)}")
        return None
    
def accept_order(order_id, payment_request):
    url = 'https://api.amboss.space/graphql'
    headers = {
        'content-type': 'application/json',
        'Authorization': f'Bearer {AMBOSS_TOKEN}',
    }
    query = '''
        mutation AcceptOrder($sellerAcceptOrderId: String!, $request: String!) {
          sellerAcceptOrder(id: $sellerAcceptOrderId, request: $request)
        }
    '''
    variables = {"sellerAcceptOrderId": order_id, "request": payment_request}

    response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
    return response.json()

def check_channel():
    url = 'https://api.amboss.space/graphql'
    headers = {
        'content-type': 'application/json',
        'Authorization': f'Bearer {AMBOSS_TOKEN}',
    }
    payload = {
        "query": "query List {\n  getUser {\n    market {\n      offer_orders {\n        list {\n          id\n          size\n          status\n        account\n        seller_invoice_amount\n        }\n      }\n    }\n  }\n}"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json().get('data', {})
        market = data.get('getUser', {}).get('market', {})
        offer_orders = market.get('offer_orders', {}).get('list', [])
        print("All Offers:", offer_orders)
        valid_channel_to_open = next((offer for offer in offer_orders if offer.get('status') == "WAITING_FOR_CHANNEL_OPEN"), None)
        print("Found Offer:", valid_channel_to_open)

        if not valid_channel_to_open:
            print("No orders with status 'WAITING_FOR_CHANNEL_OPEN' waiting for execution.")
            return None

        return valid_channel_to_open

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while processing the request: {str(e)}")
        return None
    
def get_address_by_pubkey(peer_pubkey):
    url = 'https://api.amboss.space/graphql'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {AMBOSS_TOKEN}'
    }
    query = f"""
    query List($pubkey: String!) {{
      getNode(pubkey: $pubkey) {{
        graph_info {{
          node {{
            addresses {{
              addr
            }}
          }}
        }}
      }}
    }}
    """
    variables = {
        "pubkey": peer_pubkey
    }
    payload = {
        "query": query,
        "variables": variables
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        addresses = data.get('data', {}).get('getNode', {}).get('graph_info', {}).get('node', {}).get('addresses', [])
        first_address = addresses[0]['addr'] if addresses else None

        if first_address:
            return f"{peer_pubkey}@{first_address}"
        else:
            return None
    else:
        print(f"Error: {response.status_code}")
        return None
    
def confirm_channel_point_to_amboss(order_id, transaction):
    url = 'https://api.amboss.space/graphql'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {AMBOSS_TOKEN}'
    }

    graphql_query = f'mutation Mutation($sellerAddTransactionId: String!, $transaction: String!) {{\n  sellerAddTransaction(id: $sellerAddTransactionId, transaction: $transaction)\n}}'
    
    data = {
        'query': graphql_query,
        'variables': {
            'sellerAddTransactionId': order_id,
            'transaction': transaction
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        json_response = response.json()

        if 'errors' in json_response:
            # Handle error in the JSON response and log it
            error_message = json_response['errors'][0]['message']
            log_content = f"Error in confirm_channel_point_to_amboss:\nOrder ID: {order_id}\nTransaction: {transaction}\nError Message: {error_message}\n"
            log_file_path_conf = "amboss_confirm_channel.log"
            with open(log_file_path_conf, "w") as log_file:
                log_file.write(log_content)

            return log_content
        else:
            return json_response

    except requests.exceptions.RequestException as e:
        print(f"Error making the request: {e}")
        return None