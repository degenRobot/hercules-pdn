from pathlib import Path

from brownie import accounts, config, network, project, web3, StrategyInsurance
from eth_utils import is_checksum_address
import click

API_VERSION = config["dependencies"][0].split("@")[-1]
Vault = project.load(
    Path.home() / ".brownie" / "packages" / config["dependencies"][0]
).Vault


# edit this to deploy
from brownie import USDTAVAXBQIVTX
Strategy = USDTAVAXBQIVTX




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
    vault = Vault.at(get_address("Deployed Vault: "))

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
    strat = Strategy.deploy(vault, {"from": dev})
    insurance = StrategyInsurance.deploy(strat, {'from':dev})
    strat.setInsurance(insurance, {'from': dev})    
    strat.setMinReportDelay(28800, {'from':dev})
    strat.setMaxReportDelay(43200, {'from':dev})
    offset = 10
    strat.setDebtThresholds(9800 + offset, 10200 - offset, 5000, {'from':dev})
    strat.setCollateralThresholds(4500, 5000, 5500, 8500, {'from':dev})
    
    # flatten code
    f = open("flat.sol", "w")
    Strategy.get_verification_info()
    f.write(Strategy._flattener.flattened_source)
    f.close()
    print('Successfully Deploy. See flat.sol for verification and don\'t forget to set the HEALTH CHECK!!')
    