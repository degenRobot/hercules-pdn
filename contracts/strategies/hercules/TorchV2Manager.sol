
// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.15;

import "@openzeppelin/contracts/token/ERC721/IERC721Receiver.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {
    SafeERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "../../libraries/proxy/utils/Initializable.sol";
import "../../libraries/proxy/utils/UUPSUpgradeable.sol";
import "../../interfaces/camelot/ICamelotRouter.sol";


import "../../interfaces/camelot/ICamelotRouter.sol";

import {IGammaVault} from "../../interfaces/gamma/IGammaVault.sol";
import {IUniProxy} from "../../interfaces/gamma/IUniProxy.sol";
import {IClearance} from "../../interfaces/gamma/IClearance.sol";
import {IAlgebraPool} from "../../interfaces/camelot/IAlgebraPool.sol";


interface IStrategy {
    function want () external view returns (address);
    function short() external view returns (address);
 
}

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

interface INFTPoolTorch {
    function getStakingPosition(uint256 _tokenId) external view returns (uint256 amount, uint256 amountWithMultiplier, uint256 startLockTime,
    uint256 lockDuration, uint256 lockMultiplier, uint256 rewardDebt,
    uint256 boostPoints, uint256 totalMultiplier);
    function lastTokenId() external view returns (uint256);
    function withdrawFromPosition(uint256 _tokenId, uint256 _amount) external;
    function approve(address to, uint256 tokenId) external;
    function safeTransferFrom(address from, address to, uint256 tokenId, bytes memory data) external;
    function ownerOf(uint256 tokenId) external view returns (address);
}

interface INitroPool {
    function withdraw(uint256 _amount) external;
    function harvest() external;
    function tokenIdOwner(uint256 _tokenId) external view returns (address);

}

interface IXMetis {
    function balanceOf(address owner) external view returns (uint256);
    function minRedeemDuration() external view returns (uint256);
    function redeem(uint256 xMetisAmount, uint256 duration) external;
    function getUserRedeemsLength(address user) external view returns (uint256);
    function userRedeems(address user, uint256 index) external view returns (
        uint256 grailAmount,// GRAIL amount to receive when vesting has ended
        uint256 xGrailAmount, // xGRAIL amount to redeem
        uint256 endTime,
        address dividendsAddress,
        uint256 dividendsAllocation // Share of redeeming xGRAIL to allocate to the Dividends Usage contract
    );

    function finalizeRedeem(uint256 index) external;
}

interface IXGrailToken {
    function allocate(
        address usageAddress,
        uint256 amount,
        bytes calldata usageData
    ) external;

    function balanceOf(address owner) external view returns (uint256);
    function minRedeemDuration() external view returns (uint256);

    function approveUsage(address usage, uint256 _amount) external;

    function redeem(uint256 xGrailAmount, uint256 duration) external;

    function cancelRedeem(uint256 redeemIndex) external;
}


