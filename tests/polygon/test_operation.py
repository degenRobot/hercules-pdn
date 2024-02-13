import brownie
from brownie import interface, Contract, accounts, MockAaveOracle
import pytest
import time 

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


def test_operation(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, router, whale, collatTarget
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    print("User balance before ", user_balance_before)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    print("User balance after ", token.balanceOf(user))
    
    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    print("Harvested")

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

    # withdrawal
    vault.withdraw(amount, user, 500, {'from' : user}) 
    assert (
        pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
    )

def test_emergency_exit(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # set emergency and exit
    strategy.setEmergencyExit()
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert strategy.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero
    assert pytest.approx(token.balanceOf(vault), rel=RELATIVE_APPROX) == amount

def test_profitable_harvest(
    chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    before_pps = vault.pricePerShare()

    # Use a whale of the harvest token to send
    harvest = interface.ERC20(conf['harvest_token'])
    harvestWhale = accounts.at(conf['harvest_token_whale'], True)
    sendAmount = round((vault.totalAssets() / conf['harvest_token_price']) * 0.05)
    print('Send amount: {0}'.format(sendAmount))
    print('harvestWhale balance: {0}'.format(harvest.balanceOf(harvestWhale)))
    harvest.transfer(strategy, sendAmount, {'from': harvestWhale})

    # Harvest 2: Realize profit
    chain.sleep(1)
    chain.mine(1)
    # assert 1 == 0
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault

    assert strategy.estimatedTotalAssets() + profit > amount
    assert vault.pricePerShare() > before_pps

def test_change_debt(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})

    chain.sleep(1)
    chain.mine(1)
    time.sleep(1)
    strategy.harvest()
    half = int(amount / 2)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    time.sleep(1)
    
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    time.sleep(1)
    
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    time.sleep(1)
    
    strategy.harvest()
    assert strategy.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero

def test_change_debt_lossy(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    time.sleep(1)
    

    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    chain.sleep(1)
    chain.mine(1)
    time.sleep(1)

    # Steal from the strategy
    steal = round(strategy.estimatedTotalAssets() * 0.01)
    strategy.liquidatePositionAuth(steal, {'from': gov})
    token.transfer(user, strategy.balanceOfWant(), {"from": accounts.at(strategy, True)})
    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})

    chain.sleep(1)
    chain.mine(1)
    time.sleep(1)
    

    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=1e-2) == int(amount * 0.98 / 2) 

    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})

    chain.sleep(1)
    chain.mine(1)
    time.sleep(1)
    

    strategy.harvest()
    assert strategy.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero

def test_sweep(gov, vault, strategy, token, user, amount, conf):
    # Strategy want token doesn't work
    token.transfer(strategy, amount, {"from": user})
    assert token.address == strategy.want()
    assert token.balanceOf(strategy) > 0
    strategy.sweep(token, {"from": gov})
    strategy.sweep(vault.address, {"from": gov})

def test_triggers(
    chain, gov, vault, strategy, token, amount, user, conf
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()

    strategy.harvestTrigger(0)
    strategy.tendTrigger(0)

def test_lossy_withdrawal(
    chain, gov, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)

    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # Steal from the strategy
    stealPercent = 0.01
    chain.sleep(1)
    chain.mine(1)
    steal(stealPercent, strategy, token, chain, gov, user)

    chain.mine(1)
    balBefore = token.balanceOf(user)
    vault.withdraw(amount, user, 150, {'from' : user}) 
    balAfter = token.balanceOf(user)
    assert pytest.approx(balAfter - balBefore, rel = 2e-3) == int(amount * .99)

def test_lossy_withdrawal_partial(
    chain, gov, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})

    chain.sleep(1)
    chain.mine(1)

    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount


    # Steal from the strategy
    stealPercent = 0.005
    chain.sleep(1)
    chain.mine(1)
    steal(stealPercent, strategy, token, chain, gov, user)

    balBefore = token.balanceOf(user)
    ssp_before = strategySharePrice(strategy, vault)

    #give RPC a little break to stop it spzzing out 
    time.sleep(5)

    half = int(amount / 2)
    vault.withdraw(half, user, 100, {'from' : user}) 
    balAfter = token.balanceOf(user)
    assert pytest.approx(balAfter - balBefore, rel = 2e-3) == (half * (1-stealPercent)) 

    # Check the strategy share price wasn't negatively effected
    ssp_after = strategySharePrice(strategy, vault)
    assert pytest.approx(ssp_before, rel = 2e-5) == ssp_after

