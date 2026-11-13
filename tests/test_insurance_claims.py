"""Automated tests for InsuranceClaims.sol, run against a local Ganache blockchain.

Each test deploys a fresh contract, so tests are independent of each other.

Run with:
    bash scripts/test.sh            (recommended)
    python -m pytest tests -v       (inside the virtual environment)

Set GANACHE_RPC to use a different RPC URL (default: http://127.0.0.1:7545).
"""
import os
import sys
from pathlib import Path

import pytest
from web3 import Web3
from web3.exceptions import ContractLogicError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from deploy import compile_contract  # noqa: E402

RPC_URL = os.environ.get("GANACHE_RPC", "http://127.0.0.1:7545")

# Small amounts keep Ganache's 100 ETH test accounts usable across many runs
PREMIUM = Web3.to_wei(0.1, "ether")
COVERAGE = Web3.to_wei(0.5, "ether")
POOL = Web3.to_wei(1, "ether")
CLAIM = Web3.to_wei(0.2, "ether")
EVIDENCE = Web3.keccak(text="Claim: car repair invoice #INV-2026-1142")
OTHER_EVIDENCE = Web3.keccak(text="Claim: windscreen invoice #INV-2026-1187")


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture(scope="session")
def w3():
    web3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not web3.is_connected():
        pytest.exit(f"Cannot reach Ganache at {RPC_URL}. Start Ganache and try again.", returncode=1)
    return web3


@pytest.fixture(scope="session")
def compiled():
    return compile_contract()


@pytest.fixture(scope="session")
def accounts(w3):
    insurer, policyholder, outsider = w3.eth.accounts[:3]
    return {"insurer": insurer, "policyholder": policyholder, "outsider": outsider}


@pytest.fixture
def contract(w3, compiled, accounts):
    """A freshly deployed contract, owned by the insurer."""
    abi, bytecode = compiled
    tx = w3.eth.contract(abi=abi, bytecode=bytecode).constructor().transact({"from": accounts["insurer"]})
    address = w3.eth.wait_for_transaction_receipt(tx).contractAddress
    return w3.eth.contract(address=address, abi=abi)


def send(w3, call, sender, value=0):
    receipt = w3.eth.wait_for_transaction_receipt(call.transact({"from": sender, "value": value}))
    assert receipt.status == 1
    return receipt


@pytest.fixture
def active_policy(w3, contract, accounts):
    """A funded pool and policy 1 with its premium paid."""
    send(w3, contract.functions.fundPool(), accounts["insurer"], POOL)
    send(w3, contract.functions.createPolicy(accounts["policyholder"], PREMIUM, COVERAGE, 30), accounts["insurer"])
    send(w3, contract.functions.payPremium(1), accounts["policyholder"], PREMIUM)
    return contract


# ----------------------------------------------------------------------
# Deployment and policies
# ----------------------------------------------------------------------
def test_deployer_becomes_insurer(contract, accounts):
    assert contract.functions.insurer().call() == accounts["insurer"]


def test_only_insurer_can_create_policy(contract, accounts):
    with pytest.raises(ContractLogicError, match="Only the insurer can do this"):
        contract.functions.createPolicy(accounts["policyholder"], PREMIUM, COVERAGE, 30).transact(
            {"from": accounts["outsider"]})


def test_premium_must_be_exact(w3, contract, accounts):
    send(w3, contract.functions.createPolicy(accounts["policyholder"], PREMIUM, COVERAGE, 30), accounts["insurer"])
    with pytest.raises(ContractLogicError, match="Send the exact premium"):
        contract.functions.payPremium(1).transact({"from": accounts["policyholder"], "value": PREMIUM - 1})


def test_paying_premium_activates_policy(active_policy):
    policy = active_policy.functions.policies(1).call()
    assert policy[5] is True                      # premiumPaid
    assert policy[4] > 0                          # activeUntil is set
    assert active_policy.functions.poolBalance().call() == POOL + PREMIUM


