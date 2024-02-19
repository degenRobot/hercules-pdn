// SPDX-License-Identifier: AGPL-3.0

pragma solidity 0.6.12;

interface ITorchPool {
    function approve(address to, uint256 tokenId) external;

    function getStakingPosition(uint256 tokenId)
        external
        view
        returns (
            uint256 amount,
            uint256 amountWithMultiplier,
            uint256 startLockTime,
            uint256 lockDuration,
            uint256 lockMultiplier,
            uint256 rewardDebt,
            uint256 boostPoints,
            uint256 totalMultiplier
        );

    function createPosition(uint256 amount, uint256 lockDuration) external;

    function lastTokenId() external view returns (uint256);

    function addToPosition(uint256 tokenId, uint256 amountToAdd) external;

    function withdrawFromPosition(uint256 tokenId, uint256 amountToWithdraw)
        external;

    function harvestPosition(uint256 tokenId) external;

    function xGrailRewardsShare() external view returns (uint256);

    function pendingRewards(uint256 tokenId) external view returns (uint256);

    function balanceOf(address owner) external view returns (uint256);

    function exists(uint256 tokenId) external view returns (bool);
}