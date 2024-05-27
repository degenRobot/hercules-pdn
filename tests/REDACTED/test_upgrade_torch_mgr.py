import brownie
from brownie import interface, Contract, accounts
import pytest
import time 
from tests.helper import encode_function_data


def test_migration(
    chain,
    token,
    vault,
    strategy,
    amount,
    strategy_contract,
    strategist,
    gov,
    user,
    RELATIVE_APPROX,
    torch_manager_contract,
    conf,
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    newTorchManager = torch_manager_contract.deploy(strategy, {'from': gov})
    strategy.upgradeTorchManager(newTorchManager, {'from' : strategist})

    chain.sleep(1)
    strategy.harvest()

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    assert strategy.torchManager() == newTorchManager.address
    assert newTorchManager.strategy() == strategy.address
