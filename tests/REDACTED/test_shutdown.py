# TODO: Add tests that show proper operation of this strategy through "emergencyExit"
#       Make sure to demonstrate the "worst case losses" as well as the time it takes

from brownie import ZERO_ADDRESS
import pytest


def test_vault_shutdown_can_withdraw(
    chain, token, vault, strategy, user, amount, strategist, gov, RELATIVE_APPROX
):
    ## Deposit in Vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    if token.balanceOf(user) > 0:
        token.transfer(ZERO_ADDRESS, token.balanceOf(user), {"from": user})

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    debt_before = strategy.balanceDebt()
    chain.sleep(3600 * 7)
    chain.mine(1)
    delta_debt = strategy.balanceDebt() - debt_before
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount - delta_debt
    ## Set Emergency
    strategy.setEmergencyExit({"from": strategist})

    ## Withdraw (does it work, do you get what you expect)
    vault.withdraw(amount, user, 500, {'from' : user}) 
    assert pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == amount - delta_debt


def test_basic_shutdown(
    chain, token, vault, strategy, user, strategist, gov, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    chain.mine(100)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    ## Earn interest
    chain.sleep(3600 * 24 * 1)  ## Sleep 1 day
    chain.mine(1)

    # Harvest 2: Realize profit
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    ## Set emergency
    strategy.setEmergencyExit({"from": strategist})

    strategy.harvest()  ## Remove funds from strategy

    dust = amount*0.001
    assert strategy.estimatedTotalAssets() < dust ## the strat shouldn't have more than some dust 
    assert pytest.approx(token.balanceOf(vault),rel=1e-3) == amount