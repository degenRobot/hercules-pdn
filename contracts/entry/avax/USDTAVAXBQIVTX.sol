// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "../../CoreStrategyBenqi.sol";
import "../../interfaces/vector.sol";

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

contract USDTAVAXBQIVTX is CoreStrategyBenqi {
    IVectorMainStaker public constant mainStaking =
        IVectorMainStaker(0x0E25c07748f727D6CCcD7D2711fD7bD13d13422d);

    constructor(address _vault)
        public
        CoreStrategyBenqi(
            _vault,
            CoreStrategyBenqiConfig(
                0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7, // want
                0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7, // short
                0xbb4646a764358ee93c2a9c4a147d5aDEd527ab73, // wantShortLP
                0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd, // farmToken -> JOE
                0x454E67025631C065d3cFAD6d71E6892f74487a15, // farmTokenLp -> JOE/WAVAX
                0x423D0FE33031aA4456a17b150804aA57fc157d97, // farmMasterChef
                0xd8fcDa6ec4Bdc547C0827B8804e89aCd817d56EF, // cTokenLend
                0x5C0401e81Bc07Ca70fAD469b451682c0d747Ef1c, // cTokenBorrow
                0x8729438EB15e2C8B576fCc6AeCdA6A148776C0F5, // compToken
                0xE530dC2095Ef5653205CF5ea79F8979a7028065c, // compTokenLP
                0x486Af39519B4Dc9a7fCcd318217352830E8AD9b4, // comptroller
                0x60aE616a2155Ee3d9A68541Ba4544862310933d4, // router
                1e4 //mindeploy
            )
        )
    {
        oracle = new ScreamPriceOracle(
            address(comptroller),
            address(cTokenLend),
            address(cTokenBorrow)
        );
    }

    function _getPoolHelper() internal view returns (address _poolHelper) {
        (, , , , , _poolHelper) = mainStaking.getPoolInfo(address(wantShortLP));
    }

    function _approveHelper(address _helper, uint256 _amount) internal {
        if (
            IERC20(address(wantShortLP)).allowance(address(this), _helper) <
            _amount
        ) IERC20(address(wantShortLP)).safeApprove(_helper, uint256(-1));
    }

    function _depositLp() internal override {
        uint256 lpBalance = wantShortLP.balanceOf(address(this));
        address poolHelper = _getPoolHelper();
        _approveHelper(poolHelper, lpBalance);
        IVectorPoolHelper(poolHelper).deposit(lpBalance);
    }

    function _withdrawFarm(uint256 _amount) internal override {
        if (_amount > 0) {
            IVectorPoolHelper(_getPoolHelper()).withdraw(_amount);
        }
    }

    function claimHarvest() internal override {
        IVectorPoolHelper(_getPoolHelper()).getReward();
    }

    function countLpPooled() internal view override returns (uint256) {
        return IVectorPoolHelper(_getPoolHelper()).balanceOf(address(this));
    }
}
