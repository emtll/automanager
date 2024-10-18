import sqlite3
import requests
import os
import configparser

from datetime import datetime, timezone

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'general.conf'))
config = configparser.ConfigParser()
config.read(config_file_path)

def expand_path(path):
    if not os.path.isabs(path):
        return os.path.join(os.path.expanduser("~"), path)
    return os.path.expanduser(path)

LNDG_DB_PATH = expand_path(config['Paths']['lndg_db_path'])
DB_PATH = expand_path(config['Paths']['db_path'])
MEMPOOL_API_URL_BASE = config['API']['mempool_api_url_base']

def connect_db():
    return sqlite3.connect(LNDG_DB_PATH, timeout=30)

def connect_new_db():
    return sqlite3.connect(DB_PATH, timeout=30)

def create_closed_channels_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS closed_channels (
        chan_id INTEGER PRIMARY KEY,
        pubkey TEXT,
        alias TEXT,
        opening_date TEXT,
        closure_date TEXT,
        total_routed_out INTEGER,
        total_routed_in INTEGER,
        total_rebalanced_in INTEGER,
        total_revenue INTEGER,
        revenue_ppm INTEGER,
        total_cost INTEGER,
        cost_ppm INTEGER,
        profit INTEGER,
        profit_ppm INTEGER,
        profit_margin REAL,
        assisted_revenue INTEGER,
        assisted_revenue_ppm INTEGER,
        days_open INTEGER,
        sats_per_day_profit INTEGER,
        sats_per_day_assisted INTEGER,
        apy REAL,
        iapy REAL,
        tag TEXT
    )
    """)
    conn.commit()

def get_closed_channels(conn):
    query = """
    SELECT c.chan_id, c.remote_pubkey, c.capacity, c.local_balance, c.alias, cl.closing_tx, cl.funding_txid
    FROM gui_channels c
    LEFT JOIN gui_closures cl ON c.chan_id = cl.chan_id
    WHERE c.is_open = 0;
    """
    return conn.execute(query).fetchall()

def calculate_ppm(total_cost, total_in):
    if total_in > 0:
        return int(total_cost / (total_in / 1_000_000))
    else:
        return 0

def calculate_profit(total_revenue, total_cost):
    total_revenue = total_revenue or 0
    total_cost = total_cost or 0
    return total_revenue - total_cost

def calculate_profit_ppm(profit, total_routed_out):
    if total_routed_out > 0:
        return int(profit / (total_routed_out / 1_000_000))
    else:
        return 0

def calculate_profit_margin(profit, total_routed_out):
    if total_routed_out > 0:
        return round((profit / total_routed_out) * 100, 2)
    else:
        return 0

def calculate_assisted_revenue_ppm(assisted_revenue, total_routed_in):
    if total_routed_in > 0:
        return int(assisted_revenue / (total_routed_in / 1_000_000))
    else:
        return 0

def calculate_apy(profit, total_routed_out, days_open):
    if total_routed_out > 0 and days_open > 0:
        return round((profit / total_routed_out) * (365 / days_open) * 100, 2)
    else:
        return 0

def calculate_iapy(assisted_revenue, total_routed_in, days_open):
    if total_routed_in > 0 and days_open > 0:
        return round((assisted_revenue / total_routed_in) * (365 / days_open) * 100, 2)
    else:
        return 0

def calculate_profit_per_day(profit, days_open):
    if days_open > 0:
        return int(profit / days_open)
    else:
        return 0

def get_tx_date(txid):
    if txid:
        try:
            response = requests.get(f"{MEMPOOL_API_URL_BASE}/{txid}")
            if response.status_code == 200:
                tx_data = response.json()
                block_time = tx_data.get('status', {}).get('block_time')
                if block_time:
                    return datetime.fromtimestamp(block_time, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            else:
                print(f"Error fetching transaction {txid}: {response.status_code}")
        except Exception as e:
            print(f"Error querying Mempool API: {str(e)}")
    return None

def tag(total_routed_in, total_routed_out, days_open):
    if total_routed_in == 0 and total_routed_out == 0 and days_open < 7:
        return 'new_channel'
    elif total_routed_in > (total_routed_out * 2):
        return 'source'
    elif total_routed_out > (total_routed_in * 2):
        return 'sink'
    return 'router'

def update_closed_channels_db(conn_lndg, conn_new, closed_channels):
    cursor_lndg = conn_lndg.cursor()
    cursor_new = conn_new.cursor()

    for channel in closed_channels:
        chan_id = channel[0]
        pubkey = channel[1]
        alias = channel[4] or "Unknown"
        closing_tx = channel[5]
        funding_txid = channel[6]

        total_cost_result = cursor_lndg.execute("SELECT SUM(fee) FROM gui_payments WHERE rebal_chan = ?", (chan_id,)).fetchone()
        total_cost = total_cost_result[0] if total_cost_result and total_cost_result[0] is not None else 0

        total_routed_in_result = cursor_lndg.execute("SELECT SUM(amt_in_msat) / 1000 FROM gui_forwards WHERE chan_id_in = ?", (chan_id,)).fetchone()
        total_routed_in = total_routed_in_result[0] if total_routed_in_result and total_routed_in_result[0] is not None else 0

        total_rebalanced_in_result = cursor_lndg.execute("SELECT SUM(value) FROM gui_payments WHERE rebal_chan = ?", (chan_id,)).fetchone()
        total_rebalanced_in = total_rebalanced_in_result[0] if total_rebalanced_in_result and total_rebalanced_in_result[0] is not None else 0

        total_routed_out_result = cursor_lndg.execute("SELECT SUM(amt_out_msat) / 1000, SUM(fee) FROM gui_forwards WHERE chan_id_out = ?", (chan_id,)).fetchone()
        if total_routed_out_result:
            total_routed_out = total_routed_out_result[0] if total_routed_out_result[0] is not None else 0
            total_revenue = total_routed_out_result[1] if total_routed_out_result[1] is not None else 0
        else:
            total_routed_out = 0
            total_revenue = 0

        assisted_revenue_result = cursor_lndg.execute("SELECT SUM(fee) FROM gui_forwards WHERE chan_id_in = ?", (chan_id,)).fetchone()
        assisted_revenue = assisted_revenue_result[0] if assisted_revenue_result and assisted_revenue_result[0] is not None else 0

        total_cost = float(total_cost)
        total_routed_in = float(total_routed_in)
        total_rebalanced_in = float(total_rebalanced_in)
        total_routed_out = float(total_routed_out)
        total_revenue = float(total_revenue)
        assisted_revenue = float(assisted_revenue)

        total_in = total_rebalanced_in + total_routed_in
        cost_ppm = calculate_ppm(total_cost, total_in)
        revenue_ppm = calculate_ppm(total_revenue, total_routed_out)
        profit = calculate_profit(total_revenue, total_cost)
        profit_ppm = calculate_profit_ppm(profit, total_routed_out)
        profit_margin = calculate_profit_margin(profit, total_routed_out)
        assisted_revenue_ppm = calculate_assisted_revenue_ppm(assisted_revenue, total_routed_in)

        closure_date = get_tx_date(closing_tx)
        opening_date = get_tx_date(funding_txid)
        if closure_date and opening_date:
            days_open = (datetime.strptime(closure_date, '%Y-%m-%d %H:%M:%S') - datetime.strptime(opening_date, '%Y-%m-%d %H:%M:%S')).days
            days_open = max(days_open, 1)
        else:
            days_open = 1

        apy = calculate_apy(profit, total_routed_out, days_open)
        iapy = calculate_iapy(assisted_revenue, total_routed_in, days_open)

        sats_per_day_profit = int(profit / days_open) if days_open > 0 else 0
        sats_per_day_assisted = int(assisted_revenue / days_open) if days_open > 0 else 0

        profit_per_day = calculate_profit_per_day(profit, days_open)

        channel_tag = tag(total_routed_in, total_routed_out, days_open)

        total_revenue = int(total_revenue)
        total_cost = int(total_cost)
        profit = int(profit)
        assisted_revenue = int(assisted_revenue)
        total_routed_in = int(total_routed_in)
        total_rebalanced_in = int(total_rebalanced_in)
        total_routed_out = int(total_routed_out)
        profit_per_day = int(profit_per_day)

        cursor_new.execute("""
            INSERT OR REPLACE INTO closed_channels
            (chan_id, pubkey, alias, opening_date, closure_date, total_routed_out, total_routed_in, total_rebalanced_in,
             total_revenue, revenue_ppm, total_cost, cost_ppm, profit, profit_ppm,
             profit_margin, assisted_revenue, assisted_revenue_ppm, days_open,
             sats_per_day_profit, sats_per_day_assisted, apy, iapy, tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (chan_id, pubkey, alias, opening_date, closure_date, total_routed_out, total_routed_in, total_rebalanced_in, 
              total_revenue, revenue_ppm, total_cost, cost_ppm, profit, profit_ppm,
              profit_margin, assisted_revenue, assisted_revenue_ppm, days_open,
              sats_per_day_profit, sats_per_day_assisted, apy, iapy, channel_tag))

    conn_new.commit()

def main():
    conn_new = connect_new_db()
    create_closed_channels_table(conn_new)
    conn_lndg = connect_db()
    closed_channels = get_closed_channels(conn_lndg)
    update_closed_channels_db(conn_lndg, conn_new, closed_channels)
    print("Closed channels updated in the new database.")
    conn_lndg.close()
    conn_new.close()

if __name__ == "__main__":
    main()
