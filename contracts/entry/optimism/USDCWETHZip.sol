// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "../../CoreStrategyAave.sol";
import "../../interfaces/IStakingDualRewards.sol";
import "../../interfaces/aave/IAaveOracle.sol";
import "../../interfaces/IZipRewards.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

// Pool address -> 0x794a61358d6845594f94dc1db02a252b5b4814ad
// AAVE addresses: https://docs.aave.com/developers/deployed-contracts/v3-mainnet/polygon
contract USDCWETHZIP is CoreStrategyAave {
    using SafeERC20 for IERC20;
    uint256 constant farmPid = 0;

    constructor(address _vault)
        public
        CoreStrategyAave(
            _vault,
            CoreStrategyAaveConfig(
                0x7F5c764cBc14f9669B88837ca1490cCa17c31607, // want -> USDC
                0x4200000000000000000000000000000000000006, // short -> WETH
                0x1A981dAa7967C66C3356Ad044979BC82E4a478b9, // wantShortLP -> USDC/WETH
                0xFA436399d0458Dbe8aB890c3441256E3E09022a8, // farmToken -> ZIP
                0xD7F6ECF4371eddBd60C1080BfAEc3d1d60D415d0, // farmTokenLp -> ZIP/WETH
                0x1e2F8e5f94f366eF5Dc041233c0738b1c1C2Cb0c, // farmMasterChef -> IStakingDualRewards
                0x625E7708f30cA75bfd92586e17077590C60eb4cD, // aToken
                0x0c84331e39d6658Cd6e6b9ba04736cC4c4734351, // variableDebtTOken
                0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb, // PoolAddressesProvider
                0xE6Df0BB08e5A97b40B21950a0A51b94c4DbA0Ff6, // router
                1e4 //mindeploy
            )
        )
    {}

    function balancePendingHarvest() public view override returns (uint256) {
        uint256 pending =
            IZipRewards(farmMasterChef)
                .pendingReward(farmPid, address(this))
                .add(farmToken.balanceOf(address(this)));
        uint256 harvestLp_A = farmToken.balanceOf(address(farmTokenLP));
        uint256 shortLP_A = _getShortInHarvestLp();
        uint256 totalShort = pending.mul(shortLP_A).div(harvestLp_A);
        (uint256 wantLP_B, uint256 shortLP_B) = getLpReserves();
        return totalShort.mul(wantLP_B).div(shortLP_B);
    }

    function _pendingRewards() internal view returns (uint256) {
        return 0; // TODO
    }

    function _depositLp() internal override {
        uint256 lpBalance = wantShortLP.balanceOf(address(this));

        IZipRewards(farmMasterChef).deposit(
            farmPid,
            uint128(lpBalance),
            address(this)
        );
    }

    function _withdrawFarm(uint256 _amount) internal override {
        if (_amount > 0)
            IZipRewards(farmMasterChef).withdraw(
                farmPid,
                uint128(_amount),
                address(this)
            );
    }

    function claimHarvest() internal override {
        IZipRewards(farmMasterChef).harvest(farmPid, address(this));
    }

    function countLpPooled() internal view override returns (uint256) {
        return
            IZipRewards(farmMasterChef).userInfo(farmPid, address(this)).amount;
    }
}
