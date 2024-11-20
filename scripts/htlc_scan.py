import os
import json
import logging
import requests
import configparser
import time
from datetime import datetime
from pathlib import Path

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.abspath(os.path.join(script_dir, '..', 'logs'))

if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

logging.basicConfig(
    filename=os.path.join(logs_dir, "htlc_scan.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

config_file_path = os.path.abspath(os.path.join(script_dir, '..', 'automator.conf'))
config = configparser.ConfigParser()
config.read(config_file_path)

def get_expanded_path(key):
    relative_path = config['lnd'][key]
    return os.path.expanduser(os.path.join("~", relative_path))

LND_REST_URL = config['lnd']['LND_REST_URL']
LND_MACAROON_PATH = get_expanded_path('LND_MACAROON_PATH')
LND_CERT_PATH = get_expanded_path(('LND_CERT_PATH'))
BOT_TOKEN = config['Telegram']['bot_token']
CHAT_ID = config['Telegram']['chat_id']
BLOCKS_TIL_EXPIRY = 18

def get_lnd_headers():
    with open(LND_MACAROON_PATH, "rb") as f:
        macaroon = f.read().hex()
    return {
        "Grpc-Metadata-macaroon": macaroon,
        "Content-Type": "application/json",
    }

def get_alias(lnd_rest_url, lnd_macaroon_path, lnd_cert_path):
    try:
        macaroon = Path(lnd_macaroon_path).read_bytes().hex()
        headers = {"Grpc-Metadata-macaroon": macaroon}
        response = requests.get(f"{lnd_rest_url}/v1/getinfo", headers=headers, verify=lnd_cert_path)

        if response.status_code == 200:
            data = response.json()
            self_alias = data.get("alias", "Unknown")
            return self_alias
        else:
            return f"Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"Unexpected error: {e}"

def send_telegram_message(message):
    NODE_NAME = get_alias(LND_REST_URL, LND_MACAROON_PATH, LND_CERT_PATH)
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("BOT_TOKEN or CHAT_ID is not configured. Cannot send Telegram message.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": f"🤖 HTLC Scan {NODE_NAME}\n\n{message}",
        "parse_mode": "HTML",
    }
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending Telegram message: {e}")

def reconnect_peer(pubkey):
    headers = get_lnd_headers()
    disconnect_url = f"{LND_REST_URL}/v1/peers/{pubkey}"
    try:
        disconnect_response = requests.delete(disconnect_url, headers=headers, verify=LND_CERT_PATH)
        if disconnect_response.status_code == 200:
            send_telegram_message(f"Disconnected peer {pubkey}")
        else:
            send_telegram_message(f"Failed to disconnect peer {pubkey}: {disconnect_response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error disconnecting peer {pubkey}: {e}")

    time.sleep(30)

    get_node_info_url = f"{LND_REST_URL}/v1/graph/node/{pubkey}"
    try:
        node_info_response = requests.get(get_node_info_url, headers=headers, verify=LND_CERT_PATH)
        node_info_response.raise_for_status()
        addresses = node_info_response.json().get("node", {}).get("addresses", [])
        if addresses:
            address = addresses[0].get("addr")
            connect_url = f"{LND_REST_URL}/v1/peers"
            data = {"addr": {"pubkey": pubkey, "host": address}}
            connect_response = requests.post(connect_url, headers=headers, json=data, verify=LND_CERT_PATH)
            if connect_response.status_code == 200:
                send_telegram_message(f"Reconnected peer {pubkey}")
            else:
                send_telegram_message(f"Failed to reconnect peer {pubkey}: {connect_response.text}")
        else:
            send_telegram_message(f"No address found for peer {pubkey}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error reconnecting peer {pubkey}: {e}")

def main():
    headers = get_lnd_headers()
    get_info_url = f"{LND_REST_URL}/v1/getinfo"
    try:
        response = requests.get(get_info_url, headers=headers, verify=LND_CERT_PATH)
        response.raise_for_status()
        current_block_height = response.json().get("block_height")
        max_expiry = current_block_height + BLOCKS_TIL_EXPIRY
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching block height: {e}")
        return

    list_channels_url = f"{LND_REST_URL}/v1/channels"
    try:
        response = requests.get(list_channels_url, headers=headers, verify=LND_CERT_PATH)
        response.raise_for_status()
        channels = response.json().get("channels", [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching channels: {e}")
        return

    total_pending_htlcs = sum(len(channel.get("pending_htlcs", [])) for channel in channels)

    htlcs_found = False
    for channel in channels:
        pending_htlcs = channel.get("pending_htlcs", [])
        for htlc in pending_htlcs:
            if htlc.get("expiration_height", 0) < max_expiry:
                htlcs_found = True
                pubkey = channel.get("remote_pubkey")
                alias = channel.get("alias", pubkey)
                expiration_height = htlc.get("expiration_height", 0)
                blocks_to_expire = expiration_height - current_block_height

                if htlc.get("incoming"):
                    message = f"⚠ Incoming HTLC from {alias} expires in {blocks_to_expire} blocks"
                else:
                    message = f"⚠ Outgoing HTLC to {alias} expires in {blocks_to_expire} blocks"

                send_telegram_message(message)
                reconnect_peer(pubkey)

    if not htlcs_found:
        message = f"🔎 Executing HTLC SCAN...\n\nNo critical HTLCs found\n{total_pending_htlcs} pending HTLCs"
        send_telegram_message(message)

if __name__ == "__main__":
    main()
