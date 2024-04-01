import brownie
from brownie import interface, Contract, accounts
import pytest
import time 

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
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # migrate to a new strategy
    new_strategy = strategist.deploy(strategy_contract, vault)
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    assert (
        pytest.approx(new_strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX)
        == amount
    )



def test_migration_with_low_calcdebtratio(
    chain,
    token,
    vault,
    strategy,
    amount,
    lp_token,
    Contract,
    strategy_contract,
    strategist,
    gov,
    user,
    RELATIVE_APPROX,
    router,
    shortWhale
):

    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # use other AMM's LP to force some swaps 
    short = Contract(strategy.short())
    swapAmt = short.balanceOf(lp_token)*0.015
    swapAmt = min(swapAmt, short.balanceOf(shortWhale))

    print("Force Large Swap - to offset debt ratios")

    short.approve(router.address, 2**256-1, {"from": shortWhale})
    router.swapExactTokensForTokens(swapAmt, 0, [short, token], shortWhale, 2**256-1, {"from": shortWhale})
    preWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    # migrate to a new strategy
    new_strategy = strategist.deploy(strategy_contract, vault)
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    # will be some loss so use rel = 2e-3 (due to forcing debt ratio away from 100%)
    assert (
        pytest.approx(new_strategy.estimatedTotalAssets(), rel=2e-3)
        == amount
    )


def test_migration_with_high_calcdebtratio(
    chain,
    token,
    vault,
    strategy,
    amount,
    lp_token,
    Contract,
    strategy_contract,
    strategist,
    gov,
    user,
    RELATIVE_APPROX,
    router,
    whale
):

    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # use other AMM's LP to force some swaps
    short = Contract(strategy.short())
    swapAmt = int(token.balanceOf(lp_token)*0.015)
    swapAmt = min(swapAmt, token.balanceOf(whale))

    print("Force Large Swap - to offset debt ratios")

    token.approve(router.address, 2**256-1, {"from": whale})
    router.swapExactTokensForTokens(swapAmt, 0, [token, short], whale, 2**256-1, {"from": whale})
    preWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    # migrate to a new strategy
    new_strategy = strategist.deploy(strategy_contract, vault)
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    # will be some loss so use rel = 2e-3 (due to forcing debt ratio away from 100%)
    assert (
        pytest.approx(new_strategy.estimatedTotalAssets(), rel=2e-3)
        == amount
    )

