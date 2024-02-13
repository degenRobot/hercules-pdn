import brownie
from brownie import interface, Contract, accounts, MockAaveOracle
import pytest
import time 

"""
POOL = '0x794a61358D6845594F94dc1DB02A252b5b4814aD' 
want = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174' # USDC
"""

ORACLE = '0xEBd36016B3eD09D4693Ed4251c67Bd858c3c7C9C'
POOL_ADDRESS_PROVIDER = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'

def steal(stealPercent, strategy, token, chain, gov, user):
    steal = round(strategy.estimatedTotalAssets() * stealPercent)
    strategy.liquidatePositionAuth(steal, {'from': gov})
    token.transfer(user, strategy.balanceOfWant(), {"from": accounts.at(strategy, True)})
    chain.sleep(1)
    chain.mine(1)


def offSetDebtRatioLow(strategy, lp_token, token, Contract, swapPct, router, shortWhale):
    # use other AMM's LP to force some swaps 

    short = Contract(strategy.short())
    swapAmtMax = short.balanceOf(lp_token)*swapPct
    swapAmt = min(swapAmtMax, short.balanceOf(shortWhale))
    print("Force Large Swap - to offset debt ratios")
    short.approve(router, 2**256-1, {"from": shortWhale})
    router.swapExactTokensForTokens(swapAmt, 0, [short, token], shortWhale, 2**256-1, {"from": shortWhale})
    

    

def offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale):
    short = Contract(strategy.short())
    swapAmtMax = token.balanceOf(lp_token)*swapPct
    swapAmt = min(swapAmtMax, token.balanceOf(whale))
    print("Force Large Swap - to offset debt ratios")
    token.approve(router, 2**256-1, {"from": whale})
    router.swapExactTokensForTokens(swapAmt, 0, [token, short], whale, 2**256-1, {"from": whale})
    
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

def strategySharePrice(strategy, vault):
    return strategy.estimatedTotalAssets() / vault.strategies(strategy)['totalDebt']

def test_lossy_withdrawal_partial(
    chain, gov, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, conf
):
    #strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    # Steal from the strategy
    stealPercent = 0.005
    steal(stealPercent, strategy, token, chain, gov, user)
    balBefore = token.balanceOf(user)

    #give RPC a little break to stop it spzzing out 
    time.sleep(5)

    half = int(amount / 2)
    vault.withdraw(half, user, 100, {'from' : user}) 
    balAfter = token.balanceOf(user)

    assert pytest.approx(balAfter - balBefore, rel = 2e-3) == (half * (1-stealPercent)) 

def test_partialWithdrawal_unbalancedDebtLow(
    chain, gov, accounts, token, vault, strategy, user, strategist, lp_token ,amount, RELATIVE_APPROX, conf, router, shortWhale
):
    #strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    swapPct = 0.01
    # use other AMM's LP to force some swaps 
    offSetDebtRatioLow(strategy, lp_token, token, Contract, swapPct, router, shortWhale)
    #setOracleShortPriceToLpPrice(strategy)

    strategy.setSlippageConfig(9900, 500, 500, False)

    preWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    strategyLoss = amount - strategy.estimatedTotalAssets()
    lossPercent = strategyLoss / amount

    chain.sleep(1)
    chain.mine(1)
    balBefore = token.balanceOf(user)
    ssp_before = strategySharePrice(strategy, vault)


    #give RPC a little break to stop it spzzing out 
    time.sleep(2)
    percentWithdrawn = 0.7

    withdrawAmt = int(amount * percentWithdrawn)
    vault.withdraw(withdrawAmt, user, 100, {'from' : user}) 
    balAfter = token.balanceOf(user)
    print("Withdraw Amount : ")
    print(balAfter - balBefore)

    assert (balAfter - balBefore) < int(percentWithdrawn * amount * (1 - lossPercent))

    # confirm the debt ratio wasn't impacted
    postWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Post Withdraw debt Ratio :  {0}'.format(postWithdrawDebtRatio))
    assert pytest.approx(preWithdrawDebtRatio, rel = 2e-3) == postWithdrawDebtRatio

    # confirm the loss was not felt disproportionately by the strategy - Strategy Share Price
    ssp_after = strategySharePrice(strategy, vault)
    assert ssp_after >= ssp_before 

