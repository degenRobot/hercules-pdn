// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "../../CoreStrategyAave.sol";
import "../../interfaces/vector.sol";
import "../../interfaces/aave/IAaveOracle.sol";
import "../../interfaces/aave/IRewardController.sol";
import "../../interfaces/farm.sol";

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

// Pool address -> 0x794a61358d6845594f94dc1db02a252b5b4814ad
// AAVE addresses: https://docs.aave.com/developers/deployed-contracts/v3-mainnet/polygon
contract WAVAXUSDCVTX is CoreStrategyAave {
    using SafeERC20 for IERC20;

    // Find rewarder farmMasterChef -> masterVtx.addressToPoolInfo(farmMasterChef.stakingToken).rewarder
    address public rewarder = 0xb81941bd8E538167885a9C3e18fa2B799Df2e625;
    IVectorMainStaker public constant mainStaking =
        IVectorMainStaker(0x0E25c07748f727D6CCcD7D2711fD7bD13d13422d);
    address public incentives = 0x929EC64c34a17401F460460D4B9390518E5B473e; // Aave Rewards Controller

    constructor(address _vault)
        public
        CoreStrategyAave(
            _vault,
            CoreStrategyAaveConfig(
                0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7, // want -> WAVAX
                0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E, // short -> USDC
                0xf4003F4efBE8691B60249E6afbD307aBE7758adb, // wantShortLP -> USDC/AVAX
                0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd, // farmToken -> JOE
                0x454E67025631C065d3cFAD6d71E6892f74487a15, // farmTokenLp -> JOE/WAVAX
                0x423D0FE33031aA4456a17b150804aA57fc157d97, // farmMasterChef
                0x6d80113e533a2C0fe82EaBD35f1875DcEA89Ea97, // aToken
                0xFCCf3cAbbe80101232d343252614b6A3eE81C989, // variableDebtTOken
                0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb, // PoolAddressesProvider
                0x60aE616a2155Ee3d9A68541Ba4544862310933d4, // router
                1e14 // mindeploy
            )
        )
    {}

    function _setup() internal override {
        weth = router.WAVAX();
        IERC20(address(wantShortLP)).safeApprove(_getPoolHelper(), uint256(-1));
    }

    function updateRewarder() external onlyAuthorized {
        (, , , , rewarder, ) = mainStaking.getPoolInfo(address(wantShortLP));
    }

    function _approveHelper(address _helper, uint256 _amount) internal {
        if (
            IERC20(address(wantShortLP)).allowance(address(this), _helper) <
            _amount
        ) IERC20(address(wantShortLP)).safeApprove(_helper, uint256(-1));
    }

    function _getPoolHelper() internal view returns (address _poolHelper) {
        (, , , , , _poolHelper) = mainStaking.getPoolInfo(address(wantShortLP));
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
        address[] memory assets = new address[](2);
        assets[0] = address(aToken);
        assets[1] = address(debtToken);
        IAaveRewardController(incentives).claimAllRewardsToSelf(assets);
        IVectorPoolHelper(_getPoolHelper()).getReward();
    }

    function countLpPooled() internal view override returns (uint256) {
        return IVectorPoolHelper(_getPoolHelper()).balanceOf(address(this));
    }
}
