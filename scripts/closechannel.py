import subprocess
import time
import sqlite3
import os
import requests
import configparser
import json 
from datetime import datetime

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'general.conf'))
config = configparser.ConfigParser()
config.read(config_file_path)

def expand_path(path):
    if not os.path.isabs(path):
        return os.path.join(os.path.expanduser("~"), path)
    return os.path.expanduser(path)

user_path = os.path.expanduser("~")
db_path = expand_path(config['Paths']['db_path'])
charge_lnd_config_dir = expand_path(config['Paths']['charge_lnd_config_dir'])
excluded_peers_path = expand_path(config['Paths']['excluded_peers_path'])
mempool_api_url_recomended_fees = config['API']['mempool_api_url_base']

charge_lnd_bin = config['Closechannel']['charge_lnd_bin']
charge_lnd_interval = int(config['Closechannel']['charge_lnd_interval'])
htlc_check_interval = int(config['Closechannel']['htlc_check_interval'])
movement_threshold_perc = int(config['Closechannel']['movement_threshold_perc'])
max_fee_rate = int(config['Closechannel']['max_fee_rate'])
days_inactive_source = int(config['Closechannel']['days_inactive_source'])
days_inactive_sink = int(config['Closechannel']['days_inactive_sink'])
days_inactive_router = int(config['Closechannel']['days_inactive_router'])

def print_with_timestamp(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def create_or_update_config(chan_id):
    config_path = os.path.join(charge_lnd_config_dir, f"{chan_id}.conf")
    config_lines = []

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_lines = f.readlines()

    start_idx = None
    end_idx = None
    for i, line in enumerate(config_lines):
        if line.strip().lower() == '[disable-channels]':
            start_idx = i
            for j in range(i + 1, len(config_lines)):
                if config_lines[j].startswith('['):
                    end_idx = j
                    break
            break
    
    if start_idx is not None:
        config_lines[start_idx + 1:end_idx] = [
            f"chan.id = {chan_id}\n",
            "strategy = disable\n"
        ]
    else:
        config_lines.append("\n[disable-channels]\n")
        config_lines.append(f"chan.id = {chan_id}\n")
        config_lines.append("strategy = disable\n")

    with open(config_path, 'w') as f:
        f.writelines(config_lines)

    return config_path

def execute_charge_lnd(config_path):
    result = subprocess.run(
        [charge_lnd_bin, "-c", config_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    print("charge-lnd output:\n", result.stdout)
    if result.stderr:
        print("charge-lnd errors:\n", result.stderr)

def check_pending_htlcs(chan_id, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gui_pendinghtlcs WHERE chan_id = ?", (chan_id,))
    pending_htlcs = cursor.fetchall()
    conn.close()
    if pending_htlcs:
        print(f"Pending HTLC found for channel {chan_id}. Retrying in {htlc_check_interval} seconds...")
        return True
    return False

def get_high_priority_fee():
    response = requests.get(mempool_api_url_recomended_fees)
    if response.status_code == 200:
        fees = response.json()
        return fees.get("fastestFee", None)
    else:
        print(f"Error accessing Mempool.Space API: {response.status_code}")
        return None

def days_since_activity(activity_date):
    if activity_date is None:
        return float('inf')
    last_activity = datetime.strptime(activity_date, '%Y-%m-%d %H:%M:%S')
    return (datetime.now() - last_activity).days

def load_excluded_peers():
    with open(excluded_peers_path, 'r') as f:
        excluded_data = json.load(f)
    return [peer for peer in excluded_data['EXCLUSION_LIST']]

def get_channel_info(chan_id):
    command = ["lncli", "getchaninfo", chan_id]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    else:
        print(f"Error fetching channel info: {result.stderr}")
        return None

def close_channel(funding_txid, output_index, sat_per_vbyte):
    command = [
        "lncli", "closechannel", 
        "--funding_txid", funding_txid, 
        "--output_index", str(output_index), 
        "--sat_per_vbyte", str(sat_per_vbyte)
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Channel closed successfully: {result.stdout}")
        return True
    else:
        print(f"Error closing channel: {result.stderr}")
        return False

def calculate_movement_percentage(channel):
    capacity = channel[5]  # 'capacity' column
    total_routed_in = channel[14]  # total_routed_in
    total_routed_out = channel[13]  # total_routed_out
    total_movement = total_routed_in + total_routed_out
    movement_percentage = (total_movement / capacity) * 100 if capacity > 0 else 0
    
    return movement_percentage

def should_close_channel(channel, excluded_peers):
    tag = channel[4]  # 'tag'column
    chan_id = channel[0]  # 'chan_id' column
    movement_percentage = calculate_movement_percentage(channel)

    if channel[1] in excluded_peers:  # 'pubkey' column
        print(f"Channel {chan_id} is in the excluded peers list, skipping.")
        return False

    if tag == 'new_channel':
        print(f"Channel {chan_id} is a new channel, skipping.")
        return False
    
    if tag == 'source':
        last_incoming_activity = channel[28]  # last_incoming_activity
        if days_since_activity(last_incoming_activity) > days_inactive_source and movement_percentage < movement_threshold_perc:
            return True

    if tag == 'sink':
        last_outgoing_activity = channel[27]  # last_outgoing_activity
        if days_since_activity(last_outgoing_activity) > days_inactive_sink and movement_percentage < movement_threshold_perc:
            return True

    if tag == 'router':
        last_incoming_activity = channel[28]  # last_incoming_activity
        last_outgoing_activity = channel[27]  # last_outgoing_activity
        if days_since_activity(last_incoming_activity) > days_inactive_router and days_since_activity(last_outgoing_activity) > days_inactive_router and movement_percentage < movement_threshold_perc:
            return True

    return False

def monitor_and_close_channels():
    excluded_peers = load_excluded_peers()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    table_name = 'opened_channels_lifetime'
    cursor.execute(f"SELECT * FROM {table_name}")
    channels_data = cursor.fetchall()

    for channel in channels_data:
        chan_id = channel[0]  # chan_id
        if should_close_channel(channel, excluded_peers):
            print_with_timestamp(f"Closing channel {chan_id}...")
            config_path = create_or_update_config(chan_id)
            execute_charge_lnd(config_path)

            channel_info = get_channel_info(chan_id)
            if channel_info and "chan_point" in channel_info:
                funding_txid, output_index = channel_info["chan_point"].split(':')
                if not check_pending_htlcs(chan_id, db_path):
                    while True:
                        high_priority_fee = get_high_priority_fee()
                        if high_priority_fee is not None:
                            if high_priority_fee <= max_fee_rate:
                                print(f"Closing channel {chan_id} with high priority fee {high_priority_fee}.")
                                close_channel(funding_txid, output_index, high_priority_fee)
                                return
                            else:
                                print(f"High priority fee {high_priority_fee} is too high. Waiting 1 hour to check again.")
                                time.sleep(3600)
                        else:
                            print("Failed to retrieve high priority fee. Retrying in 1 hour...")
                            time.sleep(3600)
            else:
                print(f"Error retrieving channel info for {chan_id}.")
            return

    conn.close()

if __name__ == "__main__":
    while True:
        monitor_and_close_channels()
