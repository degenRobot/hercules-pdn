// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

// These are the core Yearn libraries

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import {Math} from "@openzeppelin/contracts/math/Math.sol";
import "./interfaces/IWavax.sol";
import "./interfaces/uniswap.sol";
import "./interfaces/farm.sol";
import "./interfaces/uniswap.sol";
import "./BaseStrategyRedux.sol";
import "./screampriceoracle.sol";
import "./interfaces/QIComptroller.sol";
import {IStrategyInsurance} from "./StrategyInsurance.sol";

struct CoreStrategyBenqiConfig {
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
    address cTokenLend;
    // Short token cToken @ MM
    address cTokenBorrow;
    // Lend/Borrow rewards
    address compToken;
    address compTokenLP;
    // address compLpAddress;
    address comptroller;
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

abstract contract CoreStrategyBenqi is BaseStrategyRedux {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

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
    uint256 public rebalancePercent = 10000; // 100% (how far does rebalance of debt move towards 100% from threshold)

    // protocal limits & upper, target and lower thresholds for ratio of debt to collateral
    bool public doPriceCheck = true;

    // ERC20 Tokens;
    IERC20 public short;
    IUniswapV2Pair wantShortLP; // This is public because it helps with unit testing
    IERC20 farmTokenLP;
    IERC20 farmToken;
    IERC20 compToken;

    // Contract Interfaces
    ICTokenErc20 cTokenLend;
    ICAvax cTokenBorrow;
    address farm;
    IUniswapV2Router01 router;
    QIComptroller comptroller;
    IPriceOracle public oracle;
    IStrategyInsurance public insurance;

    uint256 public slippageAdj = 9900; // 99%

    uint256 constant BASIS_PRECISION = 10000;
    uint256 public priceSourceDiffKeeper = 500; // 5% Default
    uint256 public priceSourceDiffUser = 200; // 2% Default

    uint256 constant STD_PRECISION = 1e18;
    address wavax;
    uint256 public minDeploy;
    address[] internal cTokens = new address[](2);

    constructor(address _vault, CoreStrategyBenqiConfig memory _config)
        public
        BaseStrategyRedux(_vault)
    {
        // config = _config;

        // initialise token interfaces
        short = IERC20(_config.short);
        wantShortLP = IUniswapV2Pair(_config.wantShortLP);
        farmTokenLP = IERC20(_config.farmTokenLP);
        farmToken = IERC20(_config.farmToken);
        compToken = IERC20(_config.compToken);

        // initialise other interfaces
        cTokenLend = ICTokenErc20(_config.cTokenLend);
        cTokenBorrow = ICAvax(_config.cTokenBorrow);
        farm = (_config.farmMasterChef);
        router = IUniswapV2Router01(_config.router);
        comptroller = QIComptroller(_config.comptroller);
        wavax = router.WAVAX();

        cTokens[0] = _config.cTokenLend;
        cTokens[1] = _config.cTokenBorrow;

        comptroller.enterMarkets(cTokens);
        approveContracts();

        maxReportDelay = 21600;
        minReportDelay = 14400;
        profitFactor = 1500;
        minDeploy = _config.minDeploy;
    }

    function name() external view override returns (string memory) {
        return "StrategyHedgedFarmingV2.5";
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

        _profit += _harvestInternal();

        // Check if we're net loss or net profit
        if (_loss >= _profit) {
            _loss = _loss.sub(_profit);
            _profit = 0;
            _loss = _loss.sub(insurance.reportLoss(totalDebt, _loss));
        } else {
            _profit = _profit.sub(_loss);
            _loss = 0;
            (uint256 insurancePayment, uint256 compensation) =
                insurance.reportProfit(totalDebt, _profit);
            _profit = _profit.sub(insurancePayment).add(compensation);

            // double check insurance isn't asking for too much or zero
            if (insurancePayment > 0 && insurancePayment < _profit) {
                SafeERC20.safeTransfer(
                    want,
                    address(insurance),
                    insurancePayment
                );
            }
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

    function getTokenOutPath(address _token_in, address _token_out)
        internal
        view
        returns (address[] memory _path)
    {
        bool is_weth = _token_in == wavax || _token_out == wavax;
        _path = new address[](is_weth ? 2 : 3);
        _path[0] = _token_in;
        if (is_weth) {
            _path[1] = _token_out;
        } else {
            _path[1] = wavax;
            _path[2] = _token_out;
        }
    }

    function approveContracts() internal {
        want.safeApprove(address(cTokenLend), uint256(-1));
        short.safeApprove(address(cTokenBorrow), uint256(-1));
        want.safeApprove(address(router), uint256(-1));
        short.safeApprove(address(router), uint256(-1));
        farmToken.safeApprove(address(router), uint256(-1));
        IWavax(wavax).approve(address(router), uint256(-1));
        IERC20(address(wantShortLP)).safeApprove(address(router), uint256(-1));
        IERC20(address(wantShortLP)).safeApprove(address(farm), uint256(-1));
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

    function setInsurance(address _insurance) external onlyAuthorized {
        require(address(insurance) == address(0));
        insurance = IStrategyInsurance(_insurance);
    }

    function migrateInsurance(address _newInsurance) external onlyGovernance {
        require(address(_newInsurance) == address(0));
        insurance.migrateInsurance(_newInsurance);
        insurance = IStrategyInsurance(_newInsurance);
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
        require(_limit > _upper);
        require(_upper >= _target);
        require(_target >= _lower);
        collatUpper = _upper;
        collatTarget = _target;
        collatLower = _lower;
    }

    function liquidatePositionAuth(uint256 _amount) external onlyAuthorized {
        liquidatePosition(_amount);
    }

    function liquidateAllToLend() internal {
        _withdrawAllPooled();
        _removeAllLp();
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
        _withdrawAllPooled();
        _removeAllLp();

        uint256 debtInShort = balanceDebtInShortCurrent();
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

    /// rebalances RoboVault strat position to within target collateral range
    function rebalanceCollateral() external onlyKeepers {
        // ratio of amount borrowed to collateral
        uint256 collatRatio = calcCollateral();
        require(collatRatio <= collatLower || collatRatio >= collatUpper);
        require(_testPriceSource(priceSourceDiffKeeper));
        _rebalanceCollateralInternal();
    }

    /// rebalances RoboVault holding of short token vs LP to within target collateral range
    function rebalanceDebt() external onlyKeepers {
        uint256 debtRatio = calcDebtRatio();
        require(debtRatio < debtLower || debtRatio > debtUpper);
        require(_testPriceSource(priceSourceDiffKeeper));
        _rebalanceDebtInternal();
    }

    function claimHarvest() internal virtual;

    /// called by keeper to harvest rewards and either repay debt
    function _harvestInternal() internal returns (uint256 _wantHarvested) {
        uint256 wantBefore = balanceOfWant();
        /// harvest from farm & wantd on amt borrowed vs LP value either -> repay some debt or add to collateral
        claimHarvest();
        
        comptroller.claimReward(0, payable(address(this)), cTokens); //claim QI
        comptroller.claimReward(1, payable(address(this)), cTokens); //claim AVAX

        _sellToToken(address(farmToken));
        _sellToToken(address(compToken));
        _sellToToken(address(wavax));
        _wantHarvested = balanceOfWant().sub(wantBefore);
    }

    function _rebalanceCollateralInternal() internal {
        uint256 collatRatio = calcCollateral();
        uint256 shortPos = balanceDebt();
        uint256 lendPos = balanceLend();
        uint256 adjAmount;
        if (collatRatio > collatTarget) {
            adjAmount = (
                shortPos.sub(lendPos.mul(collatTarget).div(BASIS_PRECISION))
            )
                .mul(BASIS_PRECISION)
                .div(BASIS_PRECISION.add(collatTarget));
            /// remove some LP use 50% of withdrawn LP to repay debt and half to add to collateral
            _withdrawLpRebalanceCollateral(adjAmount.mul(2));
        } else if (collatRatio < collatTarget) {
            adjAmount = (
                (lendPos.mul(collatTarget).div(BASIS_PRECISION)).sub(shortPos)
            )
                .mul(BASIS_PRECISION)
                .div(BASIS_PRECISION.add(collatTarget));
            uint256 borrowAmt = _borrowWantEq(adjAmount);
            _redeemWant(adjAmount);
            _addToLP(borrowAmt);
            _depositLp();
        }
        emit CollatRebalance(collatRatio, adjAmount);
    }

    // deploy assets according to vault strategy
    function _deploy(uint256 _amount) internal {
        if (_amount < minDeploy) {
            return;
        }

        uint256 oPrice = oracle.getPrice();
        uint256 lpPrice = getLpPrice();
        uint256 borrow =
            collatTarget.mul(_amount).mul(1e18).div(
                BASIS_PRECISION.mul(
                    (collatTarget.mul(lpPrice).div(BASIS_PRECISION).add(oPrice))
                )
            );

        uint256 debtAllocation = borrow.mul(lpPrice).div(1e18);

        uint256 lendNeeded = _amount.sub(debtAllocation);

        _lendWant(lendNeeded);
        _borrow(borrow);
        _addToLP(borrow);
        _depositLp();
    }

    function getLpPrice() public view returns (uint256) {
        (uint256 wantInLp, uint256 shortInLp) = getLpReserves();
        return wantInLp.mul(1e18).div(shortInLp);
    }

    function getOraclePrice() public view returns (uint256) {
        return oracle.getPrice();
    }

    /**
     * @notice
     *  Reverts if the difference in the price sources are >  priceSourceDiff
     */
    function _testPriceSource(uint256 priceDiff) internal returns (bool) {
        if (doPriceCheck) {
            uint256 oPrice = oracle.getPrice();
            uint256 lpPrice = getLpPrice();
            uint256 priceSourceRatio = oPrice.mul(BASIS_PRECISION).div(lpPrice);
            return (priceSourceRatio > BASIS_PRECISION.sub(priceDiff) &&
                priceSourceRatio < BASIS_PRECISION.add(priceDiff));
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
        uint256 oPrice = oracle.getPrice();
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
                .sub(oPrice.mul(BASIS_PRECISION).mul(Di));
        } else {
            numerator = (
                collatTarget.mul(_amount).mul(1e18).sub(CrPlp.mul(Si2.sub(Di)))
            )
                .sub(oPrice.mul(BASIS_PRECISION).mul(Di));
        }

        _borrow = numerator.div(
            BASIS_PRECISION.mul(oPrice.add(CrPlp.div(BASIS_PRECISION)))
        );
        _lendNeeded = _amount.sub(
            (_borrow.add(Si2).sub(Di)).mul(lpPrice).div(1e18)
        );
    }

    function _deployFromLend(uint256 _amount) internal {
        (uint256 _lendNeeded, uint256 _borrowAmt) = _calcDeployment(_amount);
        _redeemWant(balanceLend().sub(_lendNeeded));
        _borrow(_borrowAmt);
        _addToLP(balanceShort());
        _depositLp();
    }

    function _rebalanceDebtInternal() internal {
        uint256 swapAmountWant;
        uint256 slippage;
        uint256 debtRatio = calcDebtRatio();

        // Liquidate all the lend, leaving some in debt or as short
        liquidateAllToLend();

        uint256 debtInShort = balanceDebtInShort();
        uint256 balShort = balanceShort();

        if (debtInShort > balShort) {
            uint256 debt = convertShortToWantLP(debtInShort);
            // If there's excess debt, we swap some want to repay a portion of the debt
            swapAmountWant = debt.mul(rebalancePercent).div(BASIS_PRECISION);
            _redeemWant(swapAmountWant);
            slippage = _swapExactWantShort(swapAmountWant);
            _repayDebt();
        } else {
            // If there's excess short, we swap some to want which will be used
            // to create lp in _deployFromLend()
            (swapAmountWant, slippage) = _swapExactShortWant(
                balanceShort().mul(rebalancePercent).div(BASIS_PRECISION)
            );
        }

        _deployFromLend(estimatedTotalAssets());
        emit DebtRebalance(debtRatio, swapAmountWant, slippage);
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
            liquidateAllToLend();

            // Only rebalance if more than 5% is being liquidated
            // to save on gas
            uint256 slippage = 0;
            if (stratPercent > 500) {
                // swap to ensure the debt ratio isn't negatively affected
                uint256 shortInShort = balanceShort();
                uint256 debtInShort = balanceDebtInShort();
                if (debtInShort > shortInShort) {
                    uint256 debt = convertShortToWantLP(debtInShort);
                    uint256 swapAmountWant =
                        debt.mul(stratPercent).div(BASIS_PRECISION);
                    _redeemWant(swapAmountWant);
                    slippage = _swapExactWantShort(swapAmountWant);
                    _repayDebt();
                } else {
                    (, slippage) = _swapExactShortWant(
                        balanceShort().mul(stratPercent).div(BASIS_PRECISION)
                    );
                }
            }

            // Redeploy the strat
            _deployFromLend(balanceDeployed.sub(_amountNeeded).add(slippage));
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
            balanceLend().add(balanceLp()).add(balanceShortWantEq()).sub(
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

    function getLpReserves()
        internal
        view
        returns (uint256 _wantInLp, uint256 _shortInLp)
    {
        (uint112 reserves0, uint112 reserves1, ) = wantShortLP.getReserves();
        if (wantShortLP.token0() == address(want)) {
            _wantInLp = uint256(reserves0);
            _shortInLp = uint256(reserves1);
        } else {
            _wantInLp = uint256(reserves1);
            _shortInLp = uint256(reserves0);
        }
    }

    function convertShortToWantLP(uint256 _amountShort)
        internal
        view
        returns (uint256)
    {
        (uint256 wantInLp, uint256 shortInLp) = getLpReserves();
        return (_amountShort.mul(wantInLp).div(shortInLp));
    }

    function convertShortToWantOracle(uint256 _amountShort)
        internal
        view
        returns (uint256)
    {
        return _amountShort.mul(oracle.getPrice()).div(1e18);
    }

    function convertWantToShortLP(uint256 _amountWant)
        internal
        view
        returns (uint256)
    {
        (uint256 wantInLp, uint256 shortInLp) = getLpReserves();
        return _amountWant.mul(shortInLp).div(wantInLp);
    }

    function balanceLpInShort() public view returns (uint256) {
        return countLpPooled().add(wantShortLP.balanceOf(address(this)));
    }

    /// get value of all LP in want currency
    function balanceLp() public view returns (uint256) {
        (uint256 wantInLp, ) = getLpReserves();
        return
            balanceLpInShort().mul(wantInLp).mul(2).div(
                wantShortLP.totalSupply()
            );
    }

    // value of borrowed tokens in value of want tokens
    function balanceDebtInShort() internal view returns (uint256) {
        return cTokenBorrow.borrowBalanceStored(address(this));
    }

    // value of borrowed tokens in value of want tokens
    // Uses current exchange price, not stored
    function balanceDebtInShortCurrent() internal returns (uint256) {
        return cTokenBorrow.borrowBalanceCurrent(address(this));
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

    function balancePendingHarvest() public view virtual returns (uint256) {
        uint256 rewardsPending = farmToken.balanceOf(address(this));
        uint256 harvestLP_A = farmToken.balanceOf(address(farmTokenLP));
        uint256 shortLP_A = short.balanceOf(address(farmTokenLP));
        (uint256 wantLP_B, uint256 shortLP_B) = getLpReserves();

        uint256 balShort = rewardsPending.mul(shortLP_A).div(harvestLP_A);
        uint256 balRewards = balShort.mul(wantLP_B).div(shortLP_B);
        return (balRewards);
    }

    // reserves
    function balanceOfWant() public view returns (uint256) {
        return (want.balanceOf(address(this)));
    }

    function balanceShort() public view returns (uint256) {
        return (short.balanceOf(address(this)));
    }

    function balanceShortWantEq() internal view returns (uint256) {
        return (convertShortToWantLP(short.balanceOf(address(this))));
    }

    function balanceLend() public view returns (uint256) {
        return (
            cTokenLend
                .balanceOf(address(this))
                .mul(cTokenLend.exchangeRateStored())
                .div(1e18)
        );
    }

    function countLpPooled() internal view virtual returns (uint256);

    // lend want tokens to lending platform
    function _lendWant(uint256 amount) internal {
        cTokenLend.mint(amount);
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
        cTokenBorrow.borrow(borrowAmount);
        IWavax(payable(wavax)).deposit{value: address(this).balance}();
    }

    // automatically repays debt using any short tokens held in wallet up to total debt value
    function _repayDebt() internal {
        uint256 _bal = short.balanceOf(address(this));
        if (_bal == 0) return;

        uint256 _debt = balanceDebtInShort();
        if (_bal < _debt) {
            _debt = _bal;
        }
        IWavax(wavax).withdraw(_debt);
        cTokenBorrow.repayBorrow{value: _debt}();
    }

    function _redeemWant(uint256 _redeem_amount) internal {
        cTokenLend.redeemUnderlying(_redeem_amount);
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
        _withdrawSomeLp(lpWithdraw);
        _removeAllLp();
        uint256 wantBal = balanceOfWant();
        if (_amount.div(2) <= wantBal) {
            _lendWant(_amount.div(2));
        } else {
            _lendWant(wantBal);
        }
        _repayDebt();
    }

    function _addToLP(uint256 _amountShort) internal {
        uint256 _amountWant = convertShortToWantLP(_amountShort);

        uint256 balWant = want.balanceOf(address(this));
        if (balWant < _amountWant) {
            _amountWant = balWant;
        }
        router.addLiquidity(
            address(short),
            address(want),
            _amountShort,
            _amountWant,
            _amountShort.mul(slippageAdj).div(BASIS_PRECISION),
            _amountWant.mul(slippageAdj).div(BASIS_PRECISION),
            address(this),
            now
        );
    }

    function _depositLp() internal virtual;

    function _withdrawFarm(uint256 _amount) internal virtual;

    function _withdrawSomeLp(uint256 _amount) internal {
        require(_amount <= countLpPooled());
        _withdrawFarm(_amount);
    }

    function _withdrawAllPooled() internal {
        uint256 lpPooled = countLpPooled();
        _withdrawFarm(lpPooled);
    }

    // all LP currently not in Farm is removed.
    function _removeAllLp() internal {
        uint256 _amount = wantShortLP.balanceOf(address(this));
        if (_amount > 0) {
            (uint256 wantLP, uint256 shortLP) = getLpReserves();
            uint256 lpIssued = wantShortLP.totalSupply();

            uint256 amountAMin =
                _amount.mul(shortLP).mul(slippageAdj).div(BASIS_PRECISION).div(
                    lpIssued
                );
            uint256 amountBMin =
                _amount.mul(wantLP).mul(slippageAdj).div(BASIS_PRECISION).div(
                    lpIssued
                );
            router.removeLiquidity(
                address(short),
                address(want),
                _amount,
                amountAMin,
                amountBMin,
                address(this),
                now
            );
        }
    }

    /**
     * @notice
     *  Swaps token to want using a customRouter
     *
     * @param from token to sell
     */
    function _sellToToken(
        address from
    ) internal {
        uint256 balance = IERC20(from).balanceOf(address(this));
        if (balance <= 1e18) return;
        router.swapExactTokensForTokens(
            balance,
            0,
            getTokenOutPath(from, address(want)),
            address(this),
            now
        );
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
        uint256 amountOutMin = convertWantToShortLP(_amount);
        uint256[] memory amounts =
            router.swapExactTokensForTokens(
                _amount,
                amountOutMin.mul(slippageAdj).div(BASIS_PRECISION),
                getTokenOutPath(address(want), address(short)),
                address(this),
                now
            );
        slippageWant = convertShortToWantLP(
            amountOutMin.sub(amounts[amounts.length - 1])
        );
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
        _amountWant = convertShortToWantLP(_amountShort);
        uint256[] memory amounts =
            router.swapExactTokensForTokens(
                _amountShort,
                _amountWant.mul(slippageAdj).div(BASIS_PRECISION),
                getTokenOutPath(address(short), address(want)),
                address(this),
                now
            );
        _slippageWant = _amountWant.sub(amounts[amounts.length - 1]);
    }

    function _swapWantShortExact(uint256 _amountOut)
        internal
        returns (uint256 _slippageWant)
    {
        uint256 amountInWant = convertShortToWantLP(_amountOut);
        uint256 amountInMax =
            (amountInWant.mul(BASIS_PRECISION).div(slippageAdj)).add(10); // add 1 to make up for rounding down
        uint256[] memory amounts =
            router.swapTokensForExactTokens(
                _amountOut,
                amountInMax,
                getTokenOutPath(address(want), address(short)),
                address(this),
                now
            );
        _slippageWant = amounts[0].sub(amountInWant);
    }

    // Required for BenQi interface
    receive() external payable {}
}