def test_lossy_withdrawal_tiny(
    chain, gov, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})


    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)

    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    chain.sleep(1)
    chain.mine(1)
    # Steal from the strategy
    stealPercent = 0.005
    steal(stealPercent, strategy, token, chain, gov, user)
    
    balBefore = token.balanceOf(user)
    ssp_before = strategySharePrice(strategy, vault)

    #give RPC a little break to stop it spzzing out 
    time.sleep(5)

    tiny = int(amount * 0.001)
    vault.withdraw(tiny, user, 100, {'from' : user}) 
    balAfter = token.balanceOf(user)
    assert pytest.approx(balAfter - balBefore, rel = 2e-3) == (tiny * (1-stealPercent)) 

    # Check the strategy share price wasn't negatively effected
    ssp_after = strategySharePrice(strategy, vault)
    assert pytest.approx(ssp_before, rel = 2e-5) == ssp_after

def test_lossy_withdrawal_99pc(
    chain, gov, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    chain.sleep(1)
    chain.mine(1)
    # Steal from the strategy
    stealPercent = 0.005
    steal(stealPercent, strategy, token, chain, gov, user)

    balBefore = token.balanceOf(user)
    ssp_before = strategySharePrice(strategy, vault)

    #give RPC a little break to stop it spzzing out 
    time.sleep(5)

    tiny = int(amount * 0.99)
    vault.withdraw(tiny, user, 100, {'from' : user}) 
    balAfter = token.balanceOf(user)
    assert pytest.approx(balAfter - balBefore, rel = 2e-3) == (tiny * (1-stealPercent)) 

    # Check the strategy share price wasn't negatively effected
    ssp_after = strategySharePrice(strategy, vault)
    assert pytest.approx(ssp_before, rel = 2e-5) == ssp_after

def test_lossy_withdrawal_95pc(
    chain, gov, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf, deployed_vault
):

    chain.sleep(1)
    chain.mine(1)
    # Steal from the strategy
    stealPercent = 0.005
    steal(stealPercent, strategy, token, chain, gov, user)

    balBefore = token.balanceOf(user)
    ssp_before = strategySharePrice(strategy, vault)

    #give RPC a little break to stop it spzzing out 
    time.sleep(5)
    chain.sleep(1)
    chain.mine(1)

    tiny = int(amount * 0.95)
    vault.withdraw(tiny, user, 100, {'from' : user}) 
    balAfter = token.balanceOf(user)
    assert pytest.approx(balAfter - balBefore, rel = 2e-3) == (tiny * (1-stealPercent)) 

    # Check the strategy share price wasn't negatively effected
    ssp_after = strategySharePrice(strategy, vault)
    assert pytest.approx(ssp_before, rel = 2e-5) == ssp_after

"""
def test_reduce_debt_with_low_calcdebtratio(
    chain, gov, token, vault, strategy_mock_oracle, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, lp_whale, lp_farm, lp_price, pid, router, shortWhale, strategy_mock_initialized_vault, collatTarget
):
    swapPct = 0.015
    # Setting higher testPriceSource treshold for user
    strategy_mock_oracle.setSlippageConfig(9900, 400, 500, True)
    offSetDebtRatioLow(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, shortWhale)
    # setOracleShortPriceToLpPrice(strategy_mock_oracle)
    debtRatio = strategy_mock_oracle.calcDebtRatio()
    collatRatioBefore = strategy_mock_oracle.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatioBefore))
    #assert pytest.approx(9500, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=2e-2) == collatRatioBefore

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=2e-3) == int(amount / 2)

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 0, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()
    assert strategy_mock_oracle.estimatedTotalAssets() < 2 * 10 ** (token.decimals() - 3) # near zero



def test_reduce_debt_with_high_calcdebtratio(
    chain, gov, token, vault, strategy_mock_oracle, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, lp_whale, lp_farm, lp_price, pid, router, whale, strategy_mock_initialized_vault, collatTarget
):
    swapPct = 0.015
    # Setting higher testPriceSource treshold for user
    strategy_mock_oracle.setSlippageConfig(9900, 400, 500, True)
    offSetDebtRatioHigh(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, whale)
    # setOracleShortPriceToLpPrice(strategy_mock_oracle)
    debtRatio = strategy_mock_oracle.calcDebtRatio()
    collatRatioBefore = strategy_mock_oracle.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatioBefore))
    #assert pytest.approx(10500, rel=2e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=2e-2) == collatRatioBefore

    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()
    newAmount = strategy_mock_oracle.estimatedTotalAssets() 

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()

    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=2e-3) == int(newAmount / 2)

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 0, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()
    assert strategy_mock_oracle.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero


def test_increase_debt_with_low_calcdebtratio(
    chain, gov, token, vault, strategy_mock_oracle, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, lp_whale, lp_farm, lp_price, pid, router, shortWhale, collatTarget
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    half = int(amount / 2)

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    # Change the debt ratio to ~95% and rebalance
    swapPct = 0.015
    # Setting higher testPriceSource treshold for user
    strategy_mock_oracle.setSlippageConfig(9900, 400, 500, True)

    offSetDebtRatioLow(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, shortWhale)
    # setOracleShortPriceToLpPrice(strategy_mock_oracle)

    debtRatio = strategy_mock_oracle.calcDebtRatio()
    collatRatioBefore = strategy_mock_oracle.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatioBefore))
    #assert pytest.approx(9500, rel=1e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=2e-2) == collatRatioBefore

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=2e-3) == amount

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 0, {"from": gov})
    chain.sleep(1)
    strategy_mock_oracle.harvest()
    assert strategy_mock_oracle.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero



def test_increase_debt_with_high_calcdebtratio(
    chain, gov, token, vault, strategy_mock_oracle, user, strategist, amount, RELATIVE_APPROX, conf, lp_token, lp_whale, lp_farm, lp_price, pid, router, whale, collatTarget
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    # Setting higher testPriceSource treshold for user
    strategy_mock_oracle.setSlippageConfig(9900, 400, 500, True)

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 50_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount / 2 

    swapPct = 0.015
    offSetDebtRatioHigh(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, whale)
    # setOracleShortPriceToLpPrice(strategy_mock_oracle)
    debtRatio = strategy_mock_oracle.calcDebtRatio()
    collatRatioBefore = strategy_mock_oracle.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatioBefore))
    #assert pytest.approx(10500, rel=2e-3) == debtRatio
    assert pytest.approx(collatTarget, rel=2e-2) == collatRatioBefore

    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()
    newAmount = strategy_mock_oracle.estimatedTotalAssets() 

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 100_00, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()

    loss = 0
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=2e-3) == int(amount - loss)

    
    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 0, {"from": gov})
    chain.sleep(1)
    chain.mine(1)
    strategy_mock_oracle.harvest()

    assert strategy_mock_oracle.estimatedTotalAssets() < 10 ** (token.decimals() - 3) # near zero
    
    # REMAINING AMOUNT BEING % of TVL 

    #remainingAmount = strategy.estimatedTotalAssets() / (amount - loss)
    #print('Remaining Amount:   {0}'.format(remainingAmount))

"""