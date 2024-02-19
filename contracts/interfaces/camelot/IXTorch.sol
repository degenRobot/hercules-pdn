// SPDX-License-Identifier: AGPL-3.0

pragma solidity 0.6.12;


interface IXTorch {
    function allocate(
        address usageAddress,
        uint256 amount,
        bytes calldata usageData
    ) external;

    function balanceOf(address owner) external view returns (uint256);

    function approveUsage(address usage, uint256 _amount) external;

    function redeem(uint256 xGrailAmount, uint256 duration) external;

    function cancelRedeem(uint256 redeemIndex) external;
}