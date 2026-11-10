// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title InsuranceClaims
/// @notice Smart contract acting as the trusted middle layer between a
///         policyholder (sender) and an insurer (receiver).
contract InsuranceClaims {
    
    // Types
    
    struct Policy {
        address policyholder;
        uint256 premium;           // in wei
        uint256 coverageRemaining; // in wei
        uint256 durationDays;
        uint256 activeUntil;       // set when the premium is paid
        bool premiumPaid;
    }

    // State
    
    address public immutable insurer;
    uint256 public policyCount;

    mapping(uint256 => Policy) public policies;

    // Events (permanent audit trail)

    event PoolFunded(address indexed from, uint256 amount);
    event PolicyCreated(uint256 indexed policyId, address indexed policyholder, uint256 premium, uint256 coverage);
    event PremiumPaid(uint256 indexed policyId, address indexed policyholder, uint256 amount, uint256 activeUntil);

    // Access control
   
    modifier onlyInsurer() {
        require(msg.sender == insurer, "Only the insurer can do this");
        _;
    }

    modifier onlyPolicyholder(uint256 policyId) {
        require(msg.sender == policies[policyId].policyholder, "Only the policyholder can do this");
        _;
    }

    constructor() {
        insurer = msg.sender;
    }

    // Insurer: pool and policies
    
    function fundPool() external payable onlyInsurer {
        require(msg.value > 0, "Send some ETH");
        emit PoolFunded(msg.sender, msg.value);
    }

    function createPolicy(
        address policyholder,
        uint256 premium,
        uint256 coverage,
        uint256 durationDays
    ) external onlyInsurer returns (uint256 policyId) {
        require(policyholder != address(0) && policyholder != insurer, "Invalid policyholder");
        require(premium > 0 && coverage > 0 && durationDays > 0, "Values must be above zero");

        policyId = ++policyCount;
        policies[policyId] = Policy(policyholder, premium, coverage, durationDays, 0, false);
        emit PolicyCreated(policyId, policyholder, premium, coverage);
    }

    // Policyholder: premium

    function payPremium(uint256 policyId) external payable onlyPolicyholder(policyId) {
        Policy storage p = policies[policyId];
        require(!p.premiumPaid, "Premium already paid");
        require(msg.value == p.premium, "Send the exact premium");

        p.premiumPaid = true;
        p.activeUntil = block.timestamp + p.durationDays * 1 days;
        emit PremiumPaid(policyId, msg.sender, msg.value, p.activeUntil);
    }

    function poolBalance() external view returns (uint256) {
        return address(this).balance;
    }
}
