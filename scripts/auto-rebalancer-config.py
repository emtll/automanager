import json
import subprocess
import configparser
import os
import sqlite3 

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'general.conf'))
config = configparser.ConfigParser()
config.read(config_file_path)

def expand_path(path):
    if not os.path.isabs(path):
        return os.path.join(os.path.expanduser("~"), path)
    return os.path.expanduser(path)

REGOLANCER_JSON_PATH = expand_path(config['Paths']['regolancer_json_path'])
DB_PATH = expand_path(config['Paths']['db_path'])
EXCLUDED_PEERS_PATH = expand_path(config['Paths']['excluded_peers_path'])
SERVICE_NAME = config['AutoRebalancer']['regolancer-controller_service']

def restart_service(service_name):
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', service_name], check=True)
        print(f"Service {service_name} restarted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error restarting service {service_name}: {e}")

def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def save_json(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def has_list_changed(old_list, new_list):
    return set(old_list) != set(new_list)

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def get_channels_data(conn):
    cursor = conn.cursor()
    query = """
    SELECT chan_id, pubkey, tag
    FROM opened_channels_lifetime
    """
    cursor.execute(query)
    return cursor.fetchall()

def main():
    regolancer_config = load_json(REGOLANCER_JSON_PATH)
    conn = connect_db()
    channels_data = get_channels_data(conn)
    conn.close()
    excluded_peers = load_json(EXCLUDED_PEERS_PATH)
    excluded_peers_list = [entry['pubkey'] for entry in excluded_peers['EXCLUSION_LIST']]

    exclude_from = set(regolancer_config.get("exclude_from", []))
    to = set(regolancer_config.get("to", []))
    updated_exclude_from = exclude_from.copy()
    updated_to = to.copy()

    for channel in channels_data:
        chan_id, pubkey, tag = channel

        if pubkey in excluded_peers_list:
            print(f"Channel {chan_id} is in the exclusion list of pubkeys, skipping...")
            continue

        if tag in ['new_channel', 'sink']:
            if chan_id not in updated_exclude_from:
                updated_exclude_from.add(chan_id)
                print(f"Channel {chan_id} with tag '{tag}' added to 'exclude_from'.")
            if chan_id not in updated_to:
                updated_to.add(chan_id)
                print(f"Channel {chan_id} with tag '{tag}' added to 'to'.")

        if tag == 'source':
            if chan_id in updated_exclude_from:
                updated_exclude_from.remove(chan_id)
                print(f"Channel {chan_id} with tag 'source' was removed from 'exclude_from'.")
            if chan_id in updated_to:
                updated_to.remove(chan_id)
                print(f"Channel {chan_id} with tag 'source' was removed from 'to'.")

    exclude_from_changed = has_list_changed(exclude_from, updated_exclude_from)
    to_changed = has_list_changed(to, updated_to)

    if exclude_from_changed or to_changed:
        regolancer_config['exclude_from'] = list(updated_exclude_from)
        regolancer_config['to'] = list(updated_to)

        save_json(REGOLANCER_JSON_PATH, regolancer_config)
        print("Configuration updated successfully.")
        restart_service(SERVICE_NAME)
    else:
        print("No changes detected. Service will not be restarted.")

if __name__ == "__main__":
    main()