contract TorchManagerV2 is INFTHandler {

    uint256 public tokenId;
    address public nitroPool;
    address public nftPool;
    IERC20 public want;
    IERC20 public short;

    IERC20 public metis;
    IERC20 public torch;

    address public strategy;

    address public strategist;
    address public manager;
    IAlgebraPool public algebraPool;
    IGammaVault public gammaVault;
    IClearance public clearance;
    IUniProxy public depositPoint;
    ICamelotRouter public router;
    bool public isRetired = false;
    bytes4 private constant _ERC721_RECEIVED = 0x150b7a02;

    constructor(address _strategy) {
        strategy = _strategy;
        want = IERC20(IStrategy(_strategy).want());
        short = IERC20(IStrategy(_strategy).short());

        gammaVault = IGammaVault(0x343cA50235bd4dBefAcE13416EdB21FCB07f26a2);
        depositPoint = IUniProxy(0xD882a7AD21a6432B806622Ba5323716Fba5241A8);
        algebraPool = IAlgebraPool(0x35096c3cA17D12cBB78fA4262f3c6eff73ac9fFc);  
        clearance = IClearance(0xd359e08A60E2dDBFa1fc276eC11Ce7026642Ae71);
        nftPool = 0x69E2BcCaFD7dbC4CBfB3aE2cCFe2bAC2101f668d;
        nitroPool = 0x7F404c937b0cE51773B32112467566E6549ebC0F;

        metis = IERC20(0x75cb093E4D61d2A2e65D8e0BBb01DE8d89b53481);
        torch = IERC20(0xbB1676046C36BCd2F6fD08d8f60672c7087d9aDF);

        router = ICamelotRouter(0x14679D1Da243B8c7d1A4c6d0523A2Ce614Ef027C);

        want.approve(address(gammaVault), type(uint256).max);        
        IERC20(address(short)).approve(address(gammaVault), type(uint256).max);   

        want.approve(address(depositPoint), type(uint256).max);        
        IERC20(address(short)).approve(address(depositPoint), type(uint256).max);   

        metis.approve(address(router), type(uint256).max);
        torch.approve(address(router), type(uint256).max);

    }

    modifier onlyManager() {
        _onlyManager();
        _;
    }

    modifier onlyStrategist() {
        _onlyStrategist();
        _;
    }

    modifier onlyStrategy() {
        _onlyStrategy();
        _;
    }

    modifier onlyStrategyAndAbove() {
        require(msg.sender == address(strategy) || msg.sender == manager || msg.sender == strategist);
        _;
    }

    function _onlyManager() internal {
        require(msg.sender == manager);
    }

    function _onlyStrategist() internal {
        require(
            msg.sender == manager ||
                msg.sender == strategist
        );
    }

    function _onlyStrategy() internal {
        require(msg.sender == address(strategy));
    }


    function addToLp(uint256 _amount0, uint256 _amount1) external onlyStrategy {
        if (tokenId != 0 && countLpPooled() > 0) {
            INitroPool(nitroPool).withdraw(tokenId);
            _removeAllLp();
        }

        uint256[4] memory _minAmounts;
        depositPoint.deposit(algebraPool.token0(), algebraPool.token1(), _amount0, _amount1, address(gammaVault), _minAmounts, nftPool, 0);
        _stakeInNitro();
        // Transfer any unspent want & short back to strategy
    }

    function withdrawLp() external onlyStrategy {
        if (tokenId != 0) {
            INitroPool(nitroPool).withdraw(tokenId);
            _removeAllLp();
        }
    }

    function _stakeInNitro() internal {
        bytes memory _data = abi.encode(address(this));
        INFTPoolTorch(nftPool).safeTransferFrom(address(this), nitroPool, tokenId, _data);
    }

    function _removeAllLp() internal {
        uint256 _shares = countLpPooled();
        INFTPoolTorch(nftPool).withdrawFromPosition(tokenId, countLpPooled());
        uint256[4] memory _minAmounts;
        gammaVault.withdraw(_shares, address(this), address(this), _minAmounts);

        want.transfer(address(strategy), want.balanceOf(address(this)));
        short.transfer(address(strategy), short.balanceOf(address(this)));
        // NOTE : we set TokenId back to 0 -> no LP is pooled will return balance 0 in countLpPooled
        tokenId = 0;
    }

    function onERC721Received(
        address, /*_operator*/
        address _from,
        uint256 _tokenId,
        bytes calldata /*data*/
    ) external override returns (bytes4) {
        require((msg.sender == nftPool || msg.sender == nitroPool), "unexpected nft");
        if (msg.sender == nftPool) {
            INFTPoolTorch(nftPool).approve(_from, _tokenId);
            tokenId = _tokenId;
        }
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

    function tokenIdOwner(uint256 _tokenId) external view returns (address) {
        return INitroPool(nitroPool).tokenIdOwner(_tokenId);
    }

    function onNFTWithdraw(
        address _operator,
        uint256 _tokenId,
        uint256 /*lpAmount*/
    ) external override returns (bool) {
        require((msg.sender == nftPool || msg.sender == nitroPool), "unexpected nft");
        require(
            _operator == address(this),
            "NFTHandler: caller is not the nft previous owner"
        );

        return true;
    }

    function countLpPooled() public view returns (uint256) {
        if (tokenId == 0) {
            return 0;
        }
        (uint256 _amount, , , , , , , ) = INFTPoolTorch(nftPool).getStakingPosition(tokenId);
        return _amount;
    }

    function _finaliseRedeems(address _redeemAddress) internal {
        uint256 _nRedeems = IXMetis(_redeemAddress).getUserRedeemsLength(address(this));

        if (_nRedeems == 0) {
            return;
        }
        for (uint256 i = 0; i < _nRedeems; i++) {
            (uint256 _grailAmount, uint256 _xGrailAmount, uint256 _endTime , , ) = IXMetis(_redeemAddress).userRedeems(address(this), i);
            if (_endTime < block.timestamp) {
                IXMetis(_redeemAddress).finalizeRedeem(i);
            } else {
                return;
            }
        }

    }

    function harvestRetired() external onlyStrategyAndAbove {
        require(isRetired, "not retired");

        address _xMetis = 0xcA042eA7E9AA901C85d5afA5247a79E935dB4996;
        uint256 _xMetisBalance = IXMetis(_xMetis).balanceOf(address(this));

        address _xTorch = 0xF192897fC39bF766F1011a858dE964457bcA5832;
        uint256 _xTorchBalance = IXMetis(_xTorch).balanceOf(address(this));

        _finaliseRedeems(_xMetis);
        _finaliseRedeems(_xTorch);

        if (_xMetisBalance > 0 ) {
            IXMetis(_xMetis).redeem(_xMetisBalance, IXMetis(_xMetis).minRedeemDuration());
        }
        if (_xTorchBalance > 0 ) {
            IXMetis(_xTorch).redeem(_xTorchBalance, IXMetis(_xTorch).minRedeemDuration());
        }

        uint256 _torchBalance = torch.balanceOf(address(this));

        if (_torchBalance > 1000) {
            address[] memory path;
            path = new address[](2);
            path[0] = address(torch);
            path[1] = address(metis);
            router.swapExactTokensForTokensSupportingFeeOnTransferTokens(_torchBalance, 0, path, strategy, address(0), block.timestamp);
        }

        uint256 _metisBalance = metis.balanceOf(address(this));

        if (_metisBalance > 1000) {
            address[] memory path;
            path = new address[](2);
            path[0] = address(metis);
            path[1] = address(want);
            router.swapExactTokensForTokensSupportingFeeOnTransferTokens(_metisBalance, 0, path, strategy, address(0), block.timestamp);
        } 


    }

    function harvest() external onlyStrategy {
        if (tokenId == 0) {
            return;
        }

        // NOTE : Harvest XMetis & X Torch from Nitro Pool
        INitroPool(nitroPool).harvest();

        address _xMetis = 0xcA042eA7E9AA901C85d5afA5247a79E935dB4996;
        uint256 _xMetisBalance = IXMetis(_xMetis).balanceOf(address(this));

        address _xTorch = 0xF192897fC39bF766F1011a858dE964457bcA5832;
        uint256 _xTorchBalance = IXMetis(_xTorch).balanceOf(address(this));
        // NOTE : This will finalize any existing redeems that are ready to be finalised
        _finaliseRedeems(_xMetis);
        _finaliseRedeems(_xTorch);

        if (_xMetisBalance > 0 ) {
            IXMetis(_xMetis).redeem(_xMetisBalance, IXMetis(_xMetis).minRedeemDuration());
        }
        if (_xTorchBalance > 0 ) {
            IXMetis(_xTorch).redeem(_xTorchBalance, IXMetis(_xTorch).minRedeemDuration());
        }

        uint256 _torchBalance = torch.balanceOf(address(this));

        if (_torchBalance > 1000) {
            address[] memory path;
            path = new address[](2);
            path[0] = address(torch);
            path[1] = address(metis);
            router.swapExactTokensForTokensSupportingFeeOnTransferTokens(_torchBalance, 0, path, strategy, address(0), block.timestamp);
        }

        uint256 _metisBalance = metis.balanceOf(address(this));

        if (_metisBalance > 1000) {
            address[] memory path;
            path = new address[](2);
            path[0] = address(metis);
            path[1] = address(want);
            router.swapExactTokensForTokensSupportingFeeOnTransferTokens(_metisBalance, 0, path, strategy, address(0), block.timestamp);
        } 


    }

    function retireTorchManager() external onlyStrategyAndAbove {
        if (countLpPooled() > 0) {
            INitroPool(nitroPool).withdraw(tokenId);
            _removeAllLp();
        }
        isRetired = true;
    }


}