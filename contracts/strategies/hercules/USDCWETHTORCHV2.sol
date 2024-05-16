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

interface INFTHandler is IERC721Receiver {
    function onNFTHarvest(
        address operator,
        address to,
        uint256 tokenId,
        uint256 grailAmount,
        uint256 xGrailAmount
    ) external returns (bool);

    function onNFTAddToPosition(
        address operator,
        uint256 tokenId,
        uint256 lpAmount
    ) external returns (bool);

    function onNFTWithdraw(
        address operator,
        uint256 tokenId,
        uint256 lpAmount
    ) external returns (bool);
}

interface IGrailManager {
    function deposit(uint256 _amount) external;
    function withdraw(uint256 _amount) external;
    function harvest() external;
    function balance() external view returns (uint256 _amount);
    function getPendingRewards() external view returns (uint256, uint256);
    function pool() external view returns (address);
}

interface INFTPool {
    function getStakingPosition(uint256 _tokenId) external view returns (uint256 amount, uint256 amountWithMultiplier, uint256 startLockTime,
    uint256 lockDuration, uint256 lockMultiplier, uint256 rewardDebt,
    uint256 boostPoints, uint256 totalMultiplier);
    function lastTokenId() external view returns (uint256);
    function withdrawFromPosition(uint256 _tokenId, uint256 _amount) external;
}

interface INitroPool {
    function withdraw(uint256 _amount) external;

}


contract USDCWETHTORCHV2 is CoreStrategyAaveGamma, INFTHandler {
    using SafeERC20 for IERC20;
    uint256 public tokenId;
    address public nitroPool;
    address public nftPool;
    bytes4 private constant _ERC721_RECEIVED = 0x150b7a02;

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

        nftPool = 0x69E2BcCaFD7dbC4CBfB3aE2cCFe2bAC2101f668d;
        nitroPool = 0x7F404c937b0cE51773B32112467566E6549ebC0F;

        want.approve(address(gammaVault), type(uint256).max);        
        IERC20(address(short)).approve(address(gammaVault), type(uint256).max);   

        want.approve(address(depositPoint), type(uint256).max);        
        IERC20(address(short)).approve(address(depositPoint), type(uint256).max);   

    }

    function balancePendingHarvest() public view override returns (uint256) {
        return 0;
    }

    function _addToLP(uint256 _amountShort) internal override {
        if (tokenId != 0) {
            INitroPool(nitroPool).withdraw(tokenId);
        }

        (uint256 _amount0, uint256 _amount1) = _getAmountsIn(_amountShort);
        uint256[4] memory _minAmounts;
        // Check Max deposit amounts 
        // Deposit into Gamma Vault & Farm 
        depositPoint.deposit(algebraPool.token0(), algebraPool.token1(), _amount0, _amount1, address(gammaVault), _minAmounts, nftPool, 0);


    }


    function _depositLp() internal override {
        uint256 lpBalance = wantShortLP.balanceOf(address(this));
        //IGrailManager(grailManager).deposit(lpBalance);
    }

    function _withdrawFarm(uint256 _amount) internal override {
        if (_amount > 0)
            INitroPool(nitroPool).withdraw(_amount);
            INFTPool(nftPool).withdrawFromPosition(tokenId, _amount);
    }

    function claimHarvest() internal override {
        //IGrailManager(grailManager).harvest();
    }

    function countLpPooled() internal view override returns (uint256) {
        if (tokenId == 0) {
            return 0;
        }
        (uint256 _amount, , , , , , , ) = INFTPool(nftPool).getStakingPosition(tokenId);
        return _amount;
    }

    function setAave(address _oracle, address _pool) external onlyAuthorized {
        require(_oracle != address(0) && _pool != address(0), "invalid address");
        oracle = IAaveOracle(_oracle);
        pool = IPool(_pool);
        want.safeApprove(address(pool), type(uint256).max);
        short.safeApprove(address(pool), type(uint256).max);
        emit SetAave(_oracle, _pool);
    }

    function onERC721Received(
        address, /*_operator*/
        address _from,
        uint256 _tokenId,
        bytes calldata /*data*/
    ) external override returns (bytes4) {
        require(msg.sender == nftPool, "unexpected nft");
        tokenId = _tokenId;
        //nitroPool.approve(_from, _tokenId);
        return _ERC721_RECEIVED;
    }

    function onNFTHarvest(
        address _operator,
        address _to,
        uint256, /*tokenId*/
        uint256, /*grailAmount*/
        uint256 /*xGrailAmount*/
    ) external override returns (bool) {
        require(
            _operator == address(this),
            "caller is not the nft previous owner"
        );

        return true;
    }

    function onNFTAddToPosition(
        address _operator,
        uint256, /*tokenId*/
        uint256 /*lpAmount*/
    ) external override returns (bool) {
        require(
            _operator == address(this),
            "caller is not the nft previous owner"
        );
        return true;
    }

    function onNFTWithdraw(
        address _operator,
        uint256 _tokenId,
        uint256 /*lpAmount*/
    ) external override returns (bool) {
        require(msg.sender == nftPool, "unexpected nft");
        require(
            _operator == address(this),
            "NFTHandler: caller is not the nft previous owner"
        );
        /*
        if (!pool.exists(_tokenId)) {
            tokenId = uint256(0);
        }
        */
        return true;
    }

}
