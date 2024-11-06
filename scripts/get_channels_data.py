import sqlite3
import json
import os
import requests
import configparser
from datetime import datetime, timedelta, timezone

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'automator.conf'))
config = configparser.ConfigParser()
config.read(config_file_path)

def expand_path(path):
    if not os.path.isabs(path):
        return os.path.join(os.path.expanduser("~"), path)
    return os.path.expanduser(path)

LNDG_DB_PATH = expand_path(config['Paths']['lndg_db_path'])
DB_PATH = expand_path(config['Paths']['db_path'])
PERIOD = int(config['Get_channels_data']['period'])
ROUTER_FACTOR = float(config['Get_channels_data']['router_factor'])
MEMPOOL_API_URL_BASE = config['API']['mempool_api_url_base']

def connect_db():
    conn = sqlite3.connect(LNDG_DB_PATH, timeout=30)
    return conn

def connect_new_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    return conn

def create_personalized_table(conn, PERIOD):
    cursor = conn.cursor()
    
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS opened_channels_{PERIOD}d (
        chan_id INTEGER PRIMARY KEY,
        pubkey TEXT,
        alias TEXT,
        opening_date TEXT,
        tag TEXT,
        capacity INTEGER,
        outbound_liquidity REAL,
        inbound_liquidity REAL,
        days_open INTEGER,
        total_revenue INTEGER,
        revenue_ppm INTEGER,
        total_cost INTEGER,
        cost_ppm INTEGER,
        rebal_rate INTEGER,
        total_rebalanced_in INTEGER,
        total_routed_out INTEGER,
        total_routed_in INTEGER,
        assisted_revenue INTEGER,
        assisted_revenue_ppm INTEGER,
        profit INTEGER,
        profit_ppm INTEGER,
        profit_margin REAL,
        sats_per_day_profit INTEGER,
        sats_per_day_assisted INTEGER,
        apy REAL,
        iapy REAL,
        local_fee_rate INTEGER,
        local_base_fee INTEGER,
        remote_fee_rate INTEGER,
        remote_base_fee INTEGER,
        local_inbound_fee_rate INTEGER,
        local_inbound_base_fee INTEGER,
        last_outgoing_activity TEXT,
        last_incoming_activity TEXT,
        last_rebalance TEXT
    )
    """)
    conn.commit()

def create_tables(conn):
    cursor = conn.cursor()

    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS opened_channels_1d (
        chan_id INTEGER PRIMARY KEY,
        pubkey TEXT,
        alias TEXT,
        opening_date TEXT,
        tag TEXT,
        capacity INTEGER,
        outbound_liquidity REAL,
        inbound_liquidity REAL,
        days_open INTEGER,
        total_revenue INTEGER,
        revenue_ppm INTEGER,
        total_cost INTEGER,
        cost_ppm INTEGER,
        rebal_rate INTEGER,
        total_rebalanced_in INTEGER,
        total_routed_out INTEGER,
        total_routed_in INTEGER,
        assisted_revenue INTEGER,
        assisted_revenue_ppm INTEGER,
        profit INTEGER,
        profit_ppm INTEGER,
        profit_margin REAL,
        sats_per_day_profit INTEGER,
        sats_per_day_assisted INTEGER,
        apy REAL,
        iapy REAL,
        local_fee_rate INTEGER,
        local_base_fee INTEGER,
        remote_fee_rate INTEGER,
        remote_base_fee INTEGER,
        local_inbound_fee_rate INTEGER,
        local_inbound_base_fee INTEGER,
        last_outgoing_activity TEXT,
        last_incoming_activity TEXT,
        last_rebalance TEXT
    )
    """)

    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS opened_channels_7d (
        chan_id INTEGER PRIMARY KEY,
        pubkey TEXT,
        alias TEXT,
        opening_date TEXT,
        tag TEXT,
        capacity INTEGER,
        outbound_liquidity REAL,
        inbound_liquidity REAL,
        days_open INTEGER,
        total_revenue INTEGER,
        revenue_ppm INTEGER,
        total_cost INTEGER,
        cost_ppm INTEGER,
        rebal_rate INTEGER,
        total_rebalanced_in INTEGER,
        total_routed_out INTEGER,
        total_routed_in INTEGER,
        assisted_revenue INTEGER,
        assisted_revenue_ppm INTEGER,
        profit INTEGER,
        profit_ppm INTEGER,
        profit_margin REAL,
        sats_per_day_profit INTEGER,
        sats_per_day_assisted INTEGER,
        apy REAL,
        iapy REAL,
        local_fee_rate INTEGER,
        local_base_fee INTEGER,
        remote_fee_rate INTEGER,
        remote_base_fee INTEGER,
        local_inbound_fee_rate INTEGER,
        local_inbound_base_fee INTEGER,
        last_outgoing_activity TEXT,
        last_incoming_activity TEXT,
        last_rebalance TEXT
    )
    """)

    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS opened_channels_30d (
        chan_id INTEGER PRIMARY KEY,
        pubkey TEXT,
        alias TEXT,
        opening_date TEXT,
        tag TEXT,
        capacity INTEGER,
        outbound_liquidity REAL,
        inbound_liquidity REAL,
        days_open INTEGER,
        total_revenue INTEGER,
        revenue_ppm INTEGER,
        total_cost INTEGER,
        cost_ppm INTEGER,
        rebal_rate INTEGER,
        total_rebalanced_in INTEGER,
        total_routed_out INTEGER,
        total_routed_in INTEGER,
        assisted_revenue INTEGER,
        assisted_revenue_ppm INTEGER,
        profit INTEGER,
        profit_ppm INTEGER,
        profit_margin REAL,
        sats_per_day_profit INTEGER,
        sats_per_day_assisted INTEGER,
        apy REAL,
        iapy REAL,
        local_fee_rate INTEGER,
        local_base_fee INTEGER,
        remote_fee_rate INTEGER,
        remote_base_fee INTEGER,
        local_inbound_fee_rate INTEGER,
        local_inbound_base_fee INTEGER,
        last_outgoing_activity TEXT,
        last_incoming_activity TEXT,
        last_rebalance TEXT
    )
    """)

    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS opened_channels_lifetime (
        chan_id INTEGER PRIMARY KEY,
        pubkey TEXT,
        alias TEXT,
        opening_date TEXT,
        tag TEXT,
        capacity INTEGER,
        outbound_liquidity REAL,
        inbound_liquidity REAL,
        days_open INTEGER,
        total_revenue INTEGER,
        revenue_ppm INTEGER,
        total_cost INTEGER,
        cost_ppm INTEGER,
        rebal_rate INTEGER,
        total_rebalanced_in INTEGER,
        total_routed_out INTEGER,
        total_routed_in INTEGER,
        assisted_revenue INTEGER,
        assisted_revenue_ppm INTEGER,
        profit INTEGER,
        profit_ppm INTEGER,
        profit_margin REAL,
        sats_per_day_profit INTEGER,
        sats_per_day_assisted INTEGER,
        apy REAL,
        iapy REAL,
        local_fee_rate INTEGER,
        local_base_fee INTEGER,
        remote_fee_rate INTEGER,
        remote_base_fee INTEGER,
        local_inbound_fee_rate INTEGER,
        local_inbound_base_fee INTEGER,
        last_outgoing_activity TEXT,
        last_incoming_activity TEXT,
        last_rebalance TEXT
    )
    """)
    
    conn.commit()

def upsert_channel_data(conn, data, table):
    cursor = conn.cursor()
    
    cursor.execute(f"""
    INSERT INTO {table} (
        chan_id, pubkey, alias, opening_date, tag, capacity, outbound_liquidity, inbound_liquidity, days_open, 
        total_revenue, revenue_ppm, total_cost, cost_ppm, rebal_rate, total_rebalanced_in, total_routed_out, total_routed_in, 
        assisted_revenue, assisted_revenue_ppm, profit, profit_ppm, profit_margin, sats_per_day_profit, sats_per_day_assisted, 
        apy, iapy, local_fee_rate, local_base_fee, remote_fee_rate, remote_base_fee, 
        local_inbound_fee_rate, local_inbound_base_fee,  -- Novas colunas
        last_outgoing_activity, last_incoming_activity, last_rebalance
    ) 
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(chan_id) DO UPDATE SET
        pubkey=excluded.pubkey,
        alias=excluded.alias,
        opening_date=excluded.opening_date,
        tag=excluded.tag,
        capacity=excluded.capacity,
        outbound_liquidity=excluded.outbound_liquidity,
        inbound_liquidity=excluded.inbound_liquidity,
        days_open=excluded.days_open,
        total_revenue=excluded.total_revenue,
        revenue_ppm=excluded.revenue_ppm,
        total_cost=excluded.total_cost,
        cost_ppm=excluded.cost_ppm,
        rebal_rate=excluded.rebal_rate,
        total_rebalanced_in=excluded.total_rebalanced_in,
        total_routed_out=excluded.total_routed_out,
        total_routed_in=excluded.total_routed_in,
        assisted_revenue=excluded.assisted_revenue,
        assisted_revenue_ppm=excluded.assisted_revenue_ppm,
        profit=excluded.profit,
        profit_ppm=excluded.profit_ppm,
        profit_margin=excluded.profit_margin,
        sats_per_day_profit=excluded.sats_per_day_profit,
        sats_per_day_assisted=excluded.sats_per_day_assisted,
        apy=excluded.apy,
        iapy=excluded.iapy,
        local_fee_rate=excluded.local_fee_rate,
        local_base_fee=excluded.local_base_fee,
        remote_fee_rate=excluded.remote_fee_rate,
        remote_base_fee=excluded.remote_base_fee,
        local_inbound_fee_rate=excluded.local_inbound_fee_rate,  -- Atualização
        local_inbound_base_fee=excluded.local_inbound_base_fee,  -- Atualização
        last_outgoing_activity=excluded.last_outgoing_activity,
        last_incoming_activity=excluded.last_incoming_activity,
        last_rebalance=excluded.last_rebalance
    """, data)
    conn.commit()

def calculate_ppm(total_cost, total_in):
    if total_in > 0:
        return int(total_cost / (total_in / 1_000_000))
    return 0

def calculate_rebal_rate(total_cost, total_rebalanced_in):
    if total_rebalanced_in > 0:
        return int((total_cost / total_rebalanced_in) * 1_000_000)
    return 0

def calculate_profit(total_revenue, total_cost):
    return total_revenue - total_cost

def calculate_profit_ppm(total_profit, total_routed_out):
    if total_routed_out > 0:
        return int(total_profit / (total_routed_out / 1_000_000))
    return 0

def calculate_profit_margin(total_profit, total_routed_out):
    if total_routed_out > 0:
        return (total_profit / total_routed_out) * 100  
    return 0

def calculate_apy(profit, total_routed_out, period, days_open):
    if total_routed_out > 0 and days_open > 0:
        apy = (profit / total_routed_out) * (365 / min(days_open, period)) * 100
        return round(apy, 3)
    return 0

def calculate_iapy(assisted_revenue, total_routed_in, period, days_open):
    if total_routed_in > 0 and days_open > 0:
        iapy = (assisted_revenue / total_routed_in) * (365 / min(days_open, period)) * 100
        return round(iapy, 3)
    return 0

def calculate_assisted_revenue_ppm(assisted_revenue, total_routed_in):
    if total_routed_in > 0:
        return int(assisted_revenue / (total_routed_in / 1_000_000))
    return 0

def calculate_sats_per_day(amount, days_open):
    if days_open > 0:
        return int(amount / days_open)
    return 0

def calculate_outbound_liquidity(local_balance, capacity):
    if capacity > 0:
        return round((local_balance / capacity) * 100, 1)  
    return 0

def calculate_inbound_liquidity(local_balance, capacity):
    remote_balance = capacity - local_balance
    if capacity > 0:
        return round((remote_balance / capacity) * 100, 1)  
    return 0

def get_lifetime_data(conn, chan_id):
    query = """
    SELECT total_routed_in, total_routed_out, days_open
    FROM opened_channels_lifetime
    WHERE chan_id = ?;
    """
    result = conn.execute(query, (chan_id,)).fetchone()
    if result:
        total_routed_in, total_routed_out, days_open = result
        return total_routed_in, total_routed_out, days_open
    return None, None, None

def tag(conn, chan_id, total_routed_in, total_routed_out, days_open):
    lifetime_routed_in, lifetime_routed_out, lifetime_days_open = get_lifetime_data(conn, chan_id)

    if lifetime_routed_in is not None and lifetime_routed_out is not None:
        total_routed_in = lifetime_routed_in
        total_routed_out = lifetime_routed_out
        days_open = lifetime_days_open

    if total_routed_in == 0 and total_routed_out == 0 and days_open < 7:
        return 'new_channel'
    elif total_routed_in > (total_routed_out * ROUTER_FACTOR) and days_open > 7:
        return 'source'
    elif total_routed_out > (total_routed_in * ROUTER_FACTOR) and days_open > 7:
        return 'sink'
    elif days_open > 7:
        return 'router'

def get_active_channels(conn):
    query = """
    SELECT chan_id, remote_pubkey, capacity, local_balance, unsettled_balance, alias, local_fee_rate, local_base_fee, 
           remote_fee_rate, remote_base_fee, local_inbound_fee_rate, local_inbound_base_fee, funding_txid
    FROM gui_channels 
    WHERE is_open = 1;
    """
    return conn.execute(query).fetchall()

def remove_closed_channels(conn, active_chan_ids, table):
    cursor = conn.cursor()

    placeholders = ', '.join('?' for _ in active_chan_ids)

    if active_chan_ids:
        cursor.execute(f""" 
        DELETE FROM {table}
        WHERE chan_id NOT IN ({placeholders})
        """, active_chan_ids)
    else:
        cursor.execute(f"DELETE FROM {table}")
    
    conn.commit()

def get_opening_date(funding_txid):
    if funding_txid:
        MEMPOOL_API_URL = f"https://mempool.space/api/tx/{funding_txid}"
        try:
            response = requests.get(MEMPOOL_API_URL)
            if response.status_code == 200:
                tx_data = response.json()
                block_time = tx_data.get('status', {}).get('block_time')
                if block_time:
                    return datetime.fromtimestamp(block_time, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"Error while fetching transaction {funding_txid}: {str(e)}")
    return None

def calculate_days_open(opening_date):
    if opening_date:
        opening_date_obj = datetime.strptime(opening_date, '%Y-%m-%d %H:%M:%S')
        current_date = datetime.now()
        days_open = (current_date - opening_date_obj).days
        return days_open
    return 0

def get_last_outgoing_activity(conn, chan_id):
    query = """
    SELECT MAX(forward_date) 
    FROM gui_forwards 
    WHERE chan_id_out = ?;
    """
    result = conn.execute(query, (chan_id,)).fetchone()
    return result[0] if result[0] else None

def get_last_incoming_activity(conn, chan_id):
    query = """
    SELECT MAX(forward_date) 
    FROM gui_forwards 
    WHERE chan_id_in = ?;
    """
    result = conn.execute(query, (chan_id,)).fetchone()
    return result[0] if result[0] else None

def get_last_rebalance(conn, chan_id):
    query = """
    SELECT MAX(creation_date)
    FROM gui_payments
    WHERE rebal_chan = ?
    AND chan_out IS NOT NULL;
    """
    result = conn.execute(query, (chan_id,)).fetchone()
    return result[0] if result[0] else None

def get_rebalances(conn, start_date):
    query = """
    SELECT rebal_chan, SUM(fee) as total_cost
    FROM gui_payments
    WHERE rebal_chan IS NOT NULL
    AND chan_out IS NOT NULL
    AND creation_date >= ?
    GROUP BY rebal_chan;
    """
    return conn.execute(query, (start_date,)).fetchall()

def get_routed_in(conn, start_date):
    query = """
    SELECT chan_id_in, SUM(amt_in_msat) / 1000 as total_routed_in
    FROM gui_forwards
    WHERE chan_id_in IS NOT NULL
    AND forward_date >= ?
    GROUP BY chan_id_in;
    """
    return conn.execute(query, (start_date,)).fetchall()

def get_rebalanced_in(conn, start_date):
    query = """
    SELECT rebal_chan, SUM(value) as total_rebalanced_in
    FROM gui_payments
    WHERE rebal_chan IS NOT NULL
    AND chan_out IS NOT NULL
    AND creation_date >= ?
    GROUP BY rebal_chan;
    """
    return conn.execute(query, (start_date,)).fetchall()

def get_routed_out_and_revenue(conn, start_date):
    query = """
    SELECT chan_id_out, SUM(amt_out_msat) / 1000 as total_routed_out, SUM(fee) as total_revenue
    FROM gui_forwards
    WHERE chan_id_out IS NOT NULL
    AND forward_date >= ?
    GROUP BY chan_id_out;
    """
    return conn.execute(query, (start_date,)).fetchall()

def get_assisted_revenue(conn, start_date):
    query = """
    SELECT chan_id_in, SUM(fee) as total_assisted_revenue
    FROM gui_forwards
    WHERE chan_id_in IS NOT NULL
    AND forward_date >= ?
    GROUP BY chan_id_in;
    """
    return conn.execute(query, (start_date,)).fetchall()

def main():
    current_date = datetime.now()
    start_date_period = (current_date - timedelta(days=PERIOD)).strftime('%Y-%m-%d %H:%M:%S')
    start_date_1d = (current_date - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    start_date_7d = (current_date - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    start_date_30d = (current_date - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    start_date_lifetime = "1970-01-01 00:00:00"
    
    conn = connect_db()
    new_conn = connect_new_db()
    if PERIOD not in [1, 7, 30]:
        create_personalized_table(new_conn, PERIOD)
    create_tables(new_conn)
    
    active_channels = get_active_channels(conn)
    active_chan_ids = [channel[0] for channel in active_channels]

    periods = {
        f'opened_channels_{PERIOD}d': start_date_period if PERIOD not in [1, 7, 30] else None,
        'opened_channels_1d': start_date_1d,
        'opened_channels_7d': start_date_7d,
        'opened_channels_30d': start_date_30d,
        'opened_channels_lifetime': start_date_lifetime
    }

    periods = {k: v for k, v in periods.items() if v is not None}
    
    for table_name in periods.keys():
        remove_closed_channels(new_conn, active_chan_ids, table_name)
    
    for table_name, start_date in periods.items():
        rebalances = get_rebalances(conn, start_date)
        routed_in = get_routed_in(conn, start_date)
        rebalanced_in = get_rebalanced_in(conn, start_date)
        routed_out_revenue = get_routed_out_and_revenue(conn, start_date)
        assisted_revenue_dict = {row[0]: row[1] for row in get_assisted_revenue(conn, start_date)}

        rebalances_dict = {row[0]: row[1] for row in rebalances}
        routed_in_dict = {row[0]: row[1] for row in routed_in}
        rebalanced_in_dict = {row[0]: row[1] for row in rebalanced_in}
        routed_out_dict = {row[0]: row[1] for row in routed_out_revenue}
        revenue_dict = {row[0]: row[2] for row in routed_out_revenue}

        for channel in active_channels:
            chan_id = channel[0]
            pubkey = channel[1]
            alias = channel[5] or "Unknown"
            local_fee_rate = channel[6]
            local_base_fee = channel[7]
            remote_fee_rate = channel[8]
            remote_base_fee = channel[9]
            local_inbound_fee_rate = channel[10]
            local_inbound_base_fee = channel[11]
            funding_txid = channel[12]

            total_cost = int(rebalances_dict.get(chan_id, 0))
            total_rebalanced_in = int(rebalanced_in_dict.get(chan_id, 0))
            total_routed_in = int(routed_in_dict.get(chan_id, 0))
            total_routed_out = int(routed_out_dict.get(chan_id, 0))
            total_revenue = int(revenue_dict.get(chan_id, 0))
            assisted_revenue = int(assisted_revenue_dict.get(chan_id, 0))

            ppm = calculate_ppm(total_cost, total_rebalanced_in + total_routed_in)
            revenue_ppm = calculate_ppm(total_revenue, total_routed_out)
            assisted_revenue_ppm = calculate_assisted_revenue_ppm(assisted_revenue, total_routed_in)

            profit = calculate_profit(total_revenue, total_cost)
            profit_ppm = calculate_profit_ppm(profit, total_routed_out)
            profit_margin = round(calculate_profit_margin(profit, total_routed_out), 3)

            rebal_rate = calculate_rebal_rate(total_cost, total_rebalanced_in)

            opening_date = get_opening_date(funding_txid)
            days_open = calculate_days_open(opening_date)

            apy = calculate_apy(profit, total_routed_out, PERIOD, days_open)
            iapy = calculate_iapy(assisted_revenue, total_routed_in, PERIOD, days_open)

            sats_per_day_profit = calculate_sats_per_day(profit, days_open)
            sats_per_day_assisted = calculate_sats_per_day(assisted_revenue, days_open)

            last_outgoing_activity = get_last_outgoing_activity(conn, chan_id)
            last_incoming_activity = get_last_incoming_activity(conn, chan_id)
            last_rebalance = get_last_rebalance(conn, chan_id)

            capacity = channel[2]
            local_balance = channel[3]
            outbound_liquidity = calculate_outbound_liquidity(local_balance, capacity)
            inbound_liquidity = calculate_inbound_liquidity(local_balance, capacity)

            tag_value = tag(new_conn, chan_id, total_routed_in, total_routed_out, days_open)

            data = (
                chan_id, pubkey, alias, opening_date, tag_value, capacity, outbound_liquidity, inbound_liquidity,
                days_open, total_revenue, revenue_ppm, total_cost, ppm, rebal_rate, total_rebalanced_in, total_routed_out, total_routed_in, 
                assisted_revenue, assisted_revenue_ppm, profit, profit_ppm, profit_margin, sats_per_day_profit, 
                sats_per_day_assisted, apy, iapy, local_fee_rate, local_base_fee, remote_fee_rate, remote_base_fee, 
                local_inbound_fee_rate, local_inbound_base_fee,
                last_outgoing_activity, last_incoming_activity, last_rebalance
            )

            upsert_channel_data(new_conn, data, table_name)
            if PERIOD not in [1, 7, 30]:
                upsert_channel_data(new_conn, data, f"opened_channels_{PERIOD}d")

    conn.close()
    new_conn.close()

if __name__ == "__main__":
    main()
