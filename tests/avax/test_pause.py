import brownie
from brownie import interface, Contract, accounts, MockAaveOracle
import pytest
import time

from conftest import POOL_ADDRESS_PROVIDER
def farmWithdraw(lp_farm, pid, strategy, amount):
    auth = accounts.at(strategy, True)
    lp_farm.withdraw( amount, {'from': auth})


def offSetDebtRatioLow(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, shortWhale):
    # use other AMM's LP to force some swaps 
    short = Contract(strategy_mock_oracle.short())
    swapAmtMax = short.balanceOf(lp_token)*swapPct
    swapAmt = min(swapAmtMax, short.balanceOf(shortWhale))
    print("Force Large Swap - to offset debt ratios")
    short.approve(router, 2**256-1, {"from": shortWhale})
    router.swapExactTokensForTokens(swapAmt, 0, [short, token], shortWhale, 2**256-1, {"from": shortWhale})
    


def offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale):
    # use other AMM's LP to force some swaps 
    short = Contract(strategy.short())
    swapAmtMax = token.balanceOf(lp_token)*swapPct
    swapAmt = min(swapAmtMax, token.balanceOf(whale))
    print("Force Large Swap - to offset debt ratios")
    token.approve(router, 2**256-1, {"from": whale})
    router.swapExactTokensForTokens(swapAmt, 0, [token, short], whale, 2**256-1, {"from": whale})

def setOracleShortPriceToLpPrice(strategy_mock_oracle):
    short = Contract(strategy_mock_oracle.short())
    # Oracle should reflect the "new" price
    pool_address_provider = interface.IPoolAddressesProvider(POOL_ADDRESS_PROVIDER)
    oracle = MockAaveOracle.at(pool_address_provider.getPriceOracle())
    new_price = strategy_mock_oracle.getLpPrice()
    print("Oracle price before", oracle.getAssetPrice(short))
    oracle.setAssetPrice(short, new_price * 100)
    print("Strategy Lp price", new_price)
    print("Oracle price", oracle.getAssetPrice(short))
    print("Strategy oracle price", strategy_mock_oracle.getOraclePrice())


def steal(stealPercent, strategy, token, chain, gov, user):
    steal = round(strategy.estimatedTotalAssets() * stealPercent)
    strategy.liquidatePositionAuth(steal, {'from': gov})
    token.transfer(user, strategy.balanceOfWant(), {"from": accounts.at(strategy, True)})
    chain.sleep(1)
    chain.mine(1)


def strategySharePrice(strategy, vault):
    return strategy.estimatedTotalAssets() / vault.strategies(strategy)['totalDebt']



def test_pause_withdraw(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, router, whale, collatTarget
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    
    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    strat = strategy
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # make tiny swap to avoid issue where dif
    swapPct = 1 / 1000
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale) 

    # check debt ratio
    debtRatio = strategy.calcDebtRatio()
    collatRatio = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(10000, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=1e-2) == collatRatio
    chain.sleep(1)
    chain.mine(1)

    strategy.pauseStrat()
    
    collatRatio = strategy.calcCollateral()
    assert pytest.approx(0, rel=1e-2) == collatRatio
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # withdrawal
    vault.withdraw(amount, user, 500, {'from' : user}) 
    assert (
        pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
    )


def test_pause_unpauseStrat(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, router, whale, collatTarget
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    
    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    strat = strategy
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # make tiny swap to avoid issue where dif
    swapPct = 1 / 1000
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale) 

    # check debt ratio
    debtRatio = strategy.calcDebtRatio()
    collatRatio = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(10000, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=1e-2) == collatRatio
    chain.sleep(1)
    chain.mine(1)

    strategy.pauseStrat()
    
    collatRatio = strategy.calcCollateral()
    assert pytest.approx(0, rel=1e-2) == collatRatio


    strategy.unpauseStrat()

    debtRatio = strategy.calcDebtRatio()
    collatRatio = strategy.calcCollateral()

    assert pytest.approx(10000, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=1e-2) == collatRatio
    chain.sleep(1)
    chain.mine(1)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount



def test_pause_reduce_debt(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, router, whale, collatTarget
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    
    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    strat = strategy
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # make tiny swap to avoid issue where dif
    swapPct = 1 / 1000
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale) 

    # check debt ratio
    debtRatio = strategy.calcDebtRatio()
    collatRatio = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(10000, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=1e-2) == collatRatio
    chain.sleep(1)
    chain.mine(1)

    strategy.pauseStrat()
    
    collatRatio = strategy.calcCollateral()
    assert pytest.approx(0, rel=1e-2) == collatRatio

    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=2e-3) == amount * 0.5

    collatRatio = strategy.calcCollateral()
    assert pytest.approx(0, rel=1e-2) == collatRatio

def test_pause_increase_debt(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, router, whale, collatTarget
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    
    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})


    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    strat = strategy
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount * 0.5

    # make tiny swap to avoid issue where dif
    swapPct = 1 / 1000
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale) 

    # check debt ratio
    debtRatio = strategy.calcDebtRatio()
    collatRatio = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(10000, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=1e-2) == collatRatio
    chain.sleep(1)
    chain.mine(1)

    strategy.pauseStrat()
    
    collatRatio = strategy.calcCollateral()
    assert pytest.approx(0, rel=1e-2) == collatRatio

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=2e-3) == amount 

    collatRatio = strategy.calcCollateral()
    assert pytest.approx(0, rel=1e-2) == collatRatio


def test_pause_offsetHigh(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, router, whale, collatTarget
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    
    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    strat = strategy
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # make tiny swap to avoid issue where dif
    swapPct = 0.01
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale) 

    # check debt ratio
    debtRatio = strategy.calcDebtRatio()
    collatRatio = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(collatTarget, rel=1e-2) == collatRatio
    chain.sleep(1)
    chain.mine(1)

    strategy.pauseStrat()
    
    collatRatio = strategy.calcCollateral()
    assert pytest.approx(0, rel=1e-2) == collatRatio
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-3) == amount


def test_pause_offsetLow(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, router, shortWhale, collatTarget
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    
    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    strat = strategy
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # make tiny swap to avoid issue where dif
    swapPct = 0.01
    offSetDebtRatioLow(strategy, lp_token, token, Contract, swapPct, router, shortWhale) 

    # check debt ratio
    debtRatio = strategy.calcDebtRatio()
    collatRatio = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(collatTarget, rel=1e-2) == collatRatio
    chain.sleep(1)
    chain.mine(1)

    strategy.pauseStrat()
    
    collatRatio = strategy.calcCollateral()
    assert pytest.approx(0, rel=1e-2) == collatRatio
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-3) == amount
