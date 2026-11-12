// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title InsuranceClaims
/// @notice Smart contract acting as the trusted middle layer between a
///         policyholder (sender) and an insurer (receiver).
contract InsuranceClaims {
    
    // Types
    
    enum ClaimStatus { Pending, Approved, Rejected }

    struct Policy {
        address policyholder;
        uint256 premium;           // in wei
        uint256 coverageRemaining; // in wei
        uint256 durationDays;
        uint256 activeUntil;       // set when the premium is paid
        bool premiumPaid;
    }

    struct Claim {
        uint256 policyId;
        uint256 amount;            // in wei
        bytes32 evidenceHash;      // Keccak-256 hash of the claim documents
        uint256 filedAt;
        ClaimStatus status;
    }

    
    // State
    
    address public immutable insurer;
    uint256 public policyCount;
    uint256 public claimCount;

    mapping(uint256 => Policy) public policies;
    mapping(uint256 => Claim) public claims;
    mapping(bytes32 => bool) private usedEvidence;
    bool private locked;

    
    // Events (permanent audit trail)
    
    event PoolFunded(address indexed from, uint256 amount);
    event PolicyCreated(uint256 indexed policyId, address indexed policyholder, uint256 premium, uint256 coverage);
    event PremiumPaid(uint256 indexed policyId, address indexed policyholder, uint256 amount, uint256 activeUntil);
    event ClaimFiled(uint256 indexed claimId, uint256 indexed policyId, uint256 amount, bytes32 evidenceHash);
    event ClaimApproved(uint256 indexed claimId, address indexed policyholder, uint256 amount);
    event ClaimRejected(uint256 indexed claimId, string reason);

    
    // Access control
    
    modifier onlyInsurer() {
        require(msg.sender == insurer, "Only the insurer can do this");
        _;
    }

    modifier onlyPolicyholder(uint256 policyId) {
        require(msg.sender == policies[policyId].policyholder, "Only the policyholder can do this");
        _;
    }

    modifier nonReentrant() {
        require(!locked, "Reentrant call");
        locked = true;
        _;
        locked = false;
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

    
    // Policyholder: premium and claims
    
    function payPremium(uint256 policyId) external payable onlyPolicyholder(policyId) {
        Policy storage p = policies[policyId];
        require(!p.premiumPaid, "Premium already paid");
        require(msg.value == p.premium, "Send the exact premium");

        p.premiumPaid = true;
        p.activeUntil = block.timestamp + p.durationDays * 1 days;
        emit PremiumPaid(policyId, msg.sender, msg.value, p.activeUntil);
    }

    function fileClaim(
        uint256 policyId,
        uint256 amount,
        bytes32 evidenceHash
    ) external onlyPolicyholder(policyId) returns (uint256 claimId) {
        Policy storage p = policies[policyId];
        require(p.premiumPaid && block.timestamp <= p.activeUntil, "Policy is not active");
        require(amount > 0 && amount <= p.coverageRemaining, "Amount exceeds coverage");
        require(evidenceHash != bytes32(0), "Evidence hash required");
        require(!usedEvidence[evidenceHash], "Evidence already used");

        usedEvidence[evidenceHash] = true;
        claimId = ++claimCount;
        claims[claimId] = Claim(policyId, amount, evidenceHash, block.timestamp, ClaimStatus.Pending);
        emit ClaimFiled(claimId, policyId, amount, evidenceHash);
    }

    
    // Insurer: decisions
    
    function approveClaim(uint256 claimId)
        external onlyInsurer nonReentrant
    {
        Claim storage c = claims[claimId];
        require(c.filedAt != 0 && c.status == ClaimStatus.Pending,
                "Claim is not pending");
        Policy storage p = policies[c.policyId];
        require(c.amount <= p.coverageRemaining, "Amount exceeds coverage");
        require(address(this).balance >= c.amount, "Pool has insufficient funds");

        // Effects before interaction (checks-effects-interactions)
        c.status = ClaimStatus.Approved;
        p.coverageRemaining -= c.amount;

        (bool sent, ) = payable(p.policyholder).call{value: c.amount}("");
        require(sent, "Payout failed");
        emit ClaimApproved(claimId, p.policyholder, c.amount);
    }

    function rejectClaim(uint256 claimId, string calldata reason) external onlyInsurer {
        Claim storage c = claims[claimId];
        require(c.filedAt != 0 && c.status == ClaimStatus.Pending, "Claim is not pending");

        c.status = ClaimStatus.Rejected;
        emit ClaimRejected(claimId, reason);
    }

    function poolBalance() external view returns (uint256) {
        return address(this).balance;
    }
}
