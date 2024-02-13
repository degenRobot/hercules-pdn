import brownie
from brownie import interface, Contract, accounts, MockAaveOracle
import pytest
import time 

def farmWithdraw(lp_farm, pid, strategy, amount):
    auth = accounts.at(strategy, True)
    lp_farm.withdraw( amount, {'from': auth})


def offSetDebtRatioLow(strategy, lp_token, token, Contract, swapPct, router, shortWhale):
    # use other AMM's LP to force some swaps 
    short = Contract(strategy.short())
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

"""
def setOracleShortPriceToLpPrice(strategy):
    short = Contract(strategy.short())
    # Oracle should reflect the "new" price
    pool_address_provider = interface.IPoolAddressesProvider(POOL_ADDRESS_PROVIDER)
    oracle = MockAaveOracle.at(pool_address_provider.getPriceOracle())
    new_price = strategy.getLpPrice()
    print("Oracle price before", oracle.getAssetPrice(short))
    oracle.setAssetPrice(short, new_price * 100)
    print("Strategy Lp price", new_price)
    print("Oracle price", oracle.getAssetPrice(short))
    print("Strategy oracle price", strategy.getOraclePrice())
"""

def steal(stealPercent, strategy, token, chain, gov, user):
    steal = round(strategy.estimatedTotalAssets() * stealPercent)
    strategy.liquidatePositionAuth(steal, {'from': gov})
    token.transfer(user, strategy.balanceOfWant(), {"from": accounts.at(strategy, True)})
    chain.sleep(1)
    chain.mine(1)


def strategySharePrice(strategy, vault):
    return strategy.estimatedTotalAssets() / vault.strategies(strategy)['totalDebt']



def test_reduce_debt_with_low_calcdebtratio(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, lp_whale, lp_farm, lp_price, pid, router, shortWhale, collatTarget
):
    swapPct = 0.015
    # Setting higher testPriceSource treshold for user
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})


    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    strategy.setSlippageConfig(9900, 400, 500, True)
    offSetDebtRatioLow(strategy, lp_token, token, Contract, swapPct, router, shortWhale)
    # setOracleShortPriceToLpPrice(strategy)
    debtRatio = strategy.calcDebtRatio()
    collatRatioBefore = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatioBefore))
    #assert pytest.approx(9500, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=2e-2) == collatRatioBefore

    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=2e-3) == int(amount / 2)

    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert strategy.estimatedTotalAssets() < 2 * 10 ** (token.decimals() - 3) # near zero



def test_reduce_debt_with_high_calcdebtratio(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, lp_whale, lp_farm, lp_price, pid, router, whale, collatTarget
):
    swapPct = 0.015
    # Setting higher testPriceSource treshold for user

    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})


    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    
    strategy.setSlippageConfig(9900, 400, 500, True)
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale)
    # setOracleShortPriceToLpPrice(strategy)
    debtRatio = strategy.calcDebtRatio()
    collatRatioBefore = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatioBefore))
    #assert pytest.approx(10500, rel=2e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=2e-2) == collatRatioBefore

    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    newAmount = strategy.estimatedTotalAssets() 

    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=2e-3) == int(newAmount / 2)

    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert strategy.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero


def test_increase_debt_with_low_calcdebtratio(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, lp_whale, lp_farm, lp_price, pid, router, shortWhale, collatTarget
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    half = int(amount / 2)

    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    # Change the debt ratio to ~95% and rebalance
    swapPct = 0.015
    # Setting higher testPriceSource treshold for user
    strategy.setSlippageConfig(9900, 400, 500, True)

    offSetDebtRatioLow(strategy, lp_token, token, Contract, swapPct, router, shortWhale)
    # setOracleShortPriceToLpPrice(strategy)

    debtRatio = strategy.calcDebtRatio()
    collatRatioBefore = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatioBefore))
    #assert pytest.approx(9500, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=2e-2) == collatRatioBefore

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=2e-3) == amount

    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert strategy.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero



def test_increase_debt_with_high_calcdebtratio(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, lp_whale, lp_farm, lp_price, pid, router, whale, collatTarget
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    # Setting higher testPriceSource treshold for user
    strategy.setSlippageConfig(9900, 400, 500, True)

    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount / 2 

    swapPct = 0.015
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale)
    # setOracleShortPriceToLpPrice(strategy)
    debtRatio = strategy.calcDebtRatio()
    collatRatioBefore = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatioBefore))
    #assert pytest.approx(10500, rel=2e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=2e-2) == collatRatioBefore

    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    newAmount = strategy.estimatedTotalAssets() 

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()

    loss = 0
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=2e-3) == int(amount - loss)

    
    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()

    assert strategy.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero
    
    # REMAINING AMOUNT BEING % of TVL 

    #remainingAmount = strategy.estimatedTotalAssets() / (amount - loss)
    #print('Remaining Amount:   {0}'.format(remainingAmount))