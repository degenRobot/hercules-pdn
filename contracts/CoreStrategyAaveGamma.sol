// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

// These are the core Yearn libraries
import {StrategyParams} from "@yearnvaults/contracts/BaseStrategy.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import {Math} from "@openzeppelin/contracts/math/Math.sol";
import "./interfaces/aave/IAToken.sol";
import "./interfaces/aave/IVariableDebtToken.sol";
import "./interfaces/aave/IPool.sol";
import "./interfaces/aave/IAaveOracle.sol";

import {IStrategyInsurance} from "./StrategyInsurance.sol";
import {BaseStrategyRedux} from "./BaseStrategyRedux.sol";
import {IGammaVault} from "./interfaces/gamma/IGammaVault.sol";
import {IClearance} from "./interfaces/gamma/IClearance.sol";

import {IUniProxy} from "./interfaces/gamma/IUniProxy.sol";
import {IMasterchef} from "./interfaces/hercules/IMasterchef.sol";
import {IAlgebraPool} from "./interfaces/hercules/IAlgebraPool.sol";
import {IUniswapV2Router01} from "./interfaces/hercules/IUniswap.sol";
import {IRouter} from "./interfaces/hercules/IRouter.sol";
import {IPoolAddressesProvider} from "./interfaces/aave/IPoolAddressesProvider.sol";
import {ExactInputSingleParams} from "./interfaces/hercules/IRouter.sol";


struct CoreStrategyAaveConfig {
    // A portion of want token is depoisited into a lending platform to be used as
    // collateral. Short token is borrowed and compined with the remaining want token
    // and deposited into LP and farmed.
    address want;
    address short;
    /*****************************/
    /*             Farm           */
    /*****************************/
    // Liquidity pool address for base <-> short tokens
    address wantShortLP;
    // Address for farming reward token - eg Spirit/BOO
    address farmToken;
    // Liquidity pool address for farmToken <-> wFTM
    address farmTokenLP;
    // Farm address for reward farming
    address farmMasterChef;
    /*****************************/
    /*        Money Market       */
    /*****************************/
    // Base token cToken @ MM
    address aToken;
    address variableDebtToken;
    // Short token cToken @ MM
    address poolAddressesProvider;
    /*****************************/
    /*            AMM            */
    /*****************************/
    // Liquidity pool address for base <-> short tokens @ the AMM.
    // @note: the AMM router address does not need to be the same
    // AMM as the farm, in fact the most liquid AMM is prefered to
    // minimise slippage.
    address router;
    uint256 minDeploy;
}

interface IERC20Extended is IERC20 {
    function decimals() external view returns (uint8);
}