def test_partialWithdrawal_unbalancedDebtHigh(
    chain, gov, accounts, token, vault, strategy, user, strategist, lp_token ,amount, RELATIVE_APPROX, conf, router, whale
):
    #strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    swapPct = 0.015
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale)
    #setOracleShortPriceToLpPrice(strategy)
    strategy.setSlippageConfig(9900, 500, 500, False)

    strategyLoss = amount - strategy.estimatedTotalAssets()
    lossPercent = strategyLoss / amount

    preWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    chain.sleep(1)
    chain.mine(1)
    balBefore = token.balanceOf(user)
    ssp_before = strategySharePrice(strategy, vault)

    #give RPC a little break to stop it spzzing out 
    time.sleep(5)
    percentWithdrawn = 0.7

    withdrawAmt = int(amount * percentWithdrawn)
    vault.withdraw(withdrawAmt, user, 100, {'from' : user})
    balAfter = token.balanceOf(user)
    print("Withdraw Amount : ")
    print(balAfter - balBefore)
    assert (balAfter - balBefore) < int(percentWithdrawn * amount * (1 - lossPercent))
    
    # confirm the debt ratio wasn't impacted
    postWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Post Withdraw debt Ratio :  {0}'.format(postWithdrawDebtRatio))
    assert pytest.approx(preWithdrawDebtRatio, rel = 2e-3) == postWithdrawDebtRatio

    # confirm the loss was not felt disproportionately by the strategy - Strategy Share Price
    ssp_after = strategySharePrice(strategy, vault)
    assert ssp_after >= ssp_before


# Load up the vault with 2 strategies, deploy them with harvests and then withdraw 75% from the vault to test  withdrawing 100% from one of the strats is okay. 
def test_withdraw_all_from_multiple_strategies(
    gov, vault, strategy, token, user, amount, conf, chain, strategy_contract, strategist, StrategyInsurance, keeper, collatTarget, collatLimit
):
    # Deposit to the vault and harvest
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    vault.updateStrategyDebtRatio(strategy.address, 50_00, {"from": gov})

    new_strategy = strategist.deploy(strategy_contract, vault)
    newInsurance = strategist.deploy(StrategyInsurance, new_strategy)
    new_strategy.setKeeper(keeper)
    new_strategy.setInsurance(newInsurance, {'from': gov})
    new_strategy.setCollateralThresholds(collatTarget - 700, collatTarget, collatTarget + 700, collatLimit)
    vault.addStrategy(new_strategy, 50_00, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    strategy.harvest()
    chain.sleep(1)
    new_strategy.harvest()

    half = int(amount/2)

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=2e-3) == half
    assert pytest.approx(new_strategy.estimatedTotalAssets(), rel=2e-3) == half

    # Withdrawal
    vault.withdraw(amount, {"from": user})
    assert (
        pytest.approx(token.balanceOf(user), rel=1e-5) == user_balance_before
    )

def test_Sandwhich_High(
    chain, gov, accounts, token, vault, strategy, user, strategist, lp_token ,amount, RELATIVE_APPROX, conf, router, whale

):
    #strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    balBefore = token.balanceOf(user)

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # do a big swap to offset debt ratio's massively 
    swapPct = 0.7
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale)

    offsetEstimatedAssets  = strategy.estimatedTotalAssets()
    strategyLoss = amount - strategy.estimatedTotalAssets()
    lossPercent = strategyLoss / amount

    preWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))


    print("Try to rebalance - this should fail due to _testPriceSource()")
    with brownie.reverts():
        strategy.rebalanceDebt()
    assert preWithdrawDebtRatio == strategy.calcDebtRatio()

    chain.sleep(1)
    chain.mine(1)
    balBefore = token.balanceOf(user)

    #give RPC a little break to stop it spzzing out 
    time.sleep(5)
    percentWithdrawn = 0.7

    withdrawAmt = int(amount * percentWithdrawn)

    with brownie.reverts():     
        vault.withdraw({'from' : user}) 

def test_Sandwhich_Low(
    chain, gov, accounts, token, vault, strategy, user, strategist, lp_token ,amount, RELATIVE_APPROX, conf, router, shortWhale
):
    #strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    balBefore = token.balanceOf(user)

    vault.updateStrategyDebtRatio(strategy.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # do a big swap to offset debt ratio's massively 
    swapPct = 0.7
    offSetDebtRatioLow(strategy, lp_token, token, Contract, swapPct, router, shortWhale)

    print("Try to rebalance - this should fail due to _testPriceSource()")
    # for some reason brownie.reverts doesn't fail.... here although transaction reverts... 
    with brownie.reverts():     
        strategy.rebalanceDebt()

    offsetEstimatedAssets  = strategy.estimatedTotalAssets()
    strategyLoss = amount - strategy.estimatedTotalAssets()
    lossPercent = strategyLoss / amount

    preWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    chain.sleep(1)
    chain.mine(1)
    balBefore = token.balanceOf(user)

    #give RPC a little break to stop it spzzing out 
    time.sleep(5)
    percentWithdrawn = 0.7

    withdrawAmt = int(amount * percentWithdrawn)

    with brownie.reverts():     
        vault.withdraw({'from' : user}) 
