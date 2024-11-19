#!/usr/bin/env python3

import time
import logging
import configparser
import threading
import os
import sys

from logging.handlers import RotatingFileHandler

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, 'logs')
os.makedirs(logs_dir, exist_ok=True)

log_file_path = os.path.join(logs_dir, "automator.log")
max_log_size = 15 * 1024 * 1024
backup_count = 3

handler = RotatingFileHandler(
    log_file_path, maxBytes=max_log_size, backupCount=backup_count
)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO, handlers=[handler])
logging.info("Logging configured with rotation and ready to use.")

config_path = os.path.join(script_dir, 'automator.conf')
config = configparser.ConfigParser()
config.read(config_path)

scripts_dir = os.path.join(script_dir, 'scripts')
sys.path.append(scripts_dir)

def get_absolute_path(path):
    if not os.path.isabs(path):
        return os.path.normpath(os.path.join(script_dir, path))
    else:
        return os.path.normpath(path)

SLEEP_GET_CHANNELS = int(config.get('Automation', 'sleep_get_channels'))
SLEEP_AUTOFEE = int(config.get('Automation', 'sleep_autofee'))
SLEEP_GET_CLOSED_CHANNELS = int(config.get('Automation', 'sleep_get_closed_channels'))
SLEEP_REBALANCER = int(config.get('Automation', 'sleep_rebalancer'))
SLEEP_CLOSECHANNEL = int(config.get('Automation', 'sleep_closechannel'))
SLEEP_MAGMAFLOW = int(config.get('Automation', 'sleep_magmaflow'))

GET_CHANNELS_SCRIPT = get_absolute_path(config.get('Paths', 'get_channels_script'))
AUTO_FEE_SCRIPT = get_absolute_path(config.get('Paths', 'autofee_script'))
AUTO_FEE_V2_SCRIPT = get_absolute_path(config.get('Paths', 'autofee_script_v2'))
GET_CLOSED_CHANNELS_SCRIPT = get_absolute_path(config.get('Paths', 'get_closed_channels_script'))
REBALANCER_SCRIPT = get_absolute_path(config.get('Paths', 'rebalancer_script'))
CLOSE_CHANNEL_SCRIPT = get_absolute_path(config.get('Paths', 'close_channel_script'))
SWAP_OUT_SCRIPT = get_absolute_path(config.get('Paths', 'swap_out_script'))
MAGMAFLOW_SCRIPT = get_absolute_path(config.get('Paths', 'magmaflow_script'))

ENABLE_AUTOFEE = config.getboolean('Control', 'enable_autofee')
ENABLE_AUTOFEE_V2 = config.getboolean('Control', 'enable_autofee_v2')
ENABLE_GET_CLOSED_CHANNELS = config.getboolean('Control', 'enable_get_closed_channels')
ENABLE_REBALANCER = config.getboolean('Control', 'enable_rebalancer')
ENABLE_CLOSE_CHANNEL = config.getboolean('Control', 'enable_close_channel')
ENABLE_SWAP_OUT = config.getboolean('Control', 'enable_swap_out')
ENABLE_MAGMAFLOW = config.getboolean('Control', 'enable_magmaflow')

db_lock = threading.Lock()

def import_main_function(script_path):
    try:
        module_name = os.path.splitext(os.path.basename(script_path))[0]
        module = __import__(module_name)
        return module.main
    except Exception as e:
        logging.error(f"Error importing 'main' function from {script_path}: {e}")
        raise

def run_script_independently(main_function, sleep_time, script):
    while True:
        try:
            with db_lock:
                logging.info(f"Running {main_function.__name__} from {script}")
                main_function()
                logging.info(f"{main_function.__name__} executed successfully")
        except Exception as e:
            logging.error(f"Error executing {main_function.__name__}: {e}")
        time.sleep(sleep_time)

def run_swap_out(swap_out_main):
    try:
        logging.info(f"Running {swap_out_main.__name__}")
        swap_out_main()
        logging.info(f"{swap_out_main.__name__} executed successfully")
    except Exception as e:
        logging.error(f"Error executing {swap_out_main.__name__}: {e}")

def main():
    threads = []

    try:
        logging.info("Starting get_channels")
        get_channels_main = import_main_function(GET_CHANNELS_SCRIPT)
        thread1 = threading.Thread(target=run_script_independently, args=(get_channels_main, SLEEP_GET_CHANNELS, GET_CHANNELS_SCRIPT))
        threads.append(thread1)
        thread1.start()

        if ENABLE_AUTOFEE:
            logging.info("Starting autofee")
            autofee_main = import_main_function(AUTO_FEE_SCRIPT)
            thread2 = threading.Thread(target=run_script_independently, args=(autofee_main, SLEEP_AUTOFEE, AUTO_FEE_SCRIPT))
            threads.append(thread2)
            thread2.start()
        
        if ENABLE_AUTOFEE_V2:
            logging.info("Starting autofee_v2")
            autofee_main = import_main_function(AUTO_FEE_V2_SCRIPT)
            thread2 = threading.Thread(target=run_script_independently, args=(autofee_main, SLEEP_AUTOFEE, AUTO_FEE_V2_SCRIPT))
            threads.append(thread2)
            thread2.start()

        if ENABLE_GET_CLOSED_CHANNELS:
            logging.info("Starting get_closed_channels")
            get_closed_channels_main = import_main_function(GET_CLOSED_CHANNELS_SCRIPT)
            thread3 = threading.Thread(target=run_script_independently, args=(get_closed_channels_main, SLEEP_GET_CLOSED_CHANNELS, GET_CLOSED_CHANNELS_SCRIPT))
            threads.append(thread3)
            thread3.start()

        if ENABLE_REBALANCER:
            logging.info("Starting rebalancer")
            rebalancer_main = import_main_function(REBALANCER_SCRIPT)
            thread4 = threading.Thread(target=run_script_independently, args=(rebalancer_main, SLEEP_REBALANCER, REBALANCER_SCRIPT))
            threads.append(thread4)
            thread4.start()

        if ENABLE_CLOSE_CHANNEL:
            logging.info("Starting close_channel")
            close_channel_main = import_main_function(CLOSE_CHANNEL_SCRIPT)
            thread5 = threading.Thread(target=run_script_independently, args=(close_channel_main, SLEEP_CLOSECHANNEL, CLOSE_CHANNEL_SCRIPT))
            threads.append(thread5)
            thread5.start()

        if ENABLE_SWAP_OUT:
            logging.info("Starting swap_out")
            swap_out_main = import_main_function(SWAP_OUT_SCRIPT)
            thread6 = threading.Thread(target=run_swap_out, args=(swap_out_main,))
            threads.append(thread6)
            thread6.start()
        
        if ENABLE_MAGMAFLOW:
            logging.info("Starting magmaflow")
            magmaflow_main = import_main_function(MAGMAFLOW_SCRIPT)
            thread7 = threading.Thread(target=run_script_independently, args=(magmaflow_main, SLEEP_MAGMAFLOW, MAGMAFLOW_SCRIPT))
            threads.append(thread7)
            thread7.start()

        for thread in threads:
            thread.join()

    except Exception as e:
        logging.error(f"Unexpected error in main controller: {e}")
        raise

if __name__ == "__main__":
    logging.info("Starting the automator")
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Automator manually interrupted")
    except Exception as e:
        logging.error(f"Unexpected error in automator: {e}")
    logging.info("Automator finished")
