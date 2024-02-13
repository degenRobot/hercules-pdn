// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "../../CoreStrategyAaveSolid.sol";
import "../../interfaces/aave/IAaveOracle.sol";
import "../../interfaces/IVelo.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

// Pool address -> 0x794a61358d6845594f94dc1db02a252b5b4814ad
// AAVE addresses: https://docs.aave.com/developers/deployed-contracts/v3-mainnet/polygon
contract USDCWETHVELO is CoreStrategyAaveSolidly {
    using SafeERC20 for IERC20;

    constructor(address _vault)
        public
        CoreStrategyAaveSolidly(
            _vault,
            CoreStrategyAaveConfig(
                0x7F5c764cBc14f9669B88837ca1490cCa17c31607, // want -> USDC
                0x4200000000000000000000000000000000000006, // short -> WETH
                0x79c912FEF520be002c2B6e57EC4324e260f38E50, // wantShortLP -> USDC/WETH
                0x3c8B650257cFb5f272f799F5e2b4e65093a11a05, // farmToken -> VELO
                0xe8537b6FF1039CB9eD0B71713f697DDbaDBb717d, // farmTokenLp -> VELO/USDC
                0xE2CEc8aB811B648bA7B1691Ce08d5E800Dd0a60a, // gauge
                0, // farmPid
                0x625E7708f30cA75bfd92586e17077590C60eb4cD, // aToken
                0x0c84331e39d6658Cd6e6b9ba04736cC4c4734351, // variableDebtTOken
                0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb, // PoolAddressesProvider
                0xa132DAB612dB5cB9fC9Ac426A0Cc215A3423F9c9, // router
                1e4 //mindeploy
            )
        )
    {}

    function balancePendingHarvest() public view override returns (uint256) {
        uint256 pending =
            IGauge(farmMasterChef)
                .earned(address(farmToken), address(this))
                .add(farmToken.balanceOf(address(this)));
        // uint256 harvestLP_A = _getHarvestInHarvestLp(); This does not work: dQuick is farmed, but we need to check for quick
        uint256 harvestLp_A = farmToken.balanceOf(address(farmTokenLP));
        uint256 harvestLp_want = want.balanceOf(address(farmTokenLP));
        return pending.mul(harvestLp_want).div(harvestLp_A);
    }

    function _farmPendingRewards(uint256 _pid, address _user)
        internal
        view
        override
        returns (uint256)
    {
        return 0; // Implemented in balancePendingHarvest
    }

    function _depositLp() internal override {
        uint256 lpBalance = wantShortLP.balanceOf(address(this));

        IGauge(farmMasterChef).depositAll(farmPid);
    }

    function _withdrawFarm(uint256 _amount) internal override {
        if (_amount > 0) IGauge(farmMasterChef).withdraw(uint256(_amount));
    }

    function claimHarvest() internal override {
        address[] memory tokens = new address[](1);
        tokens[0] = address(farmToken);
        IGauge(farmMasterChef).getReward(address(this), tokens);
    }

    function countLpPooled() internal view override returns (uint256) {
        return IGauge(farmMasterChef).balanceOf(address(this));
    }
}
