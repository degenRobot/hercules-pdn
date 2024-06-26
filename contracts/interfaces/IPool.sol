// SPDX-License-Identifier: AGPL-3.0

pragma solidity 0.8.15;

interface IAlgebraPool {

    function swapSupportingFeeOnTransferTokens(
        address sender,
        address recipient,
        bool zeroForOne,
        int256 amountSpecified,
        uint160 sqrtPriceLimitX96,
        bytes calldata data
    ) external;


}