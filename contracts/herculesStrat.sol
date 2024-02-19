// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity ^0.6.12;

import { CoreStrategyAave } from "./CoreStrategyAave.sol";
import {ITorchPool} from "./interfaces/camelot/ITorchPool.sol";

abstract contract CoreStrategyHercules is CoreStrategyAave {

    uint256 public tokenId;

    ITorchPool public torchPool;

    // Farm-specific methods
    function countLpPooled() internal view override returns (uint256 _amount) {
        if (torchPool.balanceOf(address(this)) > 0) {
            (_amount, , , , , , , ) = torchPool.getStakingPosition(tokenId);
        } else {
            _amount = 0;
        }
    }

    function _depositLp() internal override { 
        uint256 _amount = wantShortLP.balanceOf(address(this));
        if (tokenId != uint256(0)) {
            torchPool.addToPosition(tokenId, _amount);
        } else {
            torchPool.createPosition(_amount, 0);
            /*
            // TO DO - how to handle X Torch 
            uint256 balanceXGrail = balanceOfXGrail();
            if (balanceXGrail > 0) {
                _stakeXGrail(balanceXGrail);
            }
            */
        }        
    }

    function _withdrawFarm(uint256 _amount) internal override {
        if (tokenId == uint256(0)) {
            return;
        }

        torchPool.withdrawFromPosition(tokenId, _amount);        
    }

}