abstract contract CoreStrategyAaveGamma is BaseStrategyRedux {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;
    using SafeMath for uint8;

    event DebtRebalance(
        uint256 indexed debtRatio,
        uint256 indexed swapAmount,
        uint256 indexed slippage
    );
    event CollatRebalance(
        uint256 indexed collatRatio,
        uint256 indexed adjAmount
    );

    uint256 public collatUpper = 6700;
    uint256 public collatTarget = 6000;
    uint256 public collatLower = 5300;
    uint256 public debtUpper = 10190;
    uint256 public debtLower = 9810;

    // Min Amount to complete swaps 
    uint256 public dustAmt = 10000;

    // protocal limits & upper, target and lower thresholds for ratio of debt to collateral
    uint256 public collatLimit = 7500;
    uint256 public priceSourceDiffKeeper = 100;
    uint256 public priceSourceDiffUser = 100;

    uint256 public slippageAdj = 9900; // 99%
    uint256 public basisPrecision = 10000;
    uint256 constant STD_PRECISION = 1e18;

    uint8 public pid=4; 

    bool public doPriceCheck = false;
    bool public isPaused = false;

    address public weth;
    IERC20 public short;
    uint8 public wantDecimals;
    uint8 public shortDecimals;
    IERC20 public farmToken;
    // Contract Interfaces
    IUniswapV2Router01 public v2Router;
    IRouter public router;
    IPool public pool;
    IAToken public aToken;
    IVariableDebtToken public debtToken;
    IAaveOracle public oracle;
    IGammaVault public gammaVault;
    IUniProxy public depositPoint;
    IMasterchef public farmMasterChef;
    IAlgebraPool public herculesPool;
    IClearance public clearance;

    constructor(address _vault)
        public
        BaseStrategyRedux(_vault)
    {
        weth = 0x75cb093E4D61d2A2e65D8e0BBb01DE8d89b53481;
        short = IERC20(0x75cb093E4D61d2A2e65D8e0BBb01DE8d89b53481);
        wantDecimals = 6;
        shortDecimals = 18;
        _setInterfaces();
        _approveContracts();        
    }


    function _setInterfaces() internal {
        farmToken = IERC20(0xf28164A485B0B2C90639E47b0f377b4a438a16B1);
        IPoolAddressesProvider provider = IPoolAddressesProvider(0xB9FABd7500B2C6781c35Dd48d54f81fc2299D7AF);
        pool = IPool(0x90df02551bB792286e8D4f13E0e357b4Bf1D6a57);
        oracle = IAaveOracle(provider.getPriceOracle());
        aToken = IAToken(0x885C8AEC5867571582545F894A5906971dB9bf27);
        debtToken = IVariableDebtToken(0x0110174183e13D5Ea59D7512226c5D5A47bA2c40);  

        v2Router = IUniswapV2Router01(0x14679D1Da243B8c7d1A4c6d0523A2Ce614Ef027C);
        //router = IRouter(0xBde5839EC36Db2aC492b79e9E3B75e15FA8A59ec);
        // TO Double check this (flow seems to create NFT position as opposed to Gamma Vault position ???)
        
        gammaVault = IGammaVault(0xa6b3cea9E3D4b6f1BC5FA3fb1ec7d55A578473Ad);
        depositPoint = IUniProxy(0xD882a7AD21a6432B806622Ba5323716Fba5241A8);
        herculesPool = IAlgebraPool(0xA4E4949e0cccd8282f30e7E113D8A551A1eD1aeb);  
        clearance = IClearance(0xd359e08A60E2dDBFa1fc276eC11Ce7026642Ae71);

        //farmMasterChef = IMasterchef();


    }

    function _approveContracts() internal {
        want.approve(address(pool), type(uint256).max);        
        IERC20(address(short)).approve(address(pool), type(uint256).max);   

        want.approve(address(gammaVault), type(uint256).max);        
        IERC20(address(short)).approve(address(gammaVault), type(uint256).max);   

        want.approve(address(depositPoint), type(uint256).max);        
        IERC20(address(short)).approve(address(depositPoint), type(uint256).max);   


        //IERC20(address(gammaVault)).approve(address(farmMasterChef), type(uint256).max);     
        //IERC20(address(farmToken)).approve(address(router), type(uint256).max);
        //IERC20(address(farmToken)).approve(address(v2Router), type(uint256).max);
        //want.approve(address(router), type(uint256).max);        
        //IERC20(address(short)).approve(address(router), type(uint256).max);   
    }

    function _setup() internal virtual {}

    function name() external view override returns (string memory) {
        return "StrategyHedgedFarmingAaveGamma";
    }

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        uint256 totalAssets = estimatedTotalAssets();
        uint256 totalDebt = _getTotalDebt();
        if (totalAssets > totalDebt) {
            _profit = totalAssets.sub(totalDebt);
            (uint256 amountFreed, ) = _withdraw(_debtOutstanding.add(_profit));
            if (_debtOutstanding > amountFreed) {
                _debtPayment = amountFreed;
                _profit = 0;
            } else {
                _debtPayment = _debtOutstanding;
                _profit = amountFreed.sub(_debtOutstanding);
            }
        } else {
            _withdraw(_debtOutstanding);
            _debtPayment = balanceOfWant();
            _loss = totalDebt.sub(totalAssets);
        }

        _profit += _claimAndSellRewards();

        // Check if we're net loss or net profit
        if (_loss >= _profit) {
            _loss = _loss.sub(_profit);
            _profit = 0;
        } else {
            _profit = _profit.sub(_loss);
            _loss = 0;

        }
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        uint256 _wantAvailable = balanceOfWant();
        if (_debtOutstanding >= _wantAvailable) {
            return;
        }
        uint256 toInvest = _wantAvailable.sub(_debtOutstanding);

        if (toInvest > 0) {
            _deploy(toInvest);
        }
    }

    function prepareMigration(address _newStrategy) internal override {
        liquidateAllPositionsInternal();
    }

    function _getTokenOutPath(address tokenIn, address tokenOut)
        internal
        view
        returns (address[] memory _path)
    {
        bool isWeth = tokenIn == address(weth) || tokenOut == address(weth);
        _path = new address[](isWeth ? 2 : 3);
        _path[0] = tokenIn;
        if (isWeth) {
            _path[1] = tokenOut;
        } else {
            _path[1] = address(weth);
            _path[2] = tokenOut;
        }
    }

    function setSlippageConfig(
        uint256 _slippageAdj,
        uint256 _priceSourceDiffUser,
        uint256 _priceSourceDiffKeeper,
        bool _doPriceCheck
    ) external onlyAuthorized {
        slippageAdj = _slippageAdj;
        priceSourceDiffKeeper = _priceSourceDiffKeeper;
        priceSourceDiffUser = _priceSourceDiffUser;
        doPriceCheck = _doPriceCheck;
    }



    function setDebtThresholds(
        uint256 _lower,
        uint256 _upper,
        uint256 _rebalancePercent
    ) external onlyAuthorized {
        require(_lower <= basisPrecision);
        require(_rebalancePercent <= basisPrecision);
        require(_upper >= basisPrecision);
        //rebalancePercent = _rebalancePercent;
        debtUpper = _upper;
        debtLower = _lower;
    }

    function setCollateralThresholds(
        uint256 _lower,
        uint256 _target,
        uint256 _upper,
        uint256 _limit
    ) external onlyAuthorized {
        require(_limit <= basisPrecision);
        collatLimit = _limit;
        require(collatLimit > _upper);
        require(_upper >= _target);
        require(_target >= _lower);
        collatUpper = _upper;
        collatTarget = _target;
        collatLower = _lower;
    }

    function pauseStrat() external onlyKeepers {
        require(!isPaused);
        liquidateAllPositionsInternal();
        _lendWant(balanceOfWant());
        isPaused = true;
    }

    function unpauseStrat() external onlyKeepers {
        require(isPaused);
        isPaused = false;
        _redeemWant(balanceLend());
        _deploy(balanceOfWant());
    }

    function liquidatePositionAuth(uint256 _amount) external onlyAuthorized {
        liquidatePosition(_amount);
    }

    function liquidateAllToLend() internal {
        _withdrawLp(basisPrecision);
        _repayDebt();
        _lendWant(balanceOfWant());
    }

    function liquidateAllPositions()
        internal
        override
        returns (uint256 _amountFreed)
    {
        (_amountFreed, ) = liquidateAllPositionsInternal();
    }

    function liquidateAllPositionsInternal()
        internal
        returns (uint256 _amountFreed, uint256 _loss)
    {
        _withdraw(estimatedTotalAssets());
    }


    // deploy assets according to vault strategy
    function _deploy(uint256 _amount) internal {
        if (isPaused) {
            _lendWant(balanceOfWant());
            return;
        }

       uint256 oPrice = getOraclePrice();

        /*
        Due to pool having dynamic pool weights we know that the lend allocation follows the below :
        L = (1) / (1 + c(w / (1-w)))
        Where L = % of strat allocated as collateral & c = collateral target
        */

        uint256 poolWeightWant = getPoolWeightWant();
        uint256 _denominator = basisPrecision + poolWeightWant * collatTarget / (basisPrecision - poolWeightWant);

        uint256 _lendAmt = _amount * basisPrecision / _denominator;
        uint256 _borrowAmt = (_lendAmt * collatTarget / basisPrecision) * 1e18 / oPrice;

        _lendWant(_lendAmt);
        _borrow(_borrowAmt);
        _addToLP(_borrowAmt);

        // Any excess funds after should be returned back to AAVE 
        uint256 _excessWant = want.balanceOf(address(this));
        if (_excessWant > 0) {
            _lendWant(_excessWant);
        }
        _repayDebt();
    }

    function getLpPrice() public view returns (uint256) {
        (uint160 currentPrice, , , , , , , ) = herculesPool.globalState();
        uint256 price;

        uint256 const = 79228162514264337593543950336;

        if (herculesPool.token0() == address(want)) {
            // Using SafeMath for multiplication and division
            price = (const).mul(const).mul(1e18).div(uint256(currentPrice).mul(uint256(currentPrice)));
        } else {
            price = uint256(1e18).mul(uint256(currentPrice)).mul(uint256(currentPrice)).div(const.mul(const));
        }

        return price;
    }

    function getOraclePrice() public view returns (uint256) {
    

        uint256 shortOPrice = oracle.getAssetPrice(0xDeadDeAddeAddEAddeadDEaDDEAdDeaDDeAD0000);
        uint256 wantOPrice = oracle.getAssetPrice(address(want));
        return
            shortOPrice.mul(10**(wantDecimals.add(18).sub(shortDecimals))).div(
                wantOPrice
            );
    }

    /**
     * @notice
     *  Reverts if the difference in the price sources are >  priceDiff
     */
    function _testPriceSource(uint256 priceDiff) internal returns (bool) {
        if (doPriceCheck) {
            uint256 oPrice = getOraclePrice();
            uint256 lpPrice = getLpPrice();
            uint256 priceSourceRatio = oPrice.mul(basisPrecision).div(lpPrice);
            return (priceSourceRatio > basisPrecision.sub(priceDiff) &&
                priceSourceRatio < basisPrecision.add(priceDiff));
        }
        return true;
    }

    /**
     * @notice
     *  Assumes all balance is in Lend outside of a small amount of debt and short. Deploys
     *  capital maintaining the collatRatioTarget
     *
     * @dev
     *  Some crafty maths here:
     *  B: borrow amount in short (Not total debt!)
     *  L: Lend in want
     *  Cr: Collateral Target
     *  Po: Oracle price (short * Po = want)
     *  Plp: LP Price
     *  Di: Initial Debt in short
     *  Si: Initial short balance
     *
     *  We want:
     *  Cr = BPo / L
     *  T = L + Plp(B + 2Si - Di)
     *
     *  Solving this for L finds:
     *  B = (TCr - Cr*Plp(2Si-Di)) / (Po + Cr*Plp)
     */
    function _calcDeployment(uint256 _amount)
        internal
        returns (uint256 _lendNeeded, uint256 _borrow)
    {
        uint256 oPrice = getOraclePrice();
        uint256 lpPrice = getLpPrice();
        uint256 Si2 = balanceShort().mul(2);
        uint256 Di = balanceDebtInShort();
        uint256 CrPlp = collatTarget.mul(lpPrice);
        uint256 numerator;

        // NOTE: may throw if _amount * CrPlp > 1e70
        if (Di > Si2) {
            numerator = (
                collatTarget.mul(_amount).mul(1e18).add(CrPlp.mul(Di.sub(Si2)))
            )
                .sub(oPrice.mul(basisPrecision).mul(Di));
        } else {
            numerator = (
                collatTarget.mul(_amount).mul(1e18).sub(CrPlp.mul(Si2.sub(Di)))
            )
                .sub(oPrice.mul(basisPrecision).mul(Di));
        }

        _borrow = numerator.div(
            basisPrecision.mul(oPrice.add(CrPlp.div(basisPrecision)))
        );
        _lendNeeded = _amount.sub(
            (_borrow.add(Si2).sub(Di)).mul(lpPrice).div(1e18)
        );
    }

    function _deployFromLend(uint256 _amount) internal {
        if (isPaused) {
            return;
        }

        _deploy(_amount);
    }

    function rebalanceCollateral() external onlyKeepers {
        uint256 collatRatio = calcCollateralRatio();
        if (collatRatio > collatUpper) {
            uint256 _percentAdj = (collatRatio - collatTarget) * basisPrecision / collatRatio;
            _withdrawLp(_percentAdj);
            _repayDebt();
            uint256 _amountFree = want.balanceOf(address(this));
            _lendWant(_amountFree);

            // TO DO handle edge cases where pool weights are out of whack & we need to do a swap 

        } else if (collatRatio < collatLower) {
            uint256 _collatAtTarget = balanceDebt() * basisPrecision / collatTarget; 
            uint256 _redeemAmt = balanceLend() - _collatAtTarget;
            _redeemWant(_redeemAmt);
            uint256 _amountFree = want.balanceOf(address(this));
            _deploy(_amountFree);
        }

    }
    function _getTotalDebt() internal view returns (uint256) {
        return vault.strategies(address(this)).totalDebt;
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 balanceWant = balanceOfWant();
        uint256 totalAssets = estimatedTotalAssets();

        // if estimatedTotalAssets is less than params.debtRatio it means there's
        // been a loss (ignores pending harvests). This type of loss is calculated
        // proportionally
        // This stops a run-on-the-bank if there's IL between harvests.
        uint256 newAmount = _amountNeeded;
        uint256 totalDebt = _getTotalDebt();
        if (totalDebt > totalAssets) {
            uint256 ratio = totalAssets.mul(STD_PRECISION).div(totalDebt);
            newAmount = _amountNeeded.mul(ratio).div(STD_PRECISION);
            _loss = _amountNeeded.sub(newAmount);
        }

        // Liquidate the amount needed
        (, uint256 _slippage) = _withdraw(newAmount);
        _loss = _loss.add(_slippage);

        // NOTE: Maintain invariant `want.balanceOf(this) >= _liquidatedAmount`
        // NOTE: Maintain invariant `_liquidatedAmount + _loss <= _amountNeeded`
        _liquidatedAmount = balanceOfWant();
        if (_liquidatedAmount.add(_loss) > _amountNeeded) {
            _liquidatedAmount = _amountNeeded.sub(_loss);
        } else {
            _loss = _amountNeeded.sub(_liquidatedAmount);
        }
    }

    /**
     * function to remove funds from strategy when users withdraws funds in excess of reserves
     *
     * withdraw takes the following steps:
     * 1. Removes _amountNeeded worth of LP from the farms and pool
     * 2. Uses the short removed to repay debt (Swaps short or base for large withdrawals)
     * 3. Redeems the
     * @param _amountNeeded `want` amount to liquidate
     */
    function _withdraw(uint256 _amountNeeded)
        internal
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 balanceWant = balanceOfWant();
        uint256 slippage = 0;

        if (isPaused) {
            if (_amountNeeded > balanceWant) {
                _redeemWant(_amountNeeded.sub(balanceWant));
            }
            return (_amountNeeded, 0);
        }

        require(_testPriceSource(priceSourceDiffUser));
        if (_amountNeeded <= balanceWant) {
            return (_amountNeeded, 0);
        }

        uint256 balanceDeployed = balanceDeployed();

        // stratPercent: Percentage of the deployed capital we want to liquidate.
        uint256 stratPercent =
            _amountNeeded.sub(balanceWant).mul(basisPrecision).div(
                balanceDeployed
            );

        if (stratPercent > 500) {
            // swap to make up the difference in short 
            uint256 shortInShort = balanceShort();
            uint256 debtInShort = balanceDebtInShort() * stratPercent / basisPrecision;
            if (debtInShort > shortInShort) {
                uint256 swapAmountWant =_convertShortToWantLP(debtInShort - shortInShort);
                _redeemWant(swapAmountWant);
                if (swapAmountWant > dustAmt){
                    slippage = _swapExactWantShort(swapAmountWant);
                }
            } else {
                uint256 _swapAmtShort = shortInShort - debtInShort;
                if (_convertShortToWantLP(_swapAmtShort) > dustAmt) {
                    (, slippage) = _swapExactShortWant(shortInShort - (debtInShort* stratPercent / basisPrecision) );
                }
            }
        }
        
        _repayDebt();
        uint256 _redeemAmount = balanceLend() * stratPercent / basisPrecision;
        _redeemWant(_redeemAmount);

        // Note calculate loss and liquidated amount

    }

    // calculate total value of vault assets
    function estimatedTotalAssets() public view override returns (uint256) {
        return balanceOfWant().add(balanceDeployed());
    }

    // calculate total value of vault assets
    function balanceDeployed() public view returns (uint256) {
        return
            balanceLend().add(balanceLp()).add(balanceShortWantEq()).sub(
                balanceDebt()
            );
    }

    function calcDebtRatio() public view returns (uint256) {
        uint256 totalShort;
        if (herculesPool.token0() == address(want)) {
            (, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, ) = gammaVault.getTotalAmounts();           
        }

        (uint256 lpTokens, ) = farmMasterChef.userInfo(pid, address(this)); // number of LP Tokens user has in farm 
        uint256 shortInLp = totalShort * (lpTokens + gammaVault.balanceOf(address(this))) / gammaVault.totalSupply();
        return balanceDebtInShort() * basisPrecision / shortInLp;
    }

    // collateral ratio - used to trigger rebalancing of collateral
    function calcCollateralRatio() public view returns (uint256) {
        return (balanceDebtInShort() * getOraclePrice() / 1e18) * basisPrecision / balanceLend();
    }

    function _claimAndSellRewards() internal returns (uint256) {
        // CLAIM & SELL REWARDS 
        uint256 balBefore = want.balanceOf(address(this));

        farmMasterChef.harvest(pid, address(this));
        uint256 _amount = farmToken.balanceOf(address(this));
        if (_amount > 0) {

            uint256 amountOut = 0;
            v2Router.swapExactTokensForTokens(_amount, amountOut, _getTokenOutPath(address(farmToken), address(want)), address(this), block.timestamp);

            /*
            TO DO - Debug this as currently failing using upgraded router (using old router for now)
            ExactInputSingleParams memory input;

            input.amountIn = _amount;
            input.tokenIn = address(farmToken);
            input.tokenOut = address(asset);
            input.recipient = address(this);
            input.deadline = block.timestamp;
            input.amountOutMinimum = 0;
            router.exactInputSingle(input);            
            */
        }

        uint256 balAfter = want.balanceOf(address(this));

        return balAfter.sub(balBefore);
    }

    function convertShortToWantOracle(uint256 _amountShort)
        internal
        view
        returns (uint256)
    {
        return _amountShort.mul(getOraclePrice()).div(1e18);
    }

    function _convertShortToWantLP(uint256 _amountShort)
        internal
        view
        returns (uint256)
    {
        return _amountShort.mul(getLpPrice()).div(1e18);

    }

    function _convertWantToShortLP(uint256 _amountWant)
        internal
        view
        returns (uint256)
    {
        return _amountWant.mul(1e18).div(getLpPrice());

    }

    function balanceLp() public view returns (uint256) {
        uint256 totalWant; 
        uint256 totalShort;
        if (herculesPool.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }

        (uint256 lpTokens, ) = farmMasterChef.userInfo(pid, address(this)); // number of LP Tokens user has in farm 
        uint256 lpValue = (totalWant + (totalShort * getOraclePrice() / 1e18)) * (lpTokens + gammaVault.balanceOf(address(this))) / gammaVault.totalSupply();
        return(lpValue);
    }

    // value of borrowed tokens in value of want tokens
    function balanceDebtInShort() public view returns (uint256) {
        // Each debtToken is pegged 1:1 with the short token
        return debtToken.balanceOf(address(this));
    }

    // value of borrowed tokens in value of want tokens
    // Uses current exchange price, not stored
    function balanceDebtInShortCurrent() internal returns (uint256) {
        return debtToken.balanceOf(address(this));
    }

    // value of borrowed tokens in value of want tokens
    function balanceDebt() public view returns (uint256) {
        return _convertShortToWantOracle(balanceDebtInShort());
    }

    /**
     * Debt balance using price oracle
     */
    function balanceDebtOracle() public view returns (uint256) {
        return _convertShortToWantOracle(balanceDebtInShort());
    }

    // Farm can be very different -> implement in the strategy directly
    function balancePendingHarvest() public view virtual returns (uint256) {
        return 0;
    }

    // reserves
    function balanceOfWant() public view returns (uint256) {
        return (want.balanceOf(address(this)));
    }

    function balanceShort() public view returns (uint256) {
        return (short.balanceOf(address(this)));
    }

    function balanceShortWantEq() public view returns (uint256) {
        return _convertShortToWantLP(balanceShort());
    }

    function balanceLend() public view returns (uint256) {
        return aToken.balanceOf(address(this));
    }

    // lend want tokens to lending platform
    function _lendWant(uint256 amount) internal {
        pool.supply(address(want), amount, address(this), 0);
    }

    function _borrow(uint256 borrowAmount) internal {
        pool.borrow(address(short), borrowAmount, 2, 0, address(this));
    }

    // automatically repays debt using any short tokens held in wallet up to total debt value
    function _repayDebt() internal {
        uint256 _bal = short.balanceOf(address(this));
        if (_bal == 0) return;

        uint256 _debt = balanceDebtInShort();
        if (_bal < _debt) {
            pool.repay(address(short), _bal, 2, address(this));
        } else {
            pool.repay(address(short), _debt, 2, address(this));
        }
    }

    function _redeemWant(uint256 _redeem_amount) internal {
        pool.withdraw(address(want), _redeem_amount, address(this));
    }


    function getPoolWeightWant() public view returns(uint256) {
        uint256 totalWant; 
        uint256 totalShort;
        if (herculesPool.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }
        uint256 _poolWeightWant = basisPrecision * totalWant/(totalWant + _convertShortToWantOracle(totalShort));
        return _poolWeightWant;

    }

    function _getAmountsIn(uint256 _amountShort) internal view returns (uint256 _amount0, uint256 _amount1) {
        uint256 totalWant; 
        uint256 totalShort;
        if (herculesPool.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }
        uint256 balWant = want.balanceOf(address(this));
        uint256 _amountWant = totalWant * _amountShort / totalShort;
        // if we don't have enough want to add to LP, need to scale back amounts we add
        if (balWant < _amountWant) {
            _amountWant = balWant;
            _amountShort = balWant * totalShort / totalWant;
        } 

        if (herculesPool.token0() == address(want)) {
            _amount0 = _amountWant;
            _amount1 = _amountShort;
        } else {
            _amount0 = _amountShort;           
            _amount1 = _amountWant;
        }

    }

    function _getMaxValues() public view returns(uint256 deposit0Max, uint256 deposit1Max) {
        address clearanceAddress = 0xd359e08A60E2dDBFa1fc276eC11Ce7026642Ae71;
        bytes memory data = abi.encodeWithSelector(IClearance.positions.selector, address(gammaVault));

        (bool success, bytes memory returnData) = clearanceAddress.staticcall(data);
        require(success, "Call to Clearance contract failed");

        // Adjusting for tight packing of the first six boolean values
        uint256 offsetDeposit0Max = 9 * 32; // At slot 9 
        uint256 offsetDeposit1Max = 10 * 32; // At slot 10 

        assembly {
            deposit0Max := mload(add(returnData, add(offsetDeposit0Max, 32))) // add 32 for data offset
            deposit1Max := mload(add(returnData, add(offsetDeposit1Max, 32))) // add 32 for data offset
        }

        return (deposit0Max, deposit1Max);
    }

    function _checkMaxAmts(uint256 _amount0 , uint256 _amount1) internal view returns(uint256 , uint256 ) {

        (uint256 max0, uint256 max1) = _getMaxValues();

        if (_amount0 > max0) {
            _amount1 = max0 * _amount1 / _amount0;
            _amount0 = max0;
        }
        if (_amount1 > max1) {
            _amount0 = max1 * _amount0 / _amount1;
            _amount1 = max1;
        }
        return(_amount0, _amount1);
    }


    function _addToLP(uint256 _amountShort) internal {
        (uint256 _amount0, uint256 _amount1) = _getAmountsIn(_amountShort);
        uint256[4] memory _minAmounts;
        // Check Max deposit amounts 
        (_amount0, _amount1) = _checkMaxAmts(_amount0, _amount1);
        // Deposit into Gamma Vault & Farm 
        depositPoint.deposit(_amount0, _amount1, address(this), address(gammaVault), _minAmounts);
        farmMasterChef.deposit(pid, gammaVault.balanceOf(address(this)), address(this));
    }

    function _withdrawLp(uint256 _stratPercent) internal {
        (uint256 _farmBalance, ) = farmMasterChef.userInfo(pid, address(this));        
        uint256 _lpTokens = gammaVault.balanceOf(address(this));

        uint256 _lpOut = (_lpTokens + _farmBalance) * _stratPercent / basisPrecision;
        if (_farmBalance > 0) {
            farmMasterChef.withdraw(pid, _lpOut, address(this));
        }

        uint256[4] memory _minAmounts;
        gammaVault.withdraw(_lpOut, address(this), address(this), _minAmounts);
    }    


    function _swapExactWantShort(uint256 _amount)
        internal
        returns (uint256 slippageWant)
    {
        uint256 amountOut = _convertWantToShortLP(_amount);

        ExactInputSingleParams memory input;

        input.amountIn = _amount;
        input.tokenIn = address(want);
        input.tokenOut = address(short);
        input.recipient = address(this);
        input.deadline = block.timestamp;
        input.amountOutMinimum = amountOut*(slippageAdj)/(basisPrecision);
        router.exactInputSingle(input);
    }

    /**
     * @notice
     *  Swaps _amount of short for want
     *
     * @param _amountShort The amount of short to swap
     *
     * @return _amountWant Returns the want amount minus fees
     * @return _slippageWant Returns the cost of fees + slippage in want
     */
    function _swapExactShortWant(uint256 _amountShort)
        internal
        returns (uint256 _amountWant, uint256 _slippageWant)
    {
        _amountWant = _convertShortToWantLP(_amountShort);
        ExactInputSingleParams memory input;

        input.amountIn = _amountShort;
        input.amountOutMinimum = _amountWant*(slippageAdj)/(basisPrecision);
        input.tokenIn = address(short);
        input.tokenOut = address(want);
        input.recipient = address(this);
        input.deadline = block.timestamp;
        router.exactInputSingle(input);

    }

    function _convertShortToWantOracle(uint256 _amountShort)
        internal
        view
        returns (uint256)
    {
        return _amountShort .mul( getOraclePrice()).div(1e18);
    }

}
