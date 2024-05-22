import brownie
from brownie import interface, Contract, accounts
import pytest
import time 
from tests.helper import encode_function_data


def offSetDebtRatioLow(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, shortWhale):
    # use other AMM's LP to force some swaps 

    WHALEHAGOOOO = '0xaa30D6bba6285d0585722e2440Ff89E23EF68864'

    short = interface.IERC20(strategy_mock_oracle.short())
    swapAmtMax = short.balanceOf(lp_token)*swapPct
    swapAmt = min(swapAmtMax, short.balanceOf(shortWhale))
    print("Force Large Swap - to offset debt ratios")
    short.approve(router, 2**256-1, {"from": shortWhale})
    if router.address == '0x14679D1Da243B8c7d1A4c6d0523A2Ce614Ef027C' :
        camelotRouter = interface.ICamelotRouter(router.address)
        camelotRouter.swapExactTokensForTokensSupportingFeeOnTransferTokens(swapAmt, 0, [short, token], shortWhale, '0x0000000000000000000000000000000000000000' , 2**256-1, {"from": shortWhale})

    else : 
        router.swapExactTokensForTokens(swapAmt, 0, [short, token], shortWhale, 2**256-1, {"from": shortWhale})
    

    

def offSetDebtRatioHigh(strategy_mock_oracle, lp_token, token, Contract, swapPct, router, whale):
    short = interface.IERC20(strategy_mock_oracle.short())
    swapAmtMax = token.balanceOf(lp_token)*swapPct
    swapAmt = min(swapAmtMax, token.balanceOf(whale))
    print("Force Large Swap - to offset debt ratios")
    token.approve(router, 2**256-1, {"from": whale})
    if router.address == '0x14679D1Da243B8c7d1A4c6d0523A2Ce614Ef027C' :
        camelotRouter = interface.ICamelotRouter(router.address)
        camelotRouter.swapExactTokensForTokensSupportingFeeOnTransferTokens(swapAmt, 0, [token, short], whale, '0x0000000000000000000000000000000000000000' , 2**256-1, {"from": whale})
    else :
        router.swapExactTokensForTokens(swapAmt, 0, [token, short], whale, 2**256-1, {"from": whale})


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
    grail_manager_contract,
    grail_manager_proxy_contract,
    conf,
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    new_strategy = strategist.deploy(strategy_contract, vault)

    yieldBooster = '0xA4dEfAf0904529A1ffE04CC8A1eF3BC7d7F7b121'
    xGrail = '0xF192897fC39bF766F1011a858dE964457bcA5832'
    grailManager = grail_manager_contract.deploy(gov, new_strategy, new_strategy.want(), conf['lp_token'], conf['harvest_token'], xGrail, conf['lp_farm'], conf['router'], yieldBooster, {'from': gov})

    new_strategy.setGrailManager(grailManager, {'from' : strategist})

    # migrate to a new strategy
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
    shortWhale,
    grail_manager_contract,
    grail_manager_proxy_contract,
    conf,
):

    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # use other AMM's LP to force some swaps 

    print("Force Large Swap - to offset debt ratios")

    swapPct = 0.015

    offSetDebtRatioLow(strategy, lp_token, token, Contract, swapPct, router, shortWhale)
    preWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    new_strategy = strategist.deploy(strategy_contract, vault)
    
    yieldBooster = '0xA4dEfAf0904529A1ffE04CC8A1eF3BC7d7F7b121'
    xGrail = '0xF192897fC39bF766F1011a858dE964457bcA5832'
    grailManager = grail_manager_contract.deploy(gov, new_strategy, new_strategy.want(), conf['lp_token'], conf['harvest_token'], xGrail, conf['lp_farm'], conf['router'], yieldBooster, {'from': gov})

    new_strategy.setGrailManager(grailManager, {'from' : strategist})


    # migrate to a new strategy
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
    whale,
    grail_manager_contract,
    grail_manager_proxy_contract,
    conf,
):

    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # use other AMM's LP to force some swaps
    short = interface.IERC20(strategy.short())


    print("Force Large Swap - to offset debt ratios")
    swapPct = 0.015
    offSetDebtRatioHigh(strategy, lp_token, token, Contract, swapPct, router, whale)

    preWithdrawDebtRatio = strategy.calcDebtRatio()
    print('Pre Withdraw debt Ratio :  {0}'.format(preWithdrawDebtRatio))

    # migrate to a new strategy

    new_strategy = strategist.deploy(strategy_contract, vault)

    yieldBooster = '0xA4dEfAf0904529A1ffE04CC8A1eF3BC7d7F7b121'
    xGrail = '0xF192897fC39bF766F1011a858dE964457bcA5832'
    grailManager = grail_manager_contract.deploy(gov, new_strategy, new_strategy.want(), conf['lp_token'], conf['harvest_token'], xGrail, conf['lp_farm'], conf['router'], yieldBooster, {'from': gov})


    new_strategy.setGrailManager(grailManager, {'from' : strategist})

    vault.migrateStrategy(strategy, new_strategy, {"from": gov})
    # will be some loss so use rel = 2e-3 (due to forcing debt ratio away from 100%)
    assert (
        pytest.approx(new_strategy.estimatedTotalAssets(), rel=2e-3)
        == amount
    )

