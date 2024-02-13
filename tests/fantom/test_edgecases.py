import brownie
from brownie import interface, Contract, accounts, MockAaveOracle
import pytest
import time

ORACLE = '0xC466e3FeE82C6bdc2E17f2eaF2c6F1E91AD10FD3'
POOL_ADDRESS_PROVIDER = '0x6c793c628Fe2b480c5e6FB7957dDa4b9291F9c9b'


def steal(stealPercent, strategy_mock_oracle, token, chain, gov, user):
    steal = round(strategy_mock_oracle.estimatedTotalAssets() * stealPercent)
    strategy_mock_oracle.liquidatePositionAuth(steal, {'from': gov})
    token.transfer(user, strategy_mock_oracle.balanceOfWant(), {"from": accounts.at(strategy_mock_oracle, True)})
    chain.sleep(1)
    chain.mine(1)


def offSetDebtRatioLow(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, shortWhale):
    # use other AMM's LP to force some swaps 
    short = Contract(strategy_mock_oracle.short())
    swapAmtMax = short.balanceOf(lp_token)*swapPct
    swapAmt = min(swapAmtMax, short.balanceOf(shortWhale))
    print("Force Large Swap - to offset debt ratios")
    short.approve(router, 2**256-1, {"from": shortWhale})
    router.swapExactTokensForTokens(swapAmt, 0, [short, token], shortWhale, 2**256-1, {"from": shortWhale})
    

    

def offSetDebtRatioHigh(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, whale):
    short = Contract(strategy_mock_oracle.short())
    swapAmtMax = token.balanceOf(lp_token)*swapPct
    swapAmt = min(swapAmtMax, token.balanceOf(whale))
    print("Force Large Swap - to offset debt ratios")
    token.approve(router, 2**256-1, {"from": whale})
    router.swapExactTokensForTokens(swapAmt, 0, [token, short], whale, 2**256-1, {"from": whale})
    
def turnOffPriceOffsetCheck(strategy_mock_oracle, gov):
    strategy_mock_oracle.setSlippageConfig(9900, 1000, 1000, False, {'from' : gov})

def setOracleShortPriceToLpPrice(strategy_mock_oracle):
    short = Contract(strategy_mock_oracle.short())
    # Oracle should reflect the "new" price
    pool_address_provider = interface.IPoolAddressesProvider(POOL_ADDRESS_PROVIDER)
    oracle = MockAaveOracle.at(pool_address_provider.getPriceOracle())
    new_price = strategy_mock_oracle.getLpPrice()
    print("Oracle price before", oracle.getAssetPrice(short))
    """"
    oracle.setAssetPrice(short, new_price * 100)
    """
    print("Strategy Lp price", new_price)
    print("Oracle price", oracle.getAssetPrice(short))
    print("Strategy oracle price", strategy_mock_oracle.getOraclePrice())

def strategySharePrice(strategy_mock_oracle, vault):
    return strategy_mock_oracle.estimatedTotalAssets() / vault.strategies(strategy_mock_oracle)['totalDebt']

def test_lossy_withdrawal_partial(
    chain, gov, accounts, token, vault, strategy_mock_oracle, user, strategist, amount, RELATIVE_APPROX, conf
):
    # strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    # Steal from the strategy
    stealPercent = 0.005
    steal(stealPercent, strategy_mock_oracle, token, chain, gov, user)
    balBefore = token.balanceOf(user)

    # give RPC a little break to stop it spzzing out
    time.sleep(5)

    half = int(amount / 2)
    vault.withdraw(half, user, 100, {"from": user})
    balAfter = token.balanceOf(user)

    assert pytest.approx(balAfter - balBefore, rel=2e-3) == (half * (1 - stealPercent))

