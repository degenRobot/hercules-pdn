import brownie
from brownie import interface, Contract, accounts, MockAaveOracle
import pytest
import time 

def test_claim_x_assets(
        chain, accounts, gov, token, vault, strategy, torch_manager ,user, strategist, amount, RELATIVE_APPROX, conf
) : 

    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    #assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount


    xMetis = interface.IXMetis('0xcA042eA7E9AA901C85d5afA5247a79E935dB4996')
    xTorch = interface.IXMetis('0xF192897fC39bF766F1011a858dE964457bcA5832')

    chain.sleep(3600 * 6)  # we want to earn some farming rewards & test 
    chain.mine(1)

    strategy.harvest()


    ### Check if TorchManager has some tracked redemptions 

    assert xMetis.getUserRedeem(torch_manager, 0) > 0 
    assert xTorch.getUserRedeem(torch_manager, 0) > 0

    """
    function userRedeems(address user, uint256 index) external view returns (
        uint256 grailAmount,// GRAIL amount to receive when vesting has ended
        uint256 xGrailAmount, // xGRAIL amount to redeem
        uint256 endTime,
        address dividendsAddress,
        uint256 dividendsAllocation // Share of redeeming xGRAIL to allocate to the Dividends Usage contract
    );
    """

    (redeemAmount, xRedeemAmt, redeemTime, div, div1) = xMetis.userRedeems(torch_manager, 0)
    print("Metis Redeem: {0} {1} {2}".format(redeemAmount, xRedeemAmt, redeemTime))

    (redeemAmount, xRedeemAmt, redeemTime, div, div1) = xTorch.userRedeems(torch_manager, 0)
    print("Torch Redeem: {0} {1} {2}".format(redeemAmount, xRedeemAmt, redeemTime))


    minRedeemDuration = xMetis.minRedeemDuration()

    chain.sleep(minRedeemDuration - 10)
    chain.mine(1)

    strategy.harvest()

    assert xMetis.getUserRedeemsLength(torch_manager) == 2
    assert xTorch.getUserRedeemsLength(torch_manager) == 2

    chain.sleep(minRedeemDuration)
    chain.mine(1)

    # we should now be able to finalize the first redemption

    strategy.harvest()

    #assert False

    #assert xMetis.getUserRedeemsLength(torch_manager) == 2
    assert xTorch.getUserRedeemsLength(torch_manager) == 2  
    print("Post Harvest Check - should be diff amounts")
    (redeemAmount, xRedeemAmt, redeemTime, div, div1) = xMetis.userRedeems(torch_manager, 0)
    print("Metis Redeem: {0} {1} {2}".format(redeemAmount, xRedeemAmt, redeemTime))
    (redeemAmount, xRedeemAmt, redeemTime, div, div1) = xTorch.userRedeems(torch_manager, 0)
    print("Torch Redeem: {0} {1} {2}".format(redeemAmount, xRedeemAmt, redeemTime))

    metis = interface.IERC20(conf['wmetis'])
    torch = interface.IERC20(conf['harvest_token'])

    assert False


def test_profitable_harvest_torch(
    chain, accounts, gov, token, vault, strategy, torch_manager ,user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    #assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    before_pps = vault.pricePerShare()

    # Use a whale of the harvest token to send
    harvest = interface.ERC20(conf['harvest_token'])
    harvestWhale = accounts.at(conf['harvest_token_whale'], True)
    sendAmount = round((0.05 * vault.totalAssets() / conf['harvest_token_price']))
    print('Send amount: {0}'.format(sendAmount))
    print('harvestWhale balance: {0}'.format(harvest.balanceOf(harvestWhale)))
    harvest.transfer(torch_manager, sendAmount, {'from': harvestWhale})

    # Harvest 2: Realize profit
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault

    print("Profit: {0}".format(profit))

    assert strategy.estimatedTotalAssets() + profit > amount
    assert vault.pricePerShare() > before_pps



def test_profitable_harvest_metis(
    chain, accounts, gov, token, vault, strategy, torch_manager ,user, strategist, amount, RELATIVE_APPROX, conf
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    #assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    before_pps = vault.pricePerShare()

    # Use a whale of the harvest token to send
    harvest = interface.ERC20(conf['wmetis'])
    harvestWhale = accounts.at('0xbD718c67cD1e2f7FBe22d47bE21036cD647C7714', True)
    sendAmount = round((0.05 * vault.totalAssets() / conf['metis_price']))
    print('Send amount: {0}'.format(sendAmount))
    print('harvestWhale balance: {0}'.format(harvest.balanceOf(harvestWhale)))
    harvest.transfer(torch_manager, sendAmount, {'from': harvestWhale})

    # Harvest 2: Realize profit
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault

    print("Profit: {0}".format(profit))

    assert strategy.estimatedTotalAssets() + profit > amount
    assert vault.pricePerShare() > before_pps


