// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity ^0.6.12;

interface IVectorMainStaker {
    function getPoolInfo(address _address)
        external
        view
        returns (
            uint256 pid,
            bool isActive,
            address token,
            address receipt,
            address rewardsAddr,
            address helper
        );

    function setPoolRewarder(address token, address _poolRewarder) external;

    function owner() external view returns (address);
}

interface IVectorPoolHelper {
    function deposit(uint256 _amount) external;

    function withdraw(uint256 _amount) external;

    function balanceOf(address _user) external view returns (uint256);

    function getReward() external;
}

interface IBaseRewardPool {
    function earned(address _account, address _token)
        external
        view
        returns (uint256);
}
