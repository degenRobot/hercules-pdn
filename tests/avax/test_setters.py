import brownie
from brownie import interface, Contract, accounts, MockAaveOracle
import pytest
from brownie import USDCWAVAXVTX, USDTAVAXBQIVTX, WETHAVAXVTX, WAVAXUSDCVTX


def test_setter_rewarder(strategy, user, gov, deployed_vault, vault, conf):
    
    new_address = accounts[6]
    strat = USDCWAVAXVTX.at(strategy.address)
          
    mainStaker = interface.IVectorMainStaker(strat.mainStaking())
        
    mainStakerGov = accounts.at(mainStaker.owner(), force=True)
    mainStaker.setPoolRewarder(conf['lp_token'], new_address, {'from': mainStakerGov})

    with brownie.reverts():
        strat.updateRewarder({'from': user})
    strat.updateRewarder({'from': gov})
        
def test_setter_incentives(strategy, user, gov, deployed_vault, vault):
    if(not strategy.name().__contains__('Aave')):
        return
    new_address = accounts[6]
    strat = USDCWAVAXVTX.at(strategy.address)

    with brownie.reverts():
        strat.updateIncentives(new_address, {'from': user})
    strat.updateIncentives(new_address, {'from': gov})
        
