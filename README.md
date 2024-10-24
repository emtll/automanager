![automator-lnd](https://github.com/user-attachments/assets/ea55c73a-4114-49aa-9359-83a8b2617e42)

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
The Automator LND project is designed to automate the management and optimization of a Lightning Network (LND) node. It integrates data from the LNDg database and various APIs to monitor channel performance, adjust fees, rebalance liquidity, and close channels based on configurable criteria. This project automates key tasks such as tracking channel activity, calculating profitability, and ensuring optimal routing efficiency.

The system relies on a dynamic configuration file (automator.conf) to manage paths, intervals, and thresholds. Key features include monitoring open and closed channels, calculating financial metrics (e.g., revenue, costs, profit, APY), and automating actions such as rebalancing and channel closures. It also ensures that inactive channels are closed based on activity patterns and liquidity movement, and integrates with external tools like charge-lnd and [mempool.space](https://mempool.space/) to manage fees and transactions efficiently.

By automating these processes, Automator LND reduces manual intervention, enhances node performance, and helps node operators maintain efficient routing while maximizing revenue and minimizing costs. This system is essential for optimizing the liquidity and routing potential of a Lightning Network node.

## Motivation
Managing a Lightning Network node used to be a time-consuming, repetitive, and often frustrating task. I found myself spending countless hours meticulously adjusting fees, monitoring channel activity, rebalancing liquidity, and closing underperforming channel all manually. Each operation demanded constant attention and intervention, diverting precious time away from more innovative and meaningful developments. It felt like a never-ending cycle of operational maintenance that stifled my productivity.

I realized I was stuck in the grind of maintaining the very infrastructure that was supposed to fuel my projects. This inefficiency was no longer sustainable. The need for automation became glaringly obvious, a solution that could free me from the burden of manual node management.

That’s when Automator LND was born. This project was designed to reclaim those lost hours, offering a fully automated solution for managing channels, adjusting fees, and optimizing liquidity. By delegating these repetitive tasks to an intelligent, automated system, I can now focus on more strategic developments, knowing that my node is running optimally in the background.

In short, Automator LND is more than just a tool-it's a game-changer. It has given me back control of my time and allowed me to direct my energy toward innovation, rather than endlessly managing channels.

## Requirements
To run the Automator LND project, the following dependencies and tools are required:

- [LNDg](https://github.com/cryptosharks131/lndg):

  - The script relies on the LNDg database (lndg.db) to gather detailed data on channel activity, payments, and forwardings. Ensure LNDg is installed and running, and the database path is correctly configured in automator.conf.

- [Charge-lnd](https://github.com/accumulator/charge-lnd):

  - Charge-lnd is used to manage Lightning Network channel fees and disable channels before closure. The script integrates with this tool for automatic channel management. Ensure charge-lnd is installed and the binary path is set in automator.conf.

- [Balance of Satoshis (BOS)](https://github.com/alexbosworth/balanceofsatoshis):

  - Balance of Satoshis is used for fee management and to issue commands related to node operations. Ensure BOS is installed, and the path to the binary is configured properly in automator.conf.

- [Regolancer](https://github.com/rkfg/regolancer):

  - Regolancer handles the automatic rebalancing of Lightning channels. It ensures liquidity is balanced across channels to optimize routing and node performance. You need regolancer installed and configured.

- [Regolancer-Controller](https://github.com/jvxis/regolancer-controller):

  - Regolancer-Controller is a systemd service that runs and manages regolancer. The Automator LND script interacts with this service to manage rebalancing activities. Ensure the service is installed and operational.

## Installation


## General Configuration
The automator.conf file is a central configuration file that governs the behavior of the Automator LND project. It allows for flexible control over the various automation scripts, paths, APIs, and operational parameters. Below is a detailed breakdown of the configuration sections:

- This section enables or disables key features of the automation system:
```
[Control]

enable_autofee: Enables the automatic fee adjustment process for channels. (Default: false)
enable_get_closed_channels: Enables the process to fetch and update data for closed channels. (Default: false)
enable_rebalancer: Enables the automatic rebalancing of channels. (Default: false)
enable_close_channel: Enables the automatic closure of inactive or unprofitable channels. (Default: false)
```

- This section defines the sleep intervals (in seconds) for various scripts, controlling how frequently they are executed:
```
[Automation]

sleep_autofee: Interval for the autofee.py script to run. (Default: 14400 seconds, i.e., 4 hours)
sleep_get_channels: Interval for fetching active channel data. (Default: 900 seconds, i.e., 15 minutes)
sleep_get_closed_channels: Interval for fetching closed channel data. (Default: 604800 seconds, i.e., 1 week)
sleep_rebalancer: Interval for the auto-rebalancer-config.py script. (Default: 86400 seconds, i.e., 24 hours)
sleep_closechannel: Interval for checking and closing inactive channels. (Default: 86400 seconds, i.e., 24 hours)
```

- This section specifies the paths to critical files and directories:
```
[Paths]

lndg_db_path: Path to the LNDg database, which contains historical channel data. (Default: lndg/data/db.sqlite3)
bos_path: Path to the Balance of Satoshis (BOS) binary used for node operations. (Default: .npm-global/bin/bos)
charge_lnd_config_dir: Directory where charge-lnd configurations are stored. (Default: charge-lnd/)
regolancer_json_path: Path to the regolancer configuration file, which handles rebalancing. (Default: regolancer-controller/default.json)
db_path: Path to the new database where processed data is stored. (Default: automator-lnd-voltz/data/database.db)
excluded_peers_path: Path to the JSON file that contains the list of peers to exclude from specific operations. (Default: automator-lnd-voltz/excluded_peers.json)
get_channels_script: Path to the script for fetching active channel data. (Default: scripts/get_channels_data.py)
autofee_script: Path to the script responsible for adjusting fees. (Default: scripts/autofee.py)
get_closed_channels_script: Path to the script for fetching closed channel data. (Default: scripts/get_closed_channels_data.py)
rebalancer_script: Path to the script that handles automatic rebalancing. (Default: scripts/auto-rebalancer-config.py)
close_channel_script: Path to the script for closing inactive channels. (Default: scripts/closechannel.py)
```

- This section configures the behavior of the fee adjustment process:
```
[Autofee]

max_fee_threshold: Maximum allowable fee rate (in PPM) for a channel before the fee is adjusted. (Default: 2500)
table_period: Time period (in days) over which to analyze data for fee adjustments. (Default: 30)
```

- This section handles the configuration for automatic rebalancing using regolancer:
```
[AutoRebalancer]

regolancer-controller_service: Specifies the systemd service responsible for running the regolancer controller. (Default: regolancer-controller.service)
```

- This section contains API endpoints for external services:
```
[API]

mempool_api_url_base: Base URL for fetching transaction details from Mempool.Space. (Default: https://mempool.space/api/tx/)
mempool_api_url_recomended_fees: URL for fetching recommended fee rates from Mempool.Space. (Default: https://mempool.space/api/v1/fees/recommended)
```

- This section defines parameters for fetching channel data:
```
[Get_channels_data]

period: Time period (in days) to analyze channel activity for metrics such as routing and liquidity. (Default: 30)
router_factor: Factor used to classify channels as sources or sinks based on liquidity movement. (Default: 2)
```

- This section configures the behavior of the channel closure process:
```
[Closechannel]

days_inactive_source: Number of inactive days before a source channel is considered for closure. (Default: 30 days)
days_inactive_sink: Number of inactive days before a sink channel is considered for closure. (Default: 30 days)
days_inactive_router: Number of inactive days before a router channel is considered for closure. (Default: 30 days)
movement_threshold_perc: Minimum percentage of liquidity movement required to avoid closure. (Default: 10%)
max_fee_rate: Maximum fee rate (in satoshis per vbyte) allowed for channel closure transactions. (Default: 1)
charge_lnd_bin: Path to the charge-lnd binary used for managing channel charges and disabling channels before closure. (Default: charge-lnd)
charge_lnd_interval: Time interval (in seconds) for running the charge-lnd service. (Default: 300 seconds)
htlc_check_interval: Time interval (in seconds) for checking pending HTLCs before closing a channel. (Default: 60 seconds)
```

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
