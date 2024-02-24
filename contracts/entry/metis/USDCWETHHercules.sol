// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "../../CoreStrategyHercules.sol";
import {CoreStrategyAaveConfig} from "../../CoreStrategyAave.sol";
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

contract USDCWETHHercules is CoreStrategyHercules {
    using SafeERC20 for IERC20;

    IERC20 torch;
    IERC20 metis;

    // xMetis ??? (how do we want to handle this )

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
                0x885c8aec5867571582545f894a5906971db9bf27, // aToken
                0x8Bb19e3DD277a73D4A95EE434F14cE4B92898421, // variableDebtTOken
                0xB9FABd7500B2C6781c35Dd48d54f81fc2299D7AF, // PoolAddressesProvider
                0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff, // router
                1e4 //mindeploy
            )
        )
    {}

    function _setup() internal override {
        weth = router.WETH(); 
        torch = IERC20(0x831753DD7087CaC61aB5644b308642cc1c33Dc13);
        yieldBooster = address(0);
        torchPool = ITorchPool(address(0));
        xTorch = IXTorch(address(0));
        //farmToken.safeApprove(address(dragonLair), uint256(-1));
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


    function _sellHarvestWant() internal override {
        //uint256 harvestBalance = farmToken.balanceOf(address(this));
        uint256 torchBalance = torch.balanceOf(address(this));
        uint256 metisBalance = metis.balanceOf(address(this));

        if (torchBalance > 0) {
            router.swapExactTokensForTokensSupportingFeeOnTransferTokens(
                torchBalance,
                0,
                getTokenOutPath(address(torch), address(want)),
                address(this),
                address(this),
                now
            );
        }

        if (metisBalance > 0 ) {
            router.swapExactTokensForTokensSupportingFeeOnTransferTokens(
                metisBalance,
                0,
                getTokenOutPath(address(metis), address(want)),
                address(this),
                address(this),
                now
            );            
        }
        
    }

}
