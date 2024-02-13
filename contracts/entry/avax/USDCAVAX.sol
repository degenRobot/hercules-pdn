// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "../../CoreStrategyAave.sol";
import "../../interfaces/IStakingDualRewards.sol";
import "../../interfaces/aave/IAaveOracle.sol";
import "../../interfaces/farm.sol";

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

// Pool address -> 0x794a61358d6845594f94dc1db02a252b5b4814ad
// AAVE addresses: https://docs.aave.com/developers/deployed-contracts/v3-mainnet/polygon
contract USDCWAVAXJOE is CoreStrategyAave {
    using SafeERC20 for IERC20;
    uint256 constant farmPid = 0;

    constructor(address _vault)
        public
        CoreStrategyAave(
            _vault,
            CoreStrategyAaveConfig(
                0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E, // want -> USDC
                0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7, // short -> WAVAX
                0xf4003F4efBE8691B60249E6afbD307aBE7758adb, // wantShortLP -> USDC/AVAX
                0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd, // farmToken -> JOE
                0x454E67025631C065d3cFAD6d71E6892f74487a15, // farmTokenLp -> JOE/WAVAX
                0x4483f0b6e2F5486D06958C20f8C39A7aBe87bf8F, // farmMasterChef -> IStakingDualRewards
                0x625E7708f30cA75bfd92586e17077590C60eb4cD, // aToken
                0x4a1c3aD6Ed28a636ee1751C69071f6be75DEb8B8, // variableDebtTOken
                0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb, // PoolAddressesProvider
                0x60aE616a2155Ee3d9A68541Ba4544862310933d4, // router
                1e4 //mindeploy
            )
        )
    {}

    function _setup() internal override {
        weth = router.WAVAX();
    }

    function _depositLp() internal override {
        uint256 lpBalance = wantShortLP.balanceOf(address(this));

        IFarmMasterChef(farmMasterChef).deposit(farmPid, lpBalance);
    }

    function _withdrawFarm(uint256 _amount) internal override {
        if (_amount > 0)
            IFarmMasterChef(farmMasterChef).withdraw(farmPid, _amount);
    }

    function claimHarvest() internal override {
        IFarmMasterChef(farmMasterChef).harvestFromMasterChef();
    }

    function countLpPooled() internal view override returns (uint256) {
        return
            IFarmMasterChef(farmMasterChef)
                .userInfo(farmPid, address(this))
                .amount;
    }
}
