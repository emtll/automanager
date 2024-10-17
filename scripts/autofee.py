import json
import os
import configparser
import sqlite3
from datetime import datetime, timedelta

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'general.conf'))
config = configparser.ConfigParser()
config.read(config_file_path)

def expand_path(path):
    if not os.path.isabs(path):
        return os.path.join(os.path.expanduser("~"), path)
    return os.path.expanduser(path)

BOS_PATH = expand_path(config['Paths']['bos_path'])
DB_PATH = expand_path(config['Paths']['db_path'])
EXCLUSION_FILE_PATH = expand_path(config['Paths']['excluded_peers_path'])
SLEEP_GET_CHANNELS_AND_AUTOFEE = int(config['Automation']['sleep_get_channels_and_autofee'])
MAX_FEE_THRESHOLD = int(config['Autofee']['max_fee_threshold'])
PERIOD = config['Autofee']['table_period']

def print_with_timestamp(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def issue_bos_command(peer_pubkey, update_fee):
    command = f"{BOS_PATH} fees --set-fee-rate {update_fee} --to {peer_pubkey}"
    print_with_timestamp(f"Executing: {command}")
    os.system(command)

def days_since_last_activity(last_activity):
    if last_activity is None or last_activity == '':
        return float('inf')
    if isinstance(last_activity, int):
        last_activity_date = datetime.fromtimestamp(last_activity)
    else:
        last_activity_date = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
    return (datetime.now() - last_activity_date).days

def calculate_new_fee(total_cost_ppm):
    return int(total_cost_ppm / 0.8)  # Adds 20% margin

def is_excluded(pubkey, exclusion_list):
    return pubkey in [entry['pubkey'] for entry in exclusion_list]

def fee_change_checker(chan_id, table_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    time_limit = datetime.now() - timedelta(seconds=SLEEP_GET_CHANNELS_AND_AUTOFEE)
    
    cursor.execute(f"""
        SELECT last_outgoing_activity FROM {table_name}
        WHERE chan_id = ? AND last_outgoing_activity >= ?
        ORDER BY last_outgoing_activity DESC LIMIT 1
    """, (chan_id, time_limit.strftime('%Y-%m-%d %H:%M:%S')))
    
    result = cursor.fetchone()
    conn.close()
    
    return result is not None

def adjust_new_channel_fee(channel):
    outbound_ratio = channel[6]      # outbound_liquidity
    days_since_opening = channel[8]  # days_open
    local_fee_rate = channel[25]     # local_fee_rate
    last_outgoing = channel[27]      # last_outgoing_activity
    last_incoming = channel[28]      # last_incoming_activity
    last_rebalance = channel[29]     # last_rebalance

    if days_since_opening >= 2 and outbound_ratio == 0 and last_incoming is None and last_rebalance is None:
        return int(local_fee_rate * 1.05)  # Fee Increase 5%
    elif outbound_ratio == 100 and days_since_opening >= 3 and last_outgoing is None:
        return int(local_fee_rate * 0.95)  # Fee Decrease 5%
    elif outbound_ratio == 50 and days_since_opening >= 3 and last_outgoing is None:
        return int(local_fee_rate * 0.95)  # Fee Decrease 5%

    return local_fee_rate  # No Update

def adjust_sink_fee(channel):
    outbound_ratio = channel[6]      # outbound_liquidity
    total_cost_ppm = channel[12]     # cost_ppm
    local_fee_rate = channel[25]     # local_fee_rate
    last_rebalance = channel[29]     # last_rebalance
    last_outgoing = channel[27]      # last_outgoing_activity

    # Ajuste para lidar com None e valores adequados
    if outbound_ratio <= 10.0 and days_since_last_activity(last_rebalance) >= 2 and local_fee_rate < MAX_FEE_THRESHOLD:
        return int(local_fee_rate * 1.05)  # Fee Increase 5%
    elif outbound_ratio <= 10.0 and days_since_last_activity(last_rebalance) < 2 and local_fee_rate < MAX_FEE_THRESHOLD:
        return int(local_fee_rate * 1.03)  # Fee Increase 3%
    elif outbound_ratio >= 10.0 and outbound_ratio < 30.0 and days_since_last_activity(last_rebalance) >= 3:
        return int(local_fee_rate * 1.02)  # Fee Increase 2%
    elif outbound_ratio >= 30.0 and days_since_last_activity(last_outgoing) >= 3:
        new_fee = int(local_fee_rate * 0.99)  # Fee Decrease 1%
        if new_fee > total_cost_ppm:
            return new_fee
        else:
            return local_fee_rate
    else:
        return calculate_new_fee(total_cost_ppm)  # Cost PPM + 20%
        
def adjust_router_fee(channel):
    outbound_ratio = channel[6]      # outbound_liquidity
    total_cost_ppm = channel[12]     # cost_ppm
    local_fee_rate = channel[25]     # local_fee_rate
    last_rebalance = channel[29]     # last_rebalance
    last_outgoing = channel[27]      # last_outgoing_activity

    if outbound_ratio <= 10.0 and days_since_last_activity(last_rebalance) >= 1 and local_fee_rate < MAX_FEE_THRESHOLD:
        return int(local_fee_rate * 1.03)  # Fee Increase 3%
    elif outbound_ratio <= 10.0 and days_since_last_activity(last_rebalance) < 1 and local_fee_rate < MAX_FEE_THRESHOLD:
        return int(local_fee_rate * 1.02)  # Fee Increase 2%
    elif outbound_ratio >= 10.0 and outbound_ratio < 30.0 and days_since_last_activity(last_rebalance) >= 3:
        return int(local_fee_rate * 1.01)  # Fee Increase 1%
    elif outbound_ratio >= 30.0 and days_since_last_activity(last_outgoing) >= 3:
        new_fee = int(local_fee_rate * 0.99)  # Fee Decrease 1%
        if new_fee > total_cost_ppm:
            return new_fee
        else:
            return local_fee_rate
    else:
        return calculate_new_fee(total_cost_ppm)  # Cost PPM + 20%

def adjust_source_fee(channel):
    total_routed_out = channel[14]   # total_routed_out
    if total_routed_out > 0:
        return 10  # Set Fee Rate to 10ppm 
    else:
        return 0  # Set Fee Rate to 0ppm

def main():
    with open(EXCLUSION_FILE_PATH, 'r') as exclusion_file:
        exclusion_data = json.load(exclusion_file)
        exclusion_list = exclusion_data['EXCLUSION_LIST']

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    table_name = f'opened_channels_{PERIOD}d'
    cursor.execute(f"SELECT * FROM {table_name}")
    channels_data = cursor.fetchall()

    for channel in channels_data:
        chan_id = channel[0]
        pubkey = channel[1]
        alias = channel[2]
        tag = channel[4]
        local_fee_rate = channel[25]

        if is_excluded(pubkey, exclusion_list):
            print_with_timestamp(f"Channel {alias} ({pubkey}) is in the exclusion list, skipping...")
            continue

        if fee_change_checker(chan_id, table_name):
            print_with_timestamp(f"Channel {alias} ({pubkey}) had a recent fee change, skipping...")
            continue

        if tag == "new_channel":
            new_fee = adjust_new_channel_fee(channel)
        elif tag == "sink":
            new_fee = adjust_sink_fee(channel)
        elif tag == "router":
            new_fee = adjust_router_fee(channel)
        elif tag == "source":
            new_fee = adjust_source_fee(channel)
        else:
            print_with_timestamp(f"Unknown tag for {alias}, skipping...")
            continue

        if new_fee != local_fee_rate:
            print_with_timestamp(f"Adjusting fee for channel {alias} ({pubkey}) to {new_fee}")
            issue_bos_command(pubkey, new_fee)
        else:
            print_with_timestamp(f"Fee for channel {alias} ({pubkey}) remains unchanged")

    conn.close()

if __name__ == "__main__":
    main()