def test_partialWithdrawal_unbalancedDebtLow(
    chain, gov, accounts, token, vault, strategy_mock_oracle, user, strategist, lp_token ,amount, RELATIVE_APPROX, conf, router, shortWhale
):
    # strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    swapPct = 0.01
    # use other AMM's LP to force some swaps 
    offSetDebtRatioLow(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, shortWhale)
    turnOffPriceOffsetCheck(strategy_mock_oracle, gov)
    preWithdrawDebtRatio = strategy_mock_oracle.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    strategyLoss = amount - strategy_mock_oracle.estimatedTotalAssets()
    lossPercent = strategyLoss / amount

    chain.sleep(1)
    chain.mine(1)
    balBefore = token.balanceOf(user)
    ssp_before = strategySharePrice(strategy_mock_oracle, vault)

    # give RPC a little break to stop it spzzing out
    time.sleep(5)
    percentWithdrawn = 0.7

    withdrawAmt = int(amount * percentWithdrawn)
    vault.withdraw(withdrawAmt, user, 100, {"from": user})
    balAfter = token.balanceOf(user)
    print("Withdraw Amount : ")
    print(balAfter - balBefore)

    assert (balAfter - balBefore) < int(percentWithdrawn * amount * (1 - lossPercent))

    # confirm the debt ratio wasn't impacted
    postWithdrawDebtRatio = strategy_mock_oracle.calcDebtRatio()
    print('Post Withdraw debt Ratio :  {0}'.format(postWithdrawDebtRatio))
    assert pytest.approx(preWithdrawDebtRatio, rel = 2e-3) == postWithdrawDebtRatio

    # confirm the loss was not felt disproportionately by the strategy - Strategy Share Price
    ssp_after = strategySharePrice(strategy_mock_oracle, vault)
    assert ssp_after >= ssp_before 

def test_partialWithdrawal_unbalancedDebtHigh(
    chain, gov, accounts, token, vault, strategy_mock_oracle, user, strategist, lp_token ,amount, RELATIVE_APPROX, conf, router, whale
):
    # strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    swapPct = 0.015
    offSetDebtRatioHigh(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, whale)
    turnOffPriceOffsetCheck(strategy_mock_oracle, gov)

    strategyLoss = amount - strategy_mock_oracle.estimatedTotalAssets()
    lossPercent = strategyLoss / amount

    preWithdrawDebtRatio = strategy_mock_oracle.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    chain.sleep(1)
    chain.mine(1)
    balBefore = token.balanceOf(user)
    ssp_before = strategySharePrice(strategy_mock_oracle, vault)

    # give RPC a little break to stop it spzzing out
    time.sleep(5)
    percentWithdrawn = 0.7

    withdrawAmt = int(amount * percentWithdrawn)
    vault.withdraw(withdrawAmt, user, 100, {"from": user})
    balAfter = token.balanceOf(user)
    print("Withdraw Amount : ")
    print(balAfter - balBefore)
    assert (balAfter - balBefore) < int(percentWithdrawn * amount * (1 - lossPercent))

    # confirm the debt ratio wasn't impacted
    postWithdrawDebtRatio = strategy_mock_oracle.calcDebtRatio()
    print('Post Withdraw debt Ratio :  {0}'.format(postWithdrawDebtRatio))
    assert pytest.approx(preWithdrawDebtRatio, rel = 2e-3) == postWithdrawDebtRatio

    # confirm the loss was not felt disproportionately by the strategy - Strategy Share Price
    ssp_after = strategySharePrice(strategy_mock_oracle, vault)
    assert ssp_after >= ssp_before


# Load up the vault with 2 strategies, deploy them with harvests and then withdraw 75% from the vault to test  withdrawing 100% from one of the strats is okay.
def test_withdraw_all_from_multiple_strategies(
    gov, vault, strategy_mock_oracle, token, user, amount, conf, chain, strategy_contract, strategist, StrategyInsurance, keeper
):
    # Deposit to the vault and harvest
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 50_00, {"from": gov})

    new_strategy = strategist.deploy(strategy_contract, vault)
    newInsurance = strategist.deploy(StrategyInsurance, new_strategy)
    new_strategy.setKeeper(keeper)
    new_strategy.setInsurance(newInsurance, {'from': gov})
    vault.addStrategy(new_strategy, 50_00, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    strategy_mock_oracle.harvest()
    chain.sleep(1)
    new_strategy.harvest()

    half = int(amount / 2)

    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=2e-3) == half
    assert pytest.approx(new_strategy.estimatedTotalAssets(), rel=2e-3) == half

    # Withdrawal
    vault.withdraw(amount, {"from": user})
    assert pytest.approx(token.balanceOf(user), rel=1e-5) == user_balance_before


