// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "../../CoreStrategyAaveGamma.sol";
import "../../interfaces/IStakingRewards.sol";
import "../../interfaces/aave/IAaveOracle.sol";

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

// Pool address -> 0x794a61358d6845594f94dc1db02a252b5b4814ad
// AAVE addresses: https://docs.aave.com/developers/deployed-contracts/v3-mainnet/polygon
// UniswapV2 Factory address: https://polygonscan.com/address/0x5757371414417b8c6caad45baef941abc7d3ab32

interface ITorchPool {

}

interface IXTorch {

}

contract USDCWETHHercules is CoreStrategyAaveGamma {
    using SafeERC20 for IERC20;

    IERC20 public torch;
    IXTorch public xTorch;
    ITorchPool public torchPool;
    IERC20 public metis;
    address public yieldBooster;

    // xMetis ??? (how do we want to handle this )

    constructor(address _vault)
        public
        CoreStrategyAaveGamma(_vault)
    {}

    function _setup() internal override {
        torch = IERC20(0x831753DD7087CaC61aB5644b308642cc1c33Dc13);
        yieldBooster = address(0);
        torchPool = ITorchPool(address(0));
        xTorch = IXTorch(address(0));
        torch.safeApprove(address(router), uint256(-1));
    }

    function balancePendingHarvest() public view override returns (uint256) {
        /*
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
        */
    }

    function _pendingRewards() internal view returns (uint256) {
        return 0; // TODO
    }



}
