// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.15;

import {
    SafeERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "./CoreStrategyAaveGamma.sol";
import "../../interfaces/aave/IAaveOracle.sol";
import "@openzeppelin/contracts/token/ERC721/IERC721Receiver.sol";


interface ITorchManager {
    function harvest() external;
    function addToLp(uint256 _amount0, uint256 _amount1) external;
    function withdrawLp() external;
    function countLpPooled() external view returns (uint256);

}

contract USDCWETHTORCHV2 is CoreStrategyAaveGamma {
    using SafeERC20 for IERC20;

    ITorchManager public torchManager;
    event SetAave(address oracle, address pool);

    constructor(address _vault)
        CoreStrategyAaveGamma(
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
        // gammaVault = IGammaVault(0xa6b3cea9E3D4b6f1BC5FA3fb1ec7d55A578473Ad);

        gammaVault = IGammaVault(0x343cA50235bd4dBefAcE13416EdB21FCB07f26a2);
        depositPoint = IUniProxy(0xD882a7AD21a6432B806622Ba5323716Fba5241A8);
        algebraPool = IAlgebraPool(0x35096c3cA17D12cBB78fA4262f3c6eff73ac9fFc);  
        clearance = IClearance(0xd359e08A60E2dDBFa1fc276eC11Ce7026642Ae71);
    }

    function balancePendingHarvest() public view override returns (uint256) {
        return 0;
    }

    function _addToLP(uint256 _amountShort) internal override {
        if (countLpPooled() > 0) {
            torchManager.withdrawLp();
        }

        (uint256 _amount0, uint256 _amount1) = _getAmountsIn(_amountShort);
        if (algebraPool.token0() == address(want)) {
            want.transfer(address(torchManager), _amount0);
            short.transfer(address(torchManager), _amount1);
        }
        else {
            want.transfer(address(torchManager), _amount1);
            short.transfer(address(torchManager), _amount0);
        }

        torchManager.addToLp(_amount0, _amount1);

    }




    function _withdrawAllPooled() internal override {
        // This should be amount of LP in Nitro Pool (skipped for now as we are not using Nitro Pool)
        if (countLpPooled() > 0) {
            torchManager.withdrawLp();
        }
    }

    function _removeAllLp() internal override {
        
    }

    function claimHarvest() internal override {
        torchManager.harvest();
    }

    function countLpPooled() internal view override returns (uint256) {
        
        // Return 0 if torchManager is not set
        if (address(torchManager) == address(0)) return 0;


        return torchManager.countLpPooled();
    }

    function setTorchManager(address _torchManager) external onlyAuthorized {
        require(_torchManager != address(0), "invalid address");
        torchManager = ITorchManager(_torchManager);
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