def test_Sandwhich_High(
    chain, gov, accounts, token, vault, strategy_mock_oracle, user, strategist, lp_token ,amount, RELATIVE_APPROX, conf, router, whale

):
    # strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    balBefore = token.balanceOf(user)

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # do a big swap to offset debt ratio's massively
    swapPct = 0.7
    offSetDebtRatioHigh(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, whale)

    offsetEstimatedAssets  = strategy_mock_oracle.estimatedTotalAssets()
    strategyLoss = amount - strategy_mock_oracle.estimatedTotalAssets()
    lossPercent = strategyLoss / amount

    preWithdrawDebtRatio = strategy_mock_oracle.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    print("Try to rebalance - this should fail due to _testPriceSource()")
    with brownie.reverts():
        strategy_mock_oracle.rebalanceDebt()
    assert preWithdrawDebtRatio == strategy_mock_oracle.calcDebtRatio()

    chain.sleep(1)
    chain.mine(1)
    balBefore = token.balanceOf(user)

    # give RPC a little break to stop it spzzing out
    time.sleep(5)
    percentWithdrawn = 0.7

    withdrawAmt = int(amount * percentWithdrawn)

    with brownie.reverts():
        vault.withdraw({"from": user})


def test_Sandwhich_Low(
    chain, gov, accounts, token, vault, strategy_mock_oracle, user, strategist, lp_token ,amount, RELATIVE_APPROX, conf, router, shortWhale
):
    # strategy.approveContracts({'from':gov})
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    balBefore = token.balanceOf(user)

    vault.updateStrategyDebtRatio(strategy_mock_oracle.address, 100_00, {"from": gov})
    chain.sleep(1)
    strategy_mock_oracle.harvest()
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # do a big swap to offset debt ratio's massively
    swapPct = 0.7
    offSetDebtRatioLow(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, shortWhale)

    print("Try to rebalance - this should fail due to _testPriceSource()")
    # for some reason brownie.reverts doesn't fail.... here although transaction reverts... 
    with brownie.reverts():     
        strategy_mock_oracle.rebalanceDebt()

    offsetEstimatedAssets  = strategy_mock_oracle.estimatedTotalAssets()
    strategyLoss = amount - strategy_mock_oracle.estimatedTotalAssets()
    lossPercent = strategyLoss / amount

    preWithdrawDebtRatio = strategy_mock_oracle.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    chain.sleep(1)
    chain.mine(1)
    balBefore = token.balanceOf(user)

    # give RPC a little break to stop it spzzing out
    time.sleep(5)
    percentWithdrawn = 0.7

    withdrawAmt = int(amount * percentWithdrawn)

    with brownie.reverts():
        vault.withdraw({"from": user})


def test_collat_rebalance_PriceOffset(chain, accounts, token, strategist, strategy_mock_initialized_vault, strategy_mock_oracle, user, conf, gov, lp_token, lp_whale, lp_farm, lp_price, pid, router, whale, shortWhale):
    # set low collateral and rebalance
    target = 4500
    strategy_mock_oracle.setCollateralThresholds(target-200, target, target+200, 7500)
    collatBefore = strategy_mock_oracle.calcCollateral()

    swapPct = 0.3
    offSetDebtRatioHigh(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, whale)
    
    # rebalance
    chain.sleep(1)
    chain.mine(1)
    
    strategy_mock_oracle.rebalanceCollateral()
    debtCollat = strategy_mock_oracle.calcCollateral()
    print('CollatRatio: {0}'.format(debtCollat))
    #assert pytest.approx(10000, rel=1e-3) == debtAfter

    # steal some LP

    # lp_token.transfer(strategy, 1000000, {'from' : lp_whale})

    offSetDebtRatioLow(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, shortWhale)
    # bring price back 
    # tx = strategy.liquidatePositionAuth(strategy.estimatedTotalAssets())

    # set collat ratio above current