# ----------------------------------------------------------------------
# Filing claims
# ----------------------------------------------------------------------
def test_cannot_claim_before_premium_is_paid(w3, contract, accounts):
    send(w3, contract.functions.createPolicy(accounts["policyholder"], PREMIUM, COVERAGE, 30), accounts["insurer"])
    with pytest.raises(ContractLogicError, match="Policy is not active"):
        contract.functions.fileClaim(1, CLAIM, EVIDENCE).transact({"from": accounts["policyholder"]})


def test_only_policyholder_can_file_claim(active_policy, accounts):
    with pytest.raises(ContractLogicError, match="Only the policyholder can do this"):
        active_policy.functions.fileClaim(1, CLAIM, EVIDENCE).transact({"from": accounts["outsider"]})


def test_claim_cannot_exceed_coverage(active_policy, accounts):
    with pytest.raises(ContractLogicError, match="Amount exceeds coverage"):
        active_policy.functions.fileClaim(1, COVERAGE + 1, EVIDENCE).transact({"from": accounts["policyholder"]})


def test_evidence_cannot_be_reused(w3, active_policy, accounts):
    send(w3, active_policy.functions.fileClaim(1, CLAIM, EVIDENCE), accounts["policyholder"])
    with pytest.raises(ContractLogicError, match="Evidence already used"):
        active_policy.functions.fileClaim(1, CLAIM, EVIDENCE).transact({"from": accounts["policyholder"]})


# ----------------------------------------------------------------------
# Decisions and payouts
# ----------------------------------------------------------------------
def test_policyholder_cannot_approve_own_claim(w3, active_policy, accounts):
    send(w3, active_policy.functions.fileClaim(1, CLAIM, EVIDENCE), accounts["policyholder"])
    with pytest.raises(ContractLogicError, match="Only the insurer can do this"):
        active_policy.functions.approveClaim(1).transact({"from": accounts["policyholder"]})


def test_approval_pays_policyholder_and_reduces_coverage(w3, active_policy, accounts):
    send(w3, active_policy.functions.fileClaim(1, CLAIM, EVIDENCE), accounts["policyholder"])
    before = w3.eth.get_balance(accounts["policyholder"])
    send(w3, active_policy.functions.approveClaim(1), accounts["insurer"])

    assert w3.eth.get_balance(accounts["policyholder"]) - before == CLAIM
    assert active_policy.functions.claims(1).call()[4] == 1            # Approved
    assert active_policy.functions.policies(1).call()[2] == COVERAGE - CLAIM
    assert active_policy.functions.poolBalance().call() == POOL + PREMIUM - CLAIM


def test_claim_cannot_be_paid_twice(w3, active_policy, accounts):
    send(w3, active_policy.functions.fileClaim(1, CLAIM, EVIDENCE), accounts["policyholder"])
    send(w3, active_policy.functions.approveClaim(1), accounts["insurer"])
    with pytest.raises(ContractLogicError, match="Claim is not pending"):
        active_policy.functions.approveClaim(1).transact({"from": accounts["insurer"]})


def test_rejected_claim_cannot_be_approved(w3, active_policy, accounts):
    send(w3, active_policy.functions.fileClaim(1, CLAIM, OTHER_EVIDENCE), accounts["policyholder"])
    send(w3, active_policy.functions.rejectClaim(1, "Invoice does not match policy"), accounts["insurer"])

    assert active_policy.functions.claims(1).call()[4] == 2            # Rejected
    with pytest.raises(ContractLogicError, match="Claim is not pending"):
        active_policy.functions.approveClaim(1).transact({"from": accounts["insurer"]})


def test_payout_needs_enough_funds_in_pool(w3, contract, accounts):
    # No fundPool: the contract only holds the 0.1 ETH premium
    send(w3, contract.functions.createPolicy(accounts["policyholder"], PREMIUM, COVERAGE, 30), accounts["insurer"])
    send(w3, contract.functions.payPremium(1), accounts["policyholder"], PREMIUM)
    send(w3, contract.functions.fileClaim(1, CLAIM, EVIDENCE), accounts["policyholder"])
    with pytest.raises(ContractLogicError, match="Pool has insufficient funds"):
        contract.functions.approveClaim(1).transact({"from": accounts["insurer"]})
