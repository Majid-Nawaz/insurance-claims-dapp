# Insurance Claims DApp

A decentralised application for processing insurance claims on the Ethereum blockchain, developed for the Distributed Digital Transactions module at CCT College Dublin.

## About the Project
Traditional insurance claims processing is slow, paper-based and opaque. Policyholders often wait weeks for a decision, insurers spend heavily on manual verification, and duplicate or altered claims are difficult to detect across organisations.

This project uses a Solidity smart contract, `InsuranceClaims.sol`, as a trusted middle layer between the **policyholder (sender)** and the **insurer (receiver)**. The contract holds premiums, records each claim with a Keccak-256 hash of its supporting documents, rejects reused evidence, and pays approved claims automatically.

## Technology Stack
| Technology | Purpose |
|------------|---------|
| Solidity 0.8 | Smart contract development |
| Remix IDE | Compilation, deployment and manual testing |
| Ganache | Local Ethereum blockchain |
| Python (web3.py, py-solc-x) | Compilation, deployment and interaction |
| pytest | Automated contract tests |
| Shell script | Automation of setup, deployment and testing |

## Repository Structure
| Path | Contents |
|------|----------|
| `contracts/InsuranceClaims.sol` | The smart contract |
| `scripts/deploy.py` | Compiles, deploys to Ganache and runs a full claim scenario |
| `scripts/run.sh` | Sets up the environment and runs `deploy.py` |
| `scripts/test.sh` | Sets up the environment and runs the test suite |
| `tests/test_insurance_claims.py` | 13 automated tests covering every contract rule |
| `screenshots/` | Testing evidence from Remix, Ganache and pytest |
| `poster/` | Poster presentation |
| `requirements.txt` | Python dependencies |

## Smart Contract Functions
| Function | Caller | Description |
|----------|--------|-------------|
| `fundPool()` | Insurer | Deposits ETH into the claims pool |
| `createPolicy(policyholder, premium, coverage, durationDays)` | Insurer | Issues a policy |
| `payPremium(policyId)` | Policyholder | Pays the exact premium and activates the policy |
| `fileClaim(policyId, amount, evidenceHash)` | Policyholder | Files a claim with the Keccak-256 hash of its evidence |
| `approveClaim(claimId)` | Insurer | Approves a pending claim and pays it out |
| `rejectClaim(claimId, reason)` | Insurer | Rejects a pending claim with a reason |
| `poolBalance()` | Anyone | Returns the ETH held by the contract |

Security controls: role checks (`onlyInsurer`, `onlyPolicyholder`), the checks-effects-interactions pattern with a re-entrancy guard, coverage and pool-balance checks, duplicate-evidence detection, and Solidity 0.8 overflow protection.

## Prerequisites
- Python 3.10 or newer
- Ganache 2.7.1 (desktop app), running on `http://127.0.0.1:7545`
- Git Bash (Windows) or any Bash shell (Linux/macOS)

## How to Run

### 1. Remix IDE
1. Open [Remix IDE](https://remix.ethereum.org) and create `InsuranceClaims.sol` with the contents of `contracts/InsuranceClaims.sol`.
2. Compile with Solidity 0.8.20 or later.
3. Deploy with Account 1 (insurer), then call `fundPool`, `createPolicy`, `payPremium`, `fileClaim` and `approveClaim` as described in the poster.

### 2. Ganache with Python
Start Ganache (Quickstart), then from the project root:
```bash
bash scripts/run.sh
```
The script creates a virtual environment, installs the dependencies, deploys the contract and runs a full scenario: policy, premium, claim, a blocked self-approval, payout and blocked evidence reuse.

To use a different RPC URL:
```bash
bash scripts/run.sh http://127.0.0.1:8545
```

### 3. Automated tests
With Ganache running:
```bash
bash scripts/test.sh
```
Expected result: `13 passed`.

## Author
Majid Nawaz | Student Number: `2024473`
BSc Computing and IT, CCT College Dublin
