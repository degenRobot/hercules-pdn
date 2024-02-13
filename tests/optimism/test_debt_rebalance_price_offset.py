from _pytest.fixtures import fixture
import brownie
from brownie import Contract, interface, accounts, StrategyInsurance
import pytest

POOL = '0x794a61358D6845594F94dc1DB02A252b5b4814aD' 
want = '0x7F5c764cBc14f9669B88837ca1490cCa17c31607' # USDC
ORACLE = '0xD81eb3728a631871a7eBBaD631b5f424909f0c77'

POOL_ADDRESS_PROVIDER = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'

def farmWithdraw(lp_farm, pid, strategy, amount, conf):
    
    auth = accounts.at(strategy, True)
    router = conf['router']
    # if VELO use IVelo
    if router == '0xa132DAB612dB5cB9fC9Ac426A0Cc215A3423F9c9' :
        lp_farm.withdraw(amount, {'from' : auth})
    else : 
        lp_farm.withdraw(pid, amount, auth, {'from': auth})

        
@pytest.fixture
def short(strategy):
    assert Contract(strategy.short())


"""
def run_debt_rebalance_price_offset(price_offset, accounts, strategy_mock_oracle, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle):
    # Edit the comp price oracle prices
    pool_address_provider = interface.IPoolAddressesProvider(POOL_ADDRESS_PROVIDER)
    oracle = MockAaveOracle.at(pool_address_provider.getPriceOracle())
    # Set the new one
    old_price = oracle.getAssetPrice(want)
    new_price = int(old_price * price_offset)
    oracle.setAssetPrice(want, new_price)
    # assert Contract(comp.oracle()).getUnderlyingPrice(cTokenLend) == new_price

    # Change the debt ratio to ~95% and rebalance
    sendAmount = round(strategy_mock_oracle.balanceLp() * (1/.95 - 1) / lp_price)
    lp_token.transfer(strategy_mock_oracle, sendAmount, {'from': lp_whale})
    print('Send amount: {0}'.format(sendAmount))
    print('debt Ratio:  {0}'.format(strategy_mock_oracle.calcDebtRatio()))

    debtRatio = strategy_mock_oracle.calcDebtRatio()
    collatRatio = strategy_mock_oracle.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    # collat will be off due to changing the price after the first harvest
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(9500, rel=1e-3) == debtRatio

    # The first one should fail because of the priceOffsetTest
    with brownie.reverts():
        strategy_mock_oracle.rebalanceDebt()

    # Rebalance Debt  and check it's back to the target
    strategy_mock_oracle.setSlippageConfig(9900, 500, 500, False)
    strategy_mock_oracle.rebalanceDebt()
    debtRatio = strategy_mock_oracle.calcDebtRatio()
    print('debtRatio:   {0}'.format(debtRatio))
    assert pytest.approx(10000, rel=1e-3) == debtRatio
    assert pytest.approx(6000, rel=1e-2) == strategy_mock_oracle.calcCollateral()

    # Change the debt ratio to ~40% and rebalance
    # sendAmount = round(strategy.balanceLpInShort() * (1/.4 - 1))
    sendAmount = round(strategy_mock_oracle.balanceLp() * (1/.4 - 1) / lp_price)
    lp_token.transfer(strategy_mock_oracle, sendAmount, {'from': lp_whale})
    print('Send amount: {0}'.format(sendAmount))
    print('debt Ratio:  {0}'.format(strategy_mock_oracle.calcDebtRatio()))

    debtRatio = strategy_mock_oracle.calcDebtRatio()
    collatRatio = strategy_mock_oracle.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(4000, rel=1e-2) == debtRatio
    assert pytest.approx(6000, rel=2e-2) == collatRatio

    # Rebalance Debt  and check it's back to the target
    strategy_mock_oracle.rebalanceDebt()
    debtRatio = strategy_mock_oracle.calcDebtRatio()
    print('debtRatio:   {0}'.format(debtRatio))
    assert pytest.approx(10000, rel=1e-3) == debtRatio 
    assert pytest.approx(6000, rel=1e-2) == strategy_mock_oracle.calcCollateral()

    # Change the debt ratio to ~105% and rebalance - steal some lp from the strat
    sendAmount = round(strategy_mock_oracle.balanceLp() * 0.05/1.05 / lp_price)
    auth = accounts.at(strategy_mock_oracle, True)
    farmWithdraw(lp_farm, pid, strategy_mock_oracle, sendAmount)
    lp_token.transfer(user, sendAmount, {'from': auth})

    print('Send amount: {0}'.format(sendAmount))
    print('debt Ratio:  {0}'.format(strategy_mock_oracle.calcDebtRatio()))

    debtRatio = strategy_mock_oracle.calcDebtRatio()
    collatRatio = strategy_mock_oracle.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(10500, rel=2e-3) == debtRatio
    assert pytest.approx(6000, rel=2e-2) == collatRatio

    # Rebalance Debt  and check it's back to the target
    print("Debt before: ", strategy_mock_oracle.balanceDebtInShort())
    print("Balance short before: ", strategy_mock_oracle.balanceShort())
    strategy_mock_oracle.rebalanceDebt()
    print("Debt after: ", strategy_mock_oracle.balanceDebtInShort())
    print("Balance short after: ", strategy_mock_oracle.balanceShort())

    debtRatio = strategy_mock_oracle.calcDebtRatio()
    print('debtRatio:   {0}'.format(debtRatio))
    assert pytest.approx(10000, rel=1e-3) == debtRatio
    assert pytest.approx(6000, rel=1e-2) == strategy_mock_oracle.calcCollateral()

    # Change the debt ratio to ~150% and rebalance - steal some lp from the strat
    # sendAmount = round(strategy.balanceLpInShort()*(1 - 1/1.50))
    sendAmount = round(strategy_mock_oracle.balanceLp() * 0.5/1.50 / lp_price)
    auth = accounts.at(strategy_mock_oracle, True)
    farmWithdraw(lp_farm, pid, strategy_mock_oracle, sendAmount)
    lp_token.transfer(user, sendAmount, {'from': auth})

    print('Send amount: {0}'.format(sendAmount))
    print('debt Ratio:  {0}'.format(strategy_mock_oracle.calcDebtRatio()))

    debtRatio = strategy_mock_oracle.calcDebtRatio()
    collatRatio = strategy_mock_oracle.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(collatRatio))
    assert pytest.approx(15000, rel=1e-2) == debtRatio
    assert pytest.approx(6000, rel=2e-2) == collatRatio

    # Rebalance Debt  and check it's back to the target
    strategy_mock_oracle.rebalanceDebt()
    debtRatio = strategy_mock_oracle.calcDebtRatio()
    print('debtRatio:   {0}'.format(debtRatio))
    assert pytest.approx(10000, rel=2e-3) == debtRatio
    assert pytest.approx(6000, rel=1e-2) == strategy_mock_oracle.calcCollateral()

    # resets the price for other test 
    oracle.setAssetPrice(want, 0)
 

def run_debt_rebalance_partial_price_offset(price_offset, accounts, strategy, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle):
    # strategy = test_strategy
    strategy.setDebtThresholds(9800, 10200, 5000)

    # Change oracle price
    # Edit the comp price oracle prices
    pool_address_provider = interface.IPoolAddressesProvider(POOL_ADDRESS_PROVIDER)
    oracle = MockAaveOracle.at(pool_address_provider.getPriceOracle())
    # Set the new one
    old_price = oracle.getAssetPrice(want)
    new_price = int(old_price * price_offset)
    oracle.setAssetPrice(want, new_price)

    # Change the debt ratio to ~95% and rebalance
    sendAmount = round(strategy.balanceLpInShort()*(1/.95 - 1))
    lp_token.transfer(strategy, sendAmount, {'from': lp_whale})
    print('Send amount: {0}'.format(sendAmount))
    print('debt Ratio:  {0}'.format(strategy.calcDebtRatio()))

    debtRatio = strategy.calcDebtRatio()
    print('debtRatio:   {0}'.format(debtRatio))
    print('collatRatio: {0}'.format(strategy.calcCollateral()))
    assert pytest.approx(9500, rel=1e-3) == debtRatio

    # The first one should fail because of the priceOffsetTest
    with brownie.reverts():
        strategy.rebalanceDebt()

    # Rebalance Debt  and check it's back to the target
    strategy.setSlippageConfig(9900, 500, 500, False)
    strategy.rebalanceDebt()
    debtRatio = strategy.calcDebtRatio()
    print('debtRatio:   {0}'.format(debtRatio))
    assert pytest.approx(9750, rel=4e-3) == debtRatio
    assert pytest.approx(6000, rel=1e-2) == strategy.calcCollateral()

    # assert False
    # rebalance the whole way now
    strategy.setDebtThresholds(9800, 10200, 10000)
    strategy.rebalanceDebt()
    assert pytest.approx(10000, rel=1e-3) == strategy.calcDebtRatio()

    strategy.setDebtThresholds(9800, 10200, 5000)
    # Change the debt ratio to ~105% and rebalance - steal some lp from the strat
    sendAmount = round(strategy.balanceLp() * 0.05/1.05 / lp_price)
    auth = accounts.at(strategy, True)
    farmWithdraw(lp_farm, pid, strategy, sendAmount)
    lp_token.transfer(user, sendAmount, {'from': auth})

    print('Send amount: {0}'.format(sendAmount))
    print('debt Ratio:  {0}'.format(strategy.calcDebtRatio()))
    debtRatio = strategy.calcDebtRatio()
    collatRatio = strategy.calcCollateral()
    print('debtRatio:   {0}'.format(debtRatio))
    print('CollatRatio: {0}'.format(collatRatio))
    assert pytest.approx(10500, rel=1e-3) == debtRatio
    assert pytest.approx(6000, rel=2e-2) == collatRatio

    # Rebalance Debt  and check it's back to the target
    strategy.rebalanceDebt()
    collatRatio = strategy.calcCollateral()
    debtRatio = strategy.calcDebtRatio()
    print('debtRatio:   {0}'.format(debtRatio))
    print('CollatRatio: {0}'.format(collatRatio))
    assert pytest.approx(10250, rel=4e-3) == debtRatio
    assert pytest.approx(6000, rel=1e-2) == collatRatio

    # return the price for other test
    oracle.setAssetPrice(want, 0)



def test_debt_rebalance_price_offset_high(accounts, strategy_mock_oracle, strategy_mock_initialized_vault, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle):
    run_debt_rebalance_price_offset(1.1, accounts, strategy_mock_oracle, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle)

def test_debt_rebalance_price_offset_low(accounts, strategy_mock_oracle, strategy_mock_initialized_vault, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle):
    run_debt_rebalance_price_offset(0.9, accounts, strategy_mock_oracle, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle)

def test_debt_rebalance_partial_price_offset_high(accounts, strategy_mock_oracle, strategy_mock_initialized_vault, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle):
    run_debt_rebalance_partial_price_offset(1.1, accounts, strategy_mock_oracle, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle)

def test_debt_rebalance_partial_price_offset_low(accounts, strategy_mock_oracle, strategy_mock_initialized_vault, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle):
    run_debt_rebalance_partial_price_offset(0.9, accounts, strategy_mock_oracle, user, lp_token, lp_whale, lp_farm, lp_price, pid, MockAaveOracle)

"""