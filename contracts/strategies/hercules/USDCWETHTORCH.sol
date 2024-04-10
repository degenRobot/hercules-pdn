// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.15;

import {
    SafeERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "./CoreStrategyAaveTorch.sol";
import "../../interfaces/aave/IAaveOracle.sol";

interface IGrailManager {
    function deposit(uint256 _amount) external;
    function withdraw(uint256 _amount) external;
    function harvest() external;
    function balance() external view returns (uint256 _amount);
    function getPendingRewards() external view returns (uint256, uint256);
}


contract USDCWETHTORCH is CoreStrategyAaveTorch {
    using SafeERC20 for IERC20;
    uint256 constant farmPid = 0;

    event SetGrailManager(address grailManager);
    event SetAave(address oracle, address pool);

    constructor(address _vault)
        CoreStrategyAaveTorch(
            _vault,
            CoreStrategyAaveConfig(
                0xEA32A96608495e54156Ae48931A7c20f0dcc1a21, // want -> USDC
                0x420000000000000000000000000000000000000A, // short -> WETH
                0x4C10a0E5fc4a6eDe720dEcdAD99B281076EAC0fA, // wantShortLP -> USDC/WETH
                0x885C8AEC5867571582545F894A5906971dB9bf27, // aToken
                0x8Bb19e3DD277a73D4A95EE434F14cE4B92898421, // variableDebtTOken
                0xB9FABd7500B2C6781c35Dd48d54f81fc2299D7AF, // PoolAddressesProvider
                0x14679D1Da243B8c7d1A4c6d0523A2Ce614Ef027C, // router
                1e4 //mindeploy
            )
        )
    {}

    function _setup() internal override {
        weth = 0x75cb093E4D61d2A2e65D8e0BBb01DE8d89b53481;
    }

    function balancePendingHarvest() public view override returns (uint256) {
        (,uint256 grailRewards) = IGrailManager(grailManager).getPendingRewards();
        return grailRewards;
    }

    function _depositLp() internal override {
        uint256 lpBalance = wantShortLP.balanceOf(address(this));
        IGrailManager(grailManager).deposit(lpBalance);
    }

    function _withdrawFarm(uint256 _amount) internal override {
        if (_amount > 0)
            IGrailManager(grailManager).withdraw(_amount);
    }

    function claimHarvest() internal override {
        IGrailManager(grailManager).harvest();
    }

    function countLpPooled() internal view override returns (uint256) {
        return IGrailManager(grailManager).balance();
    }

    function setGrailManager(address _grailManager) external onlyAuthorized {
        grailManager = _grailManager;
        IERC20(address(wantShortLP)).safeApprove(_grailManager, type(uint256).max);
        emit SetGrailManager(_grailManager);
    }

    function setAave(address _oracle, address _pool) external onlyAuthorized {
        require(_oracle != address(0) && _pool != address(0), "invalid address");
        oracle = IAaveOracle(_oracle);
        pool = IPool(_pool);
        want.safeApprove(address(pool), type(uint256).max);
        short.safeApprove(address(pool), type(uint256).max);
        emit SetAave(_oracle, _pool);
    }
}
