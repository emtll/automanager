import subprocess
import time
import logging
import configparser
import threading

logging.basicConfig(
    filename="logs/automator-controller.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

config = configparser.ConfigParser()
config.read('general.conf')

SLEEP_GET_CHANNELS_AND_AUTOFEE = int(config.get('Automation', 'sleep_get_channels_and_autofee'))
SLEEP_GET_CLOSED_CHANNELS = int(config.get('Automation', 'sleep_get_closed_channels'))
SLEEP_REBALANCER = int(config.get('Automation', 'sleep_rebalancer'))

GET_CHANNELS_SCRIPT = config.get('Paths', 'get_channels_script')
AUTO_FEE_SCRIPT = config.get('Paths', 'autofee_script')
GET_CLOSED_CHANNELS_SCRIPT = config.get('Paths', 'get_closed_channels_script')
REBALANCER_SCRIPT = config.get('Paths', 'rebalancer_script')
CLOSE_CHANNEL_SCRIPT = config.get('Paths', 'close_channel_script')

ENABLE_GET_CHANNELS_AND_AUTOFEE = config.getboolean('Control', 'enable_get_channels_and_autofee')
ENABLE_GET_CLOSED_CHANNELS = config.getboolean('Control', 'enable_get_closed_channels')
ENABLE_REBALANCER = config.getboolean('Control', 'enable_rebalancer')
ENABLE_CLOSE_CHANNEL = config.getboolean('Control', 'enable_close_channel')

def run_script_independently(script_name, sleep_time):
    while True:
        try:
            logging.info(f"Executing {script_name}")
            subprocess.run(['python3', script_name], check=True)
            logging.info(f"{script_name} executed successfully.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error executing {script_name}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error executing {script_name}: {e}")
        time.sleep(sleep_time)

def run_close_channel():
    while True:
        try:
            logging.info(f"Executing {CLOSE_CHANNEL_SCRIPT}")
            subprocess.run(['python3', CLOSE_CHANNEL_SCRIPT], check=True)
            logging.info(f"{CLOSE_CHANNEL_SCRIPT} executed successfully.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error executing {CLOSE_CHANNEL_SCRIPT}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error executing {CLOSE_CHANNEL_SCRIPT}: {e}")

def run_get_channels_and_autofee():
    while True:
        try:
            logging.info(f"Executing {GET_CHANNELS_SCRIPT}")
            subprocess.run(['python3', GET_CHANNELS_SCRIPT], check=True)
            logging.info(f"{GET_CHANNELS_SCRIPT} executed successfully.")

            logging.info(f"Executing {AUTO_FEE_SCRIPT}")
            subprocess.run(['python3', AUTO_FEE_SCRIPT], check=True)
            logging.info(f"{AUTO_FEE_SCRIPT} executed successfully.")

        except subprocess.CalledProcessError as e:
            logging.error(f"Error executing {GET_CHANNELS_SCRIPT} or {AUTO_FEE_SCRIPT}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error executing {GET_CHANNELS_SCRIPT} or {AUTO_FEE_SCRIPT}: {e}")
        
        time.sleep(SLEEP_GET_CHANNELS_AND_AUTOFEE)

def main():
    threads = []

    if ENABLE_GET_CHANNELS_AND_AUTOFEE:
        thread1 = threading.Thread(target=run_get_channels_and_autofee)
        threads.append(thread1)
        thread1.start()

    if ENABLE_GET_CLOSED_CHANNELS:
        thread2 = threading.Thread(target=run_script_independently, args=(GET_CLOSED_CHANNELS_SCRIPT, SLEEP_GET_CLOSED_CHANNELS))
        threads.append(thread2)
        thread2.start()

    if ENABLE_REBALANCER:
        thread3 = threading.Thread(target=run_script_independently, args=(REBALANCER_SCRIPT, SLEEP_REBALANCER))
        threads.append(thread3)
        thread3.start()

    if ENABLE_CLOSE_CHANNEL:
        thread4 = threading.Thread(target=run_close_channel)
        threads.append(thread4)
        thread4.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    logging.info("Starting the automator-controller")
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Automator-controller manually interrupted.")
    except Exception as e:
        logging.error(f"Unexpected error in automator-controller: {e}")
    logging.info("Automator-controller finished.")
