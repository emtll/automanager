# Automator LND
Automation for Lightning nodes of LND implementation

***Developed by [Morata](https://github.com/emtll) and already implemented in [Voltz Hub](https://amboss.space/node/02c4ae20674d7627021639986d75988b5f17c8693ed43b794beeef2384d04e5bf1) and [Voltz Wallet](https://amboss.space/node/03a961ab70c0011eff3b91b6a3afb81967597c1f27325a51dbfee72a692f1bb237) nodes***

- Automates:
  - Fee rates changes
  - Channel closure
  - Getting closed channels data summary for reports
  - Getting opened channels data for automation
  - Rebalancer configuration
  - Onchain funds (soon)
  - New channels opening (soon)
  - Swap outs (soon)
  - Magma auto-saler (soon)

## Abstract
## Motivation
## Requirements
## Installation
## General Configuration
## Scripts Explanation
In this section, we explain transparently how each script works. Feel free to change the logic to suit your use case.

### [automation-controller.py](https://github.com/emtll/automator-lnd/blob/main/automation-controller.py)
This script serves as the central controller for running multiple automation tasks related to LND node management, such as adjusting routing fees, collecting channel data, performing rebalancing, and closing inactive channels. It executes each task independently, in separate threads, allowing for flexible scheduling and non-blocking operations.

Key Features:
Multi-threaded Execution: Each task runs in its own thread, so different operations can be executed simultaneously without waiting for others to complete.
Logging: All significant actions and errors are logged to a file, ensuring proper monitoring of operations.
Configurable: All paths, sleep intervals, and feature toggles are defined in the automator.conf file, allowing for easy customization without modifying the code.
Graceful Error Handling: Errors in one thread do not affect other operations, as they are handled individually, and execution continues.

### [get_channels_data.py](https://github.com/emtll/automator-lnd/blob/main/scripts/get_channels_data.py)
This script is designed to analyze and manage Lightning Network (LND) channel data over different time periods (e.g., 1 day, 7 days, 30 days, lifetime). It performs the following key tasks:

Database Connections: It connects to two SQLite databases:

LNDg Database: This contains channel activity and liquidity data.
New Database: This stores processed channel data for different time periods.
Table Creation: It creates multiple tables (for 1-day, 7-day, 30-day, and lifetime periods) in the new database, each containing detailed information about active channels.

Channel Data Analysis: For each active channel, the script:

Fetches relevant metrics, such as liquidity, revenue, costs, and routing activity from the LNDg database.
Calculates key performance indicators (e.g., profit, revenue_ppm, cost_ppm, rebal_rate, apy).
Classifies channels as source, sink, router, or new_channel based on their routing activity.
API Usage: The script uses the Mempool.space API to get transaction details (e.g., channel opening dates).

Data Insertion/Update: It inserts or updates the channel data in the new database tables, ensuring that the data is up-to-date for each channel and time period.

Computation of Financial Metrics: The script calculates a wide range of financial metrics for each channel, such as:

Profit: The difference between revenue and costs.
Profit margin: The percentage of profit relative to the total routed volume.
Annualized Performance (APY and IAPY): How well the channel is performing over time.

### [autofee.py](https://github.com/emtll/automator-lnd/blob/main/scripts/autofee.py)
This script automates the process of adjusting routing fees for Lightning Network channels based on various conditions like channel liquidity, routing activity, and tag classification. The main idea is to optimize channel fee settings for different types of channels, ensuring efficient liquidity management and maximizing profit.

Key Functions and Logic:
Configuration and Paths:

The script loads configurations (paths, thresholds, periods) from automator.conf, making it flexible and customizable.
Paths to files like the bos_path (for executing BOS commands) and the excluded_peers_path (channels to exclude from fee adjustments) are expanded and used.
Channel Classification:

Channels are categorized as new_channel, sink, router, or source, based on their liquidity and activity patterns.
Each type has its own logic for fee adjustment.
Fee Adjustment Logic:

New Channels: Fees are adjusted based on liquidity and how long the channel has been open.
Sink Channels: Channels with low outbound liquidity and low activity have their fees increased to reduce potential routing failures.
Router Channels: Fees are adjusted to maintain a balanced liquidity flow between inbound and outbound traffic.
Source Channels: Channels with high outbound liquidity are incentivized with lower fees to attract more routing.
Fee Adjustment Commands:

The script uses BOS (Balance of Satoshis) commands to actually adjust fees by interacting with the LND node.
Fee increases or decreases are applied based on the channel's current state, liquidity ratio, and routing activity.
Exclusion and Recent Fee Changes:

Channels that are part of the exclusion list (defined in a JSON file) or have recently undergone fee changes are skipped to avoid unnecessary updates.
SQL Querying:

Channel data is retrieved from a local SQLite database, which stores the channel's performance metrics and activity logs.
Data like outbound liquidity, last activity, and cost per million (ppm) is fetched to calculate the new fees.

### [auto-rebalancer-config.py](https://github.com/emtll/automator-lnd/blob/main/scripts/auto-rebalancer-config.py)
This script is designed to manage and update the configuration for the regolancer tool, which is used for rebalancing channels in an LND node. The script automates the process of modifying two key lists—exclude_from and to—based on data from the database and a list of excluded peers.

Key Features and Workflow:
Configuration Loading:

The script reads paths and service names from automator.conf, including paths to the regolancer configuration file (regolancer_json_path), database (db_path), and excluded peers list (excluded_peers_path).
Channel Data Handling:

It fetches channel information from the opened_channels_lifetime table in the database, which contains channel IDs, public keys, and tags (such as new_channel, sink, router, or source).
Exclusion List Management:

The script loads the excluded peers from the JSON file specified in the excluded_peers_path. If a channel's public key matches an entry in this list, it is skipped from further processing.
Rebalancer Configuration Updates:

For each channel, the script checks the channel's tag:
If the tag is new_channel, sink, or router, the channel ID is added to both the exclude_from and to lists.
If the tag is source, the channel ID is removed from both lists.
It then compares the modified lists with the current configuration to detect any changes.
Saving and Restarting the Service:

If any changes are detected in the exclude_from or to lists, the script saves the updated configuration back to the regolancer JSON file and restarts the regolancer-controller_service to apply the changes.
If no changes are detected, the service is not restarted.
Key Functions:
restart_service(): Restarts the regolancer-controller service using systemctl if the configuration is updated.
has_list_changed(): Compares the old and new versions of the lists to determine if changes have occurred.
get_channels_data(): Retrieves relevant channel data (ID, public key, and tag) from the SQLite database.
load_json() and save_json(): Load and save the regolancer configuration and the excluded peers list.

### [closechannel.py](https://github.com/emtll/automator-lnd/blob/main/scripts/closechannel.py)
This script automates the process of monitoring and closing Lightning Network (LND) channels based on certain criteria. It checks if channels are inactive or not meeting liquidity thresholds and then closes them after confirming that no pending HTLCs exist. The script uses a configuration file (automator.conf) to manage paths, intervals, and settings.

Key Features:
Configuration Management:

The script reads from automator.conf for paths (database, excluded peers, and charge-lnd config) and parameters such as inactivity thresholds and fee rates.
Paths are expanded to ensure compatibility with both relative and absolute paths.
Channel Monitoring:

Channels are classified as source, sink, router, or new_channel, each with different criteria for inactivity and movement thresholds.
The script calculates the percentage of liquidity movement (routing) for each channel and checks the number of days since its last activity.
Channels that exceed the configured inactivity period and have low liquidity movement are flagged for closure.
Channel Closure Logic:

Exclusion List: Channels whose peers are listed in the excluded peers file are skipped.
Activity Check: Channels are evaluated based on their tags (source, sink, router) and the last recorded activity (inbound or outbound). Channels with no recent activity are considered for closure.
Movement Percentage: Channels with low liquidity movement below a defined threshold are marked for closure.
Pending HTLCs Check:

Before closing any channel, the script checks the database for pending HTLCs on that channel. If HTLCs are found, the script retries after a set interval.
Mempool Fee Check:

The script uses the Mempool.Space API to check the current high-priority fee for closing a channel. If the fee is below a user-defined threshold, it proceeds with closing the channel; otherwise, it waits and retries.
Charge-lnd Integration:

For channels meeting the closure criteria, a configuration file for charge-lnd is created or updated, and the charge-lnd binary is executed to disable the channel before closing.
Channel Closure:

The script retrieves the funding transaction ID and output index of the channel, and then attempts to close it using the lncli closechannel command, with a fee rate retrieved from the Mempool.Space API.
Looping Behavior:

The script continuously monitors channels and checks for closure criteria in a loop, allowing it to react to changes in channel activity over time.
Key Functions:
monitor_and_close_channels(): The core function that monitors all channels in the database, evaluates whether they should be closed, and initiates the closing process.
should_close_channel(): Determines whether a channel should be closed based on its inactivity, movement percentage, and tag.
check_pending_htlcs(): Checks if there are any pending HTLCs for a channel, ensuring the channel is not closed while there are unresolved transactions.
get_high_priority_fee(): Retrieves the current high-priority fee rate from the Mempool.Space API, used to decide the fee rate for closing a channel.
close_channel(): Executes the lncli closechannel command to close the channel with the appropriate fee rate.

### [get_closed_channels_data.py](https://github.com/emtll/automator-lnd/blob/main/scripts/get_closed_channels_data.py)
This script automates the process of gathering and updating data on closed channels in a Lightning Network (LND) node. It fetches information from the LNDg database, calculates key financial metrics, and stores this data in a new SQLite database.

Key Features:
Database Connections:

The script connects to two SQLite databases: the LNDg database (containing channel activity and closure data) and a new database where processed closed channel information is stored.
Paths for these databases are dynamically set using the automator.conf file.
Closed Channel Data Collection:

It queries the LNDg database to fetch all channels that have been closed.
For each closed channel, the script retrieves key details like the public key, channel alias, closing transaction, and funding transaction.
Financial and Performance Metrics:

The script calculates several important metrics for each closed channel, including:
Total Routed In/Out: Total liquidity routed through the channel.
Total Cost/Revenue: The cost of rebalancing and revenue from routing.
Profit: The difference between revenue and cost.
Profit PPM: Profit per million satoshis routed out.
Cost PPM and Revenue PPM: The cost and revenue for every million satoshis routed.
APY and IAPY: Annual percentage yield (APY) and inbound APY (IAPY), based on profit and liquidity movement.
Sats per Day Profit: Daily profit generated by the channel.
Assisted Revenue: Revenue generated by assisting other nodes with liquidity.
Channel Tagging: Channels are tagged as new_channel, source, sink, or router based on liquidity movement patterns.
Transaction Date Retrieval:

The script uses the Mempool.Space API to fetch the block time of the funding and closing transactions, allowing it to calculate the number of days the channel was open.
Data Insertion:

The processed channel data, including all calculated metrics, is inserted into the closed_channels table in the new database.
The table structure includes fields like chan_id, pubkey, alias, opening_date, closure_date, total_revenue, profit, and many others.
Efficient Data Updates:

If a channel is already in the database, it will be updated with the latest calculated data.
Key Functions:
connect_db() and connect_new_db(): These functions establish connections to the LNDg database and the new database where processed data is stored.
create_closed_channels_table(): Creates the closed_channels table if it doesn't exist, with fields to store metrics for closed channels.
get_closed_channels(): Queries the LNDg database to fetch all closed channels.
calculate_* Functions: These functions calculate key financial metrics such as PPM (parts per million), profit, APY, IAPY, and daily profits based on liquidity and routing data.
get_tx_date(): Fetches the block time for a given transaction from the Mempool.Space API, which helps determine when a channel was opened or closed.
tag(): Tags channels based on their activity and liquidity movement (new_channel, source, sink, or router).
update_closed_channels_db(): Inserts or updates the calculated metrics for each closed channel into the new database.
Workflow:
Connect to Databases: The script connects to both the LNDg and new databases.
Fetch Closed Channels: It retrieves all closed channels from the LNDg database.
Calculate Metrics: For each closed channel, it calculates various financial metrics like profit, revenue, and APY.
Store Data: The calculated metrics are stored in the new database.
Completion: Once all channels are processed, the script closes the database connections and prints a completion message.
