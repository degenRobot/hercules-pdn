// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.12;
pragma experimental ABIEncoderV2;


interface IAlgebraPool {
    function globalState() external view returns(
    uint160 price, // The square root of the current price in Q64.96 format
    int24 tick, // The current tick
    uint16 feeZto, // The current fee for ZtO swap in hundredths of a bip, i.e. 1e-6
    uint16 feeOtz, // The current fee for OtZ swap in hundredths of a bip, i.e. 1e-6
    uint16 timepointIndex, // The index of the last written timepoint
    uint8 communityFeeToken0, // The community fee represented as a percent of all collected fee in thousandths (1e-3)
    uint8 communityFeeToken1,
    bool unlocked // True if the contract is unlocked, otherwise - false
    );
    function token0() external view returns(address);
    function token1() external view returns(address);

}