// SPDX-License-Identifier: AGPL-3.0

pragma solidity 0.8.15;

interface ISwapRouter {

    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 limitSqrtPrice;
    }

    function exactInputSingleSupportingFeeOnTransferTokens(ExactInputSingleParams calldata params) external;

}