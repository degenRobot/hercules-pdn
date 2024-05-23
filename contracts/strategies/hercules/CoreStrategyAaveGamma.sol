// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.15;

import {
    SafeERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {
    BaseStrategy,
    StrategyParams
} from "../BaseStrategy.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "../../interfaces/camelot/ICamelotRouter.sol";
import "../../interfaces/aave/IAToken.sol";
import "../../interfaces/aave/IVariableDebtToken.sol";
import "../../interfaces/aave/IPool.sol";
import "../../interfaces/aave/IAaveOracle.sol";
import "../../interfaces/IUniswapV2Pair.sol";

import {IGammaVault} from "../../interfaces/gamma/IGammaVault.sol";
import {IUniProxy} from "../../interfaces/gamma/IUniProxy.sol";
import {IClearance} from "../../interfaces/gamma/IClearance.sol";
import {IAlgebraPool} from "../../interfaces/camelot/IAlgebraPool.sol";

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

abstract contract CoreStrategyAaveGamma is BaseStrategy {
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

    uint256 public collatUpper = 5500;
    uint256 public collatTarget = 5000;
    uint256 public collatLower = 4500;
    uint256 public debtUpper = 10390;
    uint256 public debtLower = 9610;
    uint256 public rebalancePercent = 10000; // 100% (how far does rebalance of debt move towards 100% from threshold)


    IGammaVault public gammaVault;
    IUniProxy public depositPoint;
    IAlgebraPool public algebraPool;
    IClearance public clearance;

    // protocal limits & upper, target and lower thresholds for ratio of debt to collateral
    uint256 public collatLimit = 8100;

    bool public doPriceCheck = true;

    // ERC20 Tokens;
    IERC20 public short;
    uint8 wantDecimals;
    uint8 shortDecimals;
    IUniswapV2Pair wantShortLP; // This is public because it helps with unit testing
    // Contract Interfaces
    ICamelotRouter router;
    IPool pool;
    IAToken aToken;
    IVariableDebtToken debtToken;
    IAaveOracle public oracle;

    uint256 public slippageAdj = 9900; // 99%

    uint256 constant BASIS_PRECISION = 10000;
    uint256 public priceSourceDiffKeeper = 500; // 5% Default
    uint256 public priceSourceDiffUser = 200; // 2% Default

    uint256 constant FEE_DENOMINATOR = 100000;

    bool public isPaused = false;

    uint256 constant STD_PRECISION = 1e18;
    address weth;
    uint256 public minDeploy;

    constructor(address _vault, CoreStrategyAaveConfig memory _config)
        BaseStrategy(_vault)
    {
        // initialise token interfaces
        short = IERC20(_config.short);
        wantShortLP = IUniswapV2Pair(_config.wantShortLP);
        wantDecimals = IERC20Extended(_config.want).decimals();
        shortDecimals = IERC20Extended(_config.short).decimals();

        // initialise other interfaces
        router = ICamelotRouter(_config.router);

        IPoolAddressesProvider provider =
            IPoolAddressesProvider(_config.poolAddressesProvider);
        pool = IPool(provider.getPool());
        oracle = IAaveOracle(provider.getPriceOracle());

        aToken = IAToken(_config.aToken);
        debtToken = IVariableDebtToken(_config.variableDebtToken);

        maxReportDelay = 21600;
        minReportDelay = 14400;
        profitFactor = 1500;
        minDeploy = _config.minDeploy;
        _setup();
        approveContracts();
    }

    function _setup() internal virtual {}

    function name() external view override returns (string memory) {
        return "StrategyHedgedFarmingAaveTorch";
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
        _harvestInternal();

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
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        uint256 _wantAvailable = balanceOfWant();
        if (_debtOutstanding >= _wantAvailable) {
            return;
        }
        uint256 toInvest = _wantAvailable.sub(_debtOutstanding);

        if (toInvest > 0) {
            if (balanceDeployed() > 0) {
                uint256 _balBefore = balanceOfWant();
                liquidateAllPositions();
                uint256 _balAfter = balanceOfWant();
                toInvest += _balAfter.sub(_balBefore);
            }


            _deploy(toInvest);
        }
    }

    function prepareMigration(address _newStrategy) internal override {
        liquidateAllPositionsInternal();
    }

    function ethToWant(uint256 _amtInWei)
        public
        view
        virtual
        override
        returns (uint256)
    {
        // This is not currently used by the strategies and is
        // being removed to reduce the size of the contract
        return 0;
    }

    function getTokenOutPath(address _token_in, address _token_out)
        internal
        view
        returns (address[] memory _path)
    {
        _path = new address[](2);
        _path[0] = _token_in;
        _path[1] = _token_out;

    }

    function approveContracts() internal {
        want.safeApprove(address(pool), type(uint256).max);
        short.safeApprove(address(pool), type(uint256).max);
        want.safeApprove(address(router), type(uint256).max);
        short.safeApprove(address(router), type(uint256).max);
        IERC20(address(wantShortLP)).safeApprove(address(router), type(uint256).max);
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
        require(_lower <= BASIS_PRECISION);
        require(_rebalancePercent <= BASIS_PRECISION);
        require(_upper >= BASIS_PRECISION);
        rebalancePercent = _rebalancePercent;
        debtUpper = _upper;
        debtLower = _lower;
    }

    function setCollateralThresholds(
        uint256 _lower,
        uint256 _target,
        uint256 _upper,
        uint256 _limit
    ) external onlyAuthorized {
        require(_limit <= BASIS_PRECISION);
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

    function liquidateAllToWant() internal {
        _withdrawAllPooled();
        _removeAllLp();
        _redeemWant(balanceLend());
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
        _withdrawAllPooled();
        _removeAllLp();

        uint256 debtInShort = balanceDebtInShort();
        uint256 balShort = balanceShort();
        if (balShort >= debtInShort) {
            _repayDebt();
            if (balanceShortWantEq() > 0) {
                (, _loss) = _swapExactShortWant(short.balanceOf(address(this)));
            }
        } else {
            uint256 debtDifference = debtInShort.sub(balShort);
            if (convertShortToWantLP(debtDifference) > 0) {
                (_loss) = _swapWantShortExact(debtDifference);
            } else {
                _swapExactWantShort(uint256(1));
            }
            _repayDebt();
        }

        _redeemWant(balanceLend());
        _amountFreed = balanceOfWant();
    }

    // rebalances RoboVault strat position to within target collateral range
    function rebalanceCollateral() external onlyKeepers {
        // ratio of amount borrowed to collateral
        require(!isPaused);
        uint256 collatRatio = calcCollateral();
        require(collatRatio <= collatLower || collatRatio >= collatUpper);
        require(_testPriceSource(priceSourceDiffKeeper));
        _rebalanceCollateralInternal();
    }

    function claimHarvest() internal virtual;

    /// called by keeper to harvest rewards and either repay debt
    function _harvestInternal() internal returns (uint256 _wantHarvested) {
        uint256 wantBefore = balanceOfWant();
        /// harvest from farm & wantd on amt borrowed vs LP value either -> repay some debt or add to collateral
        claimHarvest();
        _wantHarvested = balanceOfWant().sub(wantBefore);
    }

    /**
     * Checks if collateral cap is reached or if deploying `_amount` will make it reach the cap
     * returns true if the cap is reached
     */
    function collateralCapReached(uint256 _amount)
        public
        view
        virtual
        returns (bool)
    {
        // There is no limit to how much we can supply
        return false;
    }

    function _rebalanceCollateralInternal() internal {
       liquidateAllPositionsInternal();
       _deploy(balanceOfWant());   
    }


    // deploy assets according to vault strategy
    function _deploy(uint256 _amount) internal {
        if (isPaused) {
            _lendWant(balanceOfWant());
            return;
        }

        if (_amount < minDeploy || collateralCapReached(_amount)) {
            return;
        }
        uint256 oPrice = getOraclePrice();
        uint256 poolWeightWant = getPoolWeightWant();
        uint256 poolWeightShort = BASIS_PRECISION.sub(poolWeightWant);
        uint256 _denominator = BASIS_PRECISION.add((poolWeightWant.mul(collatTarget).div(poolWeightShort)));

        uint256 _lendAmt = _getLendAmount(_amount);
        uint256 _borrowAmt = _lendAmt.mul(collatTarget).div(BASIS_PRECISION).mul(1e18).div(oPrice);
        uint256 _maxWant = _amount.sub(_lendAmt);

        _lendWant(_lendAmt);
        _borrow(_borrowAmt);
        _addToLP(_maxWant, _borrowAmt);

        // Any excess funds after should be returned back to AAVE 
        // uint256 _excessWant = want.balanceOf(address(this));
        // if (_excessWant > 0) {
        //     _lendWant(_excessWant);
        // }
    }

    function getTotalAmounts() public view returns(uint256 totalWant, uint256 totalShort) {
        if (algebraPool.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }

    }

    function totalLpValue() public view returns(uint256) {
        uint256 totalWant; 
        uint256 totalShort;
        if (gammaVault.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }

        return totalWant.add( convertShortToWantLP(totalShort));        
    }

    function totalLpValueWant() public view returns(uint256) {
        uint256 totalWant; 
        uint256 totalShort;
        if (gammaVault.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }

        return totalWant;        
    }

    function _getDeployDenominator() internal view returns(uint256) {
        uint256 poolWeightWant = getPoolWeightWant();
        uint256 poolWeightShort = BASIS_PRECISION.sub(poolWeightWant);
        return BASIS_PRECISION.add((poolWeightWant.mul(collatTarget).div(poolWeightShort)));
    }

    function _getLendAmount(uint256 _amount) internal view returns(uint256) {
        uint256 _denominator = _getDeployDenominator();
        return _amount.mul(BASIS_PRECISION).div(_denominator);
    }

    function getPoolWeightWant() public view returns(uint256) {
        uint256 totalWant; 
        uint256 totalShort;
        if (gammaVault.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }

        uint256 _totalLpValue = totalWant.add( convertShortToWantLP(totalShort));

        uint256 _poolWeightWant = totalWant.mul(BASIS_PRECISION).div(_totalLpValue);
        return _poolWeightWant;

    }

    function getLpPrice() public view returns (uint256) {
        
        (uint160 currentPrice, , , , , , , ) = algebraPool.globalState(); 
        uint256 price;
        if (algebraPool.token0() == address(want)) {
            price = ((2 ** 96) * (2 ** 96)) * 1e18 / (uint256(currentPrice) * uint256(currentPrice));
        } else {
            price = 1e18 * uint256(currentPrice) * uint256(currentPrice) / ((2 ** 96) * (2 ** 96));
        }
        return(price);    
    }

    function getOraclePrice() public view returns (uint256) {
        uint256 shortOPrice = oracle.getAssetPrice(address(short));
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
            uint256 priceSourceRatio = oPrice.mul(BASIS_PRECISION).div(lpPrice);
            return (priceSourceRatio > BASIS_PRECISION.sub(priceDiff) &&
                priceSourceRatio < BASIS_PRECISION.add(priceDiff));
        }
        return true;
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
            _amountNeeded.sub(balanceWant).mul(BASIS_PRECISION).div(
                balanceDeployed
            );

        if (stratPercent > 9500) {
            // If this happened, we just undeploy the lot
            // and it'll be redeployed during the next harvest.
            (, _loss) = liquidateAllPositionsInternal();
            _liquidatedAmount = balanceOfWant().sub(balanceWant);
        } else {
            // liquidate all to lend
            liquidateAllToWant();
            // Only rebalance if more than 5% is being liquidated
            // to save on gas
            uint256 slippage = 0;
            
            if (stratPercent > 500) {
                // swap to ensure the debt ratio isn't negatively affected
                uint256 shortInShort = balanceShort();
                uint256 debtInShort = balanceDebtInShort();
                if (debtInShort > shortInShort) {
                    uint256 debt =
                        convertShortToWantLP(debtInShort.sub(shortInShort));
                    uint256 swapAmountWant =
                        debt.mul(stratPercent).div(BASIS_PRECISION);
                    _redeemWant(swapAmountWant);
                    slippage = _swapExactWantShort(swapAmountWant);
                } else {
                    (, slippage) = _swapExactShortWant(
                        (shortInShort.sub(debtInShort)).mul(stratPercent).div(
                            BASIS_PRECISION
                        )
                    );
                }
            }
            
            _repayDebt();

            if (want.balanceOf(address(this)) > _amountNeeded) {
                _deploy(want.balanceOf(address(this)).sub(_amountNeeded));
            }
            _liquidatedAmount = balanceOfWant().sub(balanceWant);
            _loss = slippage;


        }
    }

    // calculate total value of vault assets
    function estimatedTotalAssets() public view override returns (uint256) {
        return balanceOfWant().add(balanceDeployed());
    }

    // calculate total value of vault assets
    function balanceDeployed() public view returns (uint256) {
        return
            balanceLend().add(balanceLp()).sub(
                balanceDebt()
            );
    }

    // debt ratio - used to trigger rebalancing of debt
    function calcDebtRatio() public view returns (uint256) {
        return (balanceDebt().mul(BASIS_PRECISION).mul(2).div(balanceLp()));
    }

    // calculate debt / collateral - used to trigger rebalancing of debt & collateral
    function calcCollateral() public view returns (uint256) {
        return balanceDebtOracle().mul(BASIS_PRECISION).div(balanceLend());
    }

    function convertShortToWantLP(uint256 _amountShort)
        internal
        view
        returns (uint256)
    {
        return _amountShort.mul(getLpPrice()).div(1e18);
    }

    function convertShortToWantOracle(uint256 _amountShort)
        internal
        view
        returns (uint256)
    {
        return _amountShort.mul(getOraclePrice()).div(1e18);
    }

    function convertWantToShortLP(uint256 _amountWant)
        internal
        view
        returns (uint256)
    {
        return _amountWant.mul(1e18).div(getLpPrice());
    }

    function balanceLpInShort() public view returns (uint256) {
        return countLpPooled().add(wantShortLP.balanceOf(address(this)));
    }

    /// get value of all LP in want currency
    function balanceLp() public view returns (uint256) {
        uint256 totalWant; 
        uint256 totalShort;
        if (algebraPool.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }

        // TO DO get balance of LP tokens from grail manager
        uint256 lpTokens = countLpPooled();
        uint256 lpValue = (totalWant + (totalShort * getOraclePrice() / 1e18)) * (lpTokens + gammaVault.balanceOf(address(this))) / gammaVault.totalSupply();
        return(lpValue);
    }

    // Value 
    function balanceDebtInShort() public view returns (uint256) {
        // Each debtToken is pegged 1:1 with the short token
        return debtToken.balanceOf(address(this));
    }

    // value of borrowed tokens in value of want tokens
    function balanceDebt() public view returns (uint256) {
        return convertShortToWantLP(balanceDebtInShort());
    }

    /**
     * Debt balance using price oracle
     */
    function balanceDebtOracle() public view returns (uint256) {
        return convertShortToWantOracle(balanceDebtInShort());
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
        return (convertShortToWantLP(short.balanceOf(address(this))));
    }

    function balanceLend() public view returns (uint256) {
        return aToken.balanceOf(address(this));
    }

    // Strategy specific
    function countLpPooled() internal view virtual returns (uint256);

    // lend want tokens to lending platform
    function _lendWant(uint256 amount) internal {
        pool.supply(address(want), amount, address(this), 0);
    }

    // borrow tokens woth _amount of want tokens
    function _borrowWantEq(uint256 _amount)
        internal
        returns (uint256 _borrowamount)
    {
        _borrowamount = convertWantToShortLP(_amount);
        _borrow(_borrowamount);
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
        if (_redeem_amount == 0) return;

        uint256 _lendBal = balanceLend();
        uint256 _debtBal = balanceDebt();

        uint256 _debtAdj = _debtBal.mul(BASIS_PRECISION).div(collatLimit);
        uint256 _maxRedeem;
        if (_debtAdj < _lendBal) {
            _maxRedeem = _lendBal.sub(_debtAdj);
        } else {
            _maxRedeem = 0;
            return;
        }

        if (_redeem_amount > _maxRedeem) {
            _redeem_amount = _maxRedeem;
        }

        pool.withdraw(address(want), _redeem_amount, address(this));
    }

    //  withdraws some LP worth _amount, uses withdrawn LP to add to collateral & repay debt
    function _withdrawLpRebalanceCollateral(uint256 _amount) internal {
        uint256 lpUnpooled = wantShortLP.balanceOf(address(this));
        uint256 lpPooled = countLpPooled();
        uint256 lpCount = lpUnpooled.add(lpPooled);
        uint256 lpReq = _amount.mul(lpCount).div(balanceLp());
        uint256 lpWithdraw;
        if (lpReq - lpUnpooled < lpPooled) {
            lpWithdraw = lpReq - lpUnpooled;
        } else {
            lpWithdraw = lpPooled;
        }
        _withdrawAllPooled();
        _removeAllLp();
        uint256 wantBal = balanceOfWant();
        if (_amount.div(2) <= wantBal) {
            _lendWant(_amount.div(2));
        } else {
            _lendWant(wantBal);
        }
        _repayDebt();
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

    function _getAmountsIn(uint256 _maxWant, uint256 _amountShort) internal view returns (uint256 _amount0, uint256 _amount1) {
        uint256 totalWant; 
        uint256 totalShort;
        if (algebraPool.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }
        uint256 balWant = want.balanceOf(address(this));
        uint256 _amountWant = totalWant * _amountShort / totalShort;
        // if we don't have enough want to add to LP, need to scale back amounts we add
        
        if (_maxWant < _amountWant) {
            _amountWant = _maxWant;
            _amountShort = _maxWant * totalShort / totalWant;
        } 
        if (algebraPool.token0() == address(want)) {
            _amount0 = _amountWant;
            _amount1 = _amountShort;
        } else {
            _amount0 = _amountShort;           
            _amount1 = _amountWant;
        }

    }

    function _addToLP(uint256 _maxWant, uint256 _amountShort) internal virtual {

    }

    // Farm-specific methods
    function _depositLp() internal virtual {

    }

    function _withdrawAllPooled() internal virtual {
    }

    // all LP currently not in Farm is removed.
    function _removeAllLp() internal virtual {
        uint256 _amount = wantShortLP.balanceOf(address(this));
        if (_amount > 0) {
            uint256[4] memory _minAmounts;
            gammaVault.withdraw(_amount, address(this), address(this), _minAmounts);
        }
    }

    /**
     * @notice
     *  Swaps _amount of want for short
     *
     * @param _amount The amount of want to swap
     *
     * @return slippageWant Returns the cost of fees + slippage in want
     */
    function _swapExactWantShort(uint256 _amount)
        internal
        returns (uint256 slippageWant)
    {
        if (_amount == 0) return (0);
        uint256 amountOutMin = convertWantToShortLP(_amount);
        uint256 shortBalanceBefore = short.balanceOf(address(this));
        uint256 _minSwap = 1000;
        if (_amount < _minSwap || amountOutMin < _minSwap) {
            return 0;
        }

        router.swapExactTokensForTokensSupportingFeeOnTransferTokens(
            _amount,
            amountOutMin.mul(slippageAdj).div(BASIS_PRECISION),
            getTokenOutPath(address(want), address(short)), // _pathWantToShort(),
            address(this),
            address(this),
            block.timestamp
        );

        uint256 amountOut = short.balanceOf(address(this)) - shortBalanceBefore;

        //slippageWant = convertShortToWantLP(amountOutMin - amountOut);
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
        if (_amountShort == 0) return(0,0);
        _amountWant = convertShortToWantLP(_amountShort);

        uint256 _minSwap = 1000000000;
        if (_amountShort < _minSwap || _amountWant < _minSwap) {
            return (0,0);
        }

        uint256 wantBalanceBefore = want.balanceOf(address(this));

        router.swapExactTokensForTokensSupportingFeeOnTransferTokens(
            _amountShort,
            _amountWant.mul(slippageAdj).div(BASIS_PRECISION),
            getTokenOutPath(address(short), address(want)),
            address(this),
            address(this),
            block.timestamp
        );

        uint256 _amountWantOut = want.balanceOf(address(this)) - wantBalanceBefore;

        //_slippageWant = _amountWant - _amountWantOut;
    }

    function _swapWantShortExact(uint256 _amountOut)
        internal
        returns (uint256 _slippageWant)
    {
        if (_amountOut == 0) return(0);
        uint256 amountInWant = convertShortToWantLP(_amountOut);
        uint256 amountInExactWant = getAmountIn(_amountOut);

        uint256 _minSwap = 1000;
        if (amountInExactWant < _minSwap || _amountOut < _minSwap) {
            return (0);
        }

        // Sub Optimal implementation given camelot does not have SwapTokensForExactTokens
        router.swapExactTokensForTokensSupportingFeeOnTransferTokens(
            amountInExactWant,
            _amountOut.mul(slippageAdj).div(BASIS_PRECISION),
            getTokenOutPath(address(want), address(short)), // _pathWantToShort(),
            address(this),
            address(this),
            block.timestamp
        );
        
        //_slippageWant = amountInExactWant - amountInWant;
    }

    function getAmountIn(uint256 _amountShort) internal returns (uint256 _amountWant) {
        uint256 totalWant; 
        uint256 totalShort;
        if (algebraPool.token0() == address(want)) {
            (totalWant, totalShort) = gammaVault.getTotalAmounts();
        } else {
             (totalShort, totalWant) = gammaVault.getTotalAmounts();           
        }
        uint256 balWant = want.balanceOf(address(this));
        uint256 _amountWant = totalWant * _amountShort / totalShort;
        // if we don't have enough want to add to LP, need to scale back amounts we add
        if (balWant < _amountWant) {
            _amountWant = balWant;
        } 

    }

    /**
     * @notice
     *  Intentionally not implmenting this. The justification being:
     *   1. It doesn't actually add any additional security because gov
     *      has the powers to do the same thing with addStrategy already
     *   2. Being able to sweep tokens from a strategy could be helpful
     *      incase of an unexpected catastropic failure.
     */
    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}
}
