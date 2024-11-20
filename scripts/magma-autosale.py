import telebot
import time
import os
import schedule
import logging
import configparser
import sys

from datetime import datetime
from magma import check_offers, accept_order, check_channel, get_address_by_pubkey, confirm_channel_point_to_amboss
from magma_lnd_rest import create_invoice, connect_to_node, open_channel, get_channel_point

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

TOKEN = config['Telegram']['bot_token']
EXPIRE = 180000
CHAT_ID = config['Telegram']['chat_id']
log_file_path = "amboss_channel_point.log"
log_file_path2 = "amboss_open_command.log"

bot = telebot.TeleBot(TOKEN)
print("Amboss Channel Open Bot Started")

@bot.message_handler(commands=['channel-to-open'])
def send_telegram_message(message):
    if message is None:
        class DummyMessage:
            def __init__(self):
                self.chat = DummyChat()

        class DummyChat:
            def __init__(self):
                self.id = CHAT_ID

        message = DummyMessage()

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    print("Date and Time:", formatted_datetime)
    bot.send_message(message.chat.id, text="🔥 Magma Auto Saler 🔥 \n\nChecking new Orders...")
    valid_channel_opening_offer = check_offers()

    if not valid_channel_opening_offer:
        bot.send_message(message.chat.id, text="No Magma orders available")
    else:
        bot.send_message(message.chat.id, text="Found Order:")
        formatted_offer = f"ID: {valid_channel_opening_offer['id']}\n"
        formatted_offer += f"Amount: {valid_channel_opening_offer['seller_invoice_amount']}\n"
        formatted_offer += f"Status: {valid_channel_opening_offer['status']}\n"
        bot.send_message(message.chat.id, text=formatted_offer)
        bot.send_message(message.chat.id, text=f"Generating Invoice of {valid_channel_opening_offer['seller_invoice_amount']} sats...")
        invoice_hash, invoice_request = create_invoice(valid_channel_opening_offer['seller_invoice_amount'],f"Magma-Channel-Sale-Order-ID:{valid_channel_opening_offer['id']}", str(EXPIRE))
        
        if "Error" in invoice_hash:
            print(invoice_hash)
            bot.send_message(message.chat.id, text=invoice_hash)
            return

        print("Invoice Result:", invoice_request)
        bot.send_message(message.chat.id, text=invoice_request)
        bot.send_message(message.chat.id, text=f"Accepting Order: {valid_channel_opening_offer['id']}")
        accept_result = accept_order(valid_channel_opening_offer['id'], invoice_request)
        print("Order Acceptance Result:", accept_result)
        bot.send_message(message.chat.id, text=f"Order Acceptance Result: {accept_result}")
    
        if 'data' in accept_result and 'sellerAcceptOrder' in accept_result['data']:
            if accept_result['data']['sellerAcceptOrder']:
                success_message = "Invoice Successfully Sent to Amboss. Now you need to wait for Buyer payment to open the channel."
                bot.send_message(message.chat.id, text=success_message)
                print(success_message)
            else:
                failure_message = "Failed to accept the order. Check the accept_result for details."
                bot.send_message(message.chat.id, text=failure_message)
                print(failure_message)
                return
        
        else:
            error_message = "Unexpected format in the order acceptance result. Check the accept_result for details."
            bot.send_message(message.chat.id, text=error_message)
            print(error_message)
            print("Unexpected Order Acceptance Result Format:", accept_result)
            return
    
    # Wait five minutes to check if the buyer pre-paid the offer
    time.sleep(300)
    
    if not os.path.exists(log_file_path) and not os.path.exists(log_file_path2):
        bot.send_message(message.chat.id, text="Checking Channels to Open...")
        valid_channel_to_open = check_channel()

        if not valid_channel_to_open:
            bot.send_message(message.chat.id, text="No Channels pending to open.")
            return

        bot.send_message(message.chat.id, text="Order:")
        formatted_offer = f"ID: {valid_channel_to_open['id']}\n"
        formatted_offer += f"Customer: {valid_channel_to_open['account']}\n"
        formatted_offer += f"Size: {valid_channel_to_open['size']} SATS\n"
        formatted_offer += f"Invoice: {valid_channel_to_open['seller_invoice_amount']} SATS\n"
        formatted_offer += f"Status: {valid_channel_to_open['status']}\n"
        bot.send_message(message.chat.id, text=formatted_offer)
        
        # Connect to peer
        bot.send_message(message.chat.id, text=f"Connecting to peer: {valid_channel_to_open['account']}")
        customer_addr = get_address_by_pubkey(valid_channel_to_open['account'])
        node_connection = connect_to_node(customer_addr)

        if node_connection == 0:
            print(f"Successfully connected to node {customer_addr}")
            bot.send_message(message.chat.id, text=f"Successfully connected to node {customer_addr}")
        
        else:
            print(f"Error connecting to node {customer_addr}:")
            bot.send_message(message.chat.id, text=f"Can't connect to node {customer_addr}. Maybe it is already connected trying to open channel anyway")

        #Open Channel
        bot.send_message(message.chat.id, text=f"Open a {valid_channel_to_open['size']} SATS channel")    
        funding_tx, msg_open = open_channel(valid_channel_to_open['account'], valid_channel_to_open['size'], valid_channel_to_open['seller_invoice_amount'])

        # Deal with  errors and show on Telegram
        if funding_tx == -1 or funding_tx == -2 or funding_tx == -3:
            bot.send_message(message.chat.id, text=msg_open)
            return
        
        # Send funding tx to Telegram
        bot.send_message(message.chat.id, text=msg_open)
        print("Waiting 10 seconds to get channel point...")
        bot.send_message(message.chat.id, text="Waiting 10 seconds to get channel point...")
        
        # Wait 10 seconds to get channel point
        time.sleep(10)

        # Get Channel Point
        channel_point = get_channel_point(funding_tx)
        
        if channel_point is None:
            #log_file_path = "amboss_channel_point.log"
            msg_cp = f"Can't get channel point, please check the log file {log_file_path} and try to get it manually from LNDG for the funding txid: {funding_tx}"
            print(msg_cp)
            bot.send_message(message.chat.id,text=msg_cp)
            
            # Create the log file and write the channel_point value
            with open(log_file_path, "w") as log_file:
                log_file.write(funding_tx)
            return
        
        print(f"Channel Point: {channel_point}")
        bot.send_message(message.chat.id, text=f"Channel Point: {channel_point}")
        print("Waiting 10 seconds to Confirm Channel Point to Magma...")
        bot.send_message(message.chat.id, text="Waiting 10 seconds to Confirm Channel Point to Magma...")
        
        # Wait 10 seconds to get channel point
        time.sleep(10)
        
        # Send Channel Point to Amboss
        print("Confirming Channel to Amboss...")
        bot.send_message(message.chat.id, text= "Confirming Channel to Amboss...")
        channel_confirmed = confirm_channel_point_to_amboss(valid_channel_to_open['id'],channel_point)

        if channel_confirmed is None or "Error" in channel_confirmed:
            #log_file_path = "amboss_channel_point.log"
            if "Error" in channel_confirmed:
                msg_confirmed = channel_confirmed
            else:
                msg_confirmed = f"Can't confirm channel point {channel_point} to Amboss, check the log file {log_file_path} and try to do it manually"
            print(msg_confirmed)
            bot.send_message(message.chat.id, text=msg_confirmed)
            
            # Create the log file and write the channel_point value
            with open(log_file_path, "w") as log_file:
                log_file.write(channel_point)
            return
        
        msg_confirmed = "Opened Channel confirmed to Amboss"
        print(msg_confirmed)
        print(f"Result: {channel_confirmed}")
        bot.send_message(message.chat.id, text=msg_confirmed)
        bot.send_message(message.chat.id, text=f"Result: {channel_confirmed}")

    elif os.path.exists(log_file_path):
        bot.send_message(message.chat.id, text=f"The log file {log_file_path} already exists. This means you need to check if there is a pending channel to confirm to Amboss. Check the {log_file_path} content")

    elif os.path.exists(log_file_path2):
        bot.send_message(message.chat.id, text=f"The log file {log_file_path2} already exists. This means you have a problem with the LNCLI command, check first the {log_file_path2} content and if the channel is opened")


def execute_bot_behavior():
    print("Executing bot behavior...")
    send_telegram_message(None)

# Schedule the bot_behavior function to run every 20 minutes
schedule.every(10).minutes.do(execute_bot_behavior)

if __name__ == "__main__":

    # Check if the log file exists
    print(f"Exist File Path1: {os.path.exists(log_file_path)}\n")
    print(f"Exist File Path2: {os.path.exists(log_file_path2)}\n")

    if not os.path.exists(log_file_path) and not os.path.exists(log_file_path2):
        if len(sys.argv) > 1 and sys.argv[1] == '--cron':
             # Execute the scheduled bot behavior immediately
            execute_bot_behavior()
            # If --cron argument is provided and log file doesn't exist, execute the scheduled bot behavior
            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            # Otherwise, run the bot polling for new messages
            bot.polling(none_stop=True)
    
    elif os.path.exists(log_file_path):
        print(f"The log file {log_file_path} already exists. This means you need to check if there is a pending channel to confirm to Amboss. Check the {log_file_path} content")
    
    elif os.path.exists(log_file_path2):
        print(f"The log file {log_file_path2} already exists. This means you have a problem with the LNCLI command, check first the {log_file_path2} content and if the channel is opened")