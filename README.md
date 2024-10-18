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
### [get_channels_data.py](https://github.com/emtll/automator-lnd/blob/main/scripts/get_channels_data.py)
### [autofee.py](https://github.com/emtll/automator-lnd/blob/main/scripts/autofee.py)
### [auto-rebalancer-config.py](https://github.com/emtll/automator-lnd/blob/main/scripts/auto-rebalancer-config.py)
### [closechannel.py](https://github.com/emtll/automator-lnd/blob/main/scripts/closechannel.py)
### [get_closed_channels_data.py](https://github.com/emtll/automator-lnd/blob/main/scripts/get_closed_channels_data.py)
