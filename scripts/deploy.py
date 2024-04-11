from pathlib import Path

from brownie import accounts, config, network, project, web3, StrategyInsurance
from eth_utils import is_checksum_address
from tests.helper import encode_function_data
import click

API_VERSION = config["dependencies"][0].split("@")[-1]
Vault = project.load(
    Path.home() / ".brownie" / "packages" / config["dependencies"][0]
).Vault

# edit this to deploy
from brownie import USDCWETHTORCH, TorchManager, GrailManagerProxy, CommonHealthCheck

Strategy = USDCWETHTORCH

def get_address(msg: str, default: str = None) -> str:
    val = click.prompt(msg, default=default)

    # Keep asking user for click.prompt until it passes
    while True:

        if is_checksum_address(val):
            return val
        elif addr := web3.ens.address(val):
            click.echo(f"Found ENS '{val}' [{addr}]")
            return addr

        click.echo(
            f"I'm sorry, but '{val}' is not a checksummed address or valid ENS record"
        )
        # NOTE: Only display default once
        val = click.prompt(msg)


def main():
    print(f"You are using the '{network.show_active()}' network")
    dev = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    print(f"You are using: 'dev' [{dev.address}]")
    #vault = Vault.at(get_address("Deployed Vault: "))
    vault = Vault.deploy({'from': dev})
    
    token = '0xEA32A96608495e54156Ae48931A7c20f0dcc1a21'
    

    vault.initialize(token, dev, dev, "Test Torch USDC", "hnUSDC", dev, dev)

    print(
        f"""
    Strategy Parameters

       api: {vault.apiVersion()}
     token: {vault.token()}
      name: '{vault.name()}'
    symbol: '{vault.symbol()}'
    """
    )
    
    if input("Continue? y/[N]: ").lower() != "y":
        print('Thanks. Byeee')
        return

    # publish_source = click.confirm("Verify source on etherscan?")
    # if input("Deploy Strategy? y/[N]: ").lower() != "y":
    #     return
    
    # strategy = Strategy.deploy(vault, {"from": dev}, publish_source=publish_source)
    print('Deploying...')

    TORCH = '0xbB1676046C36BCd2F6fD08d8f60672c7087d9aDF'
    TORCH_ROUTER = '0x14679D1Da243B8c7d1A4c6d0523A2Ce614Ef027C'


    conf = {
        'lp_token': '0x4C10a0E5fc4a6eDe720dEcdAD99B281076EAC0fA',
        'lp_farm': '0xE67348414A5Ab2c065FA2b422144A6c5C925cEfF',
        'harvest_token' : '0x3d9907F9a368ad0a51Be60f7Da3b97cf940982D8',
        'router' : '0xc873fEcbd354f5A56E00E710B90EF4201db2448d'
        'router': TORCH_ROUTER,
        'harvest_token': TORCH,

    }

    strat = Strategy.deploy(vault,{"from": dev})
    yieldBooster = '0xA4dEfAf0904529A1ffE04CC8A1eF3BC7d7F7b121'
    xGrail = '0xF192897fC39bF766F1011a858dE964457bcA5832'


    grailManager = TorchManager.deploy(dev, strat, strat.want(), conf['lp_token'], conf['harvest_token'], xGrail, conf['lp_farm'], conf['router'], yieldBooster, {'from': dev})

    #encoded_initializer_function = encode_function_data(grailManager.initialize, dev, strat, grailConfig)

    #grailManagerProxy = GrailManagerProxy.deploy(grailManager.address, encoded_initializer_function, {'from':dev})
    strat.setGrailManager(grailManager, {'from':dev})

    insurance = StrategyInsurance.deploy(strat, {'from':dev})
    strat.setInsurance(insurance, {'from': dev})  
    
    healthCare = CommonHealthCheck.deploy({'from':dev})
    strat.setHealthCheck(healthCare, {'from': dev})

    strat.setMinReportDelay(28740, {'from':dev})
    # strat.setMaxReportDelay(43200, {'from':dev})
    # offset = 10
    # strat.setDebtThresholds(9800 + offset, 10200 - offset, 5000, {'from':dev})
    # strat.setCollateralThresholds(4500, 5000, 5500, 8500, {'from':dev})
    
    # flatten code
    # f = open("flat.sol", "w")
    # Strategy.get_verification_info()
    # f.write(Strategy._flattener.flattened_source)
    # f.close()
    print('Successfully Deploy. See flat.sol for verification and don\'t forget to set the HEALTH CHECK!!')
    