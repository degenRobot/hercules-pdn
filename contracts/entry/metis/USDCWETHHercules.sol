// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "../../CoreStrategyAave.sol";
import "../../interfaces/IStakingRewards.sol";
import "../../interfaces/aave/IAaveOracle.sol";
import "../../interfaces/DragonLair.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

// Pool address -> 0x794a61358d6845594f94dc1db02a252b5b4814ad
// AAVE addresses: https://docs.aave.com/developers/deployed-contracts/v3-mainnet/polygon
// UniswapV2 Factory address: https://polygonscan.com/address/0x5757371414417b8c6caad45baef941abc7d3ab32

contract USDCWETHHercules is CoreStrategyAave {
    using SafeERC20 for IERC20;

    IERC20 quick;
    DragonLair dragonLair;

    constructor(address _vault)
        public
        CoreStrategyAave(
            _vault,
            CoreStrategyAaveConfig(
                0xEA32A96608495e54156Ae48931A7c20f0dcc1a21, // want -> USDC
                0x420000000000000000000000000000000000000A, // short -> WETH
                0x853Ee4b2A13f8a742d64C8F088bE7bA2131f670d, // wantShortLP -> USDC/WETH
                0xf28164A485B0B2C90639E47b0f377b4a438a16B1, // farmToken -> TORCH
                0x019ba0325f1988213D448b3472fA1cf8D07618d7, // farmTokenLp -> TORCH/WETH
                0xbB703E95348424FF9e94fbE4FB524f6d280331B8, // farmMasterChef -> IStakingReward
                0x625E7708f30cA75bfd92586e17077590C60eb4cD, // aToken
                0x0c84331e39d6658Cd6e6b9ba04736cC4c4734351, // variableDebtTOken
                0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb, // PoolAddressesProvider
                0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff, // router
                1e4 //mindeploy
            )
        )
    {}

    function _setup() internal override {
        weth = router.WETH(); // this is wMatic on quickswap 
        quick = IERC20(0x831753DD7087CaC61aB5644b308642cc1c33Dc13);
        dragonLair = DragonLair(0xf28164A485B0B2C90639E47b0f377b4a438a16B1);
        farmToken.safeApprove(address(dragonLair), uint256(-1));
        quick.safeApprove(address(router), uint256(-1));
    }

    function balancePendingHarvest() public view override returns (uint256) {
        uint256 dQuickPending =
            IStakingRewards(farmMasterChef).earned(address(this)).add(
                farmToken.balanceOf(address(this))
            );
        uint256 quickAmount =
            dragonLair.QUICKForDQUICK(dQuickPending).add(
                quick.balanceOf(address(this))
            );
        // uint256 harvestLP_A = _getHarvestInHarvestLp(); This does not work: dQuick is farmed, but we need to check for quick
        uint256 harvestLp_A = quick.balanceOf(address(farmTokenLP));
        uint256 shortLP_A = _getShortInHarvestLp();

        uint256 total_wmatic = quickAmount.mul(shortLP_A).div(harvestLp_A);


        (uint256 wantLP_B, uint256 shortLP_B) = getLpReserves();
        return total_wmatic.mul(wantLP_B).div(shortLP_B);
    }

    function _pendingRewards() internal view returns (uint256) {
        return 0; // TODO
    }

    function _depositLp() internal override {
        uint256 lpBalance = wantShortLP.balanceOf(address(this));

        IStakingRewards(farmMasterChef).stake(lpBalance);
    }

    function _sellHarvestWant() internal override {
        uint256 harvestBalance = farmToken.balanceOf(address(this));

        if (dragonLair.balanceOf(address(this)) > 0) {
            dragonLair.leave(harvestBalance);
        }

        uint256 quickBalance = quick.balanceOf(address(this));


        if (quickBalance > 0) {
            router.swapExactTokensForTokens(
                quickBalance,
                0,
                getTokenOutPath(address(quick), address(want)),
                address(this),
                now
            );
        }
        
    }

    function _withdrawFarm(uint256 _amount) internal override {
        if (_amount > 0) IStakingRewards(farmMasterChef).withdraw(_amount);
    }

    function claimHarvest() internal override {
        IStakingRewards(farmMasterChef).getReward();
    }

    function countLpPooled() internal view override returns (uint256) {
        return IStakingRewards(farmMasterChef).balanceOf(address(this));
    }
}
