// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity ^0.6.12;

import { CoreStrategyAave } from "./CoreStrategyAave.sol";
import {ITorchPool} from "./interfaces/camelot/ITorchPool.sol";
import {IXTorch} from "./interfaces/camelot/IXTorch.sol";
import {INFTHandler} from "./interfaces/camelot/INFTHandler.sol";

abstract contract CoreStrategyHercules is CoreStrategyAave, INFTHandler {

    uint256 public tokenId;
    address public yieldBooster;

    ITorchPool public torchPool;
    IXTorch public xTorch;

    bytes4 private constant _ERC721_RECEIVED = 0x150b7a02;


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

    function getPendingRewards() public view returns (uint256) {
        return torchPool.pendingRewards(tokenId);
    }



    function _stakeXTorch(uint256 _amount) internal {
        bytes memory usageData = abi.encode(address(torchPool), tokenId);
        uint256 _minAmount = 1000;
        if (_amount > _minAmount) {
            xTorch.allocate(yieldBooster, _amount, usageData);
        }    
        }

    function onERC721Received(
        address, /*_operator*/
        address _from,
        uint256 _tokenId,
        bytes calldata /*data*/
    ) external override returns (bytes4) {
        require(msg.sender == address(pool), "unexpected nft");
        require(_from == address(0), "unexpected operator");
        tokenId = _tokenId;
        torchPool.approve(_from, _tokenId);
        return _ERC721_RECEIVED;
    }

    function onNFTHarvest(
        address _operator,
        address _to,
        uint256, /*tokenId*/
        uint256, /*grailAmount*/
        uint256 /*xGrailAmount*/
    ) external override returns (bool) {
        require(
            _operator == address(this),
            "caller is not the nft previous owner"
        );

        return true;
    }

    function onNFTAddToPosition(
        address _operator,
        uint256, /*tokenId*/
        uint256 /*lpAmount*/
    ) external override returns (bool) {
        require(
            _operator == address(this),
            "caller is not the nft previous owner"
        );
        return true;
    }

    function onNFTWithdraw(
        address _operator,
        uint256 _tokenId,
        uint256 /*lpAmount*/
    ) external override returns (bool) {
        require(msg.sender == address(pool), "unexpected nft");
        require(
            _operator == address(this),
            "NFTHandler: caller is not the nft previous owner"
        );
        if (!torchPool.exists(_tokenId)) {
            tokenId = uint256(0);
        }
        return true;
    }


}