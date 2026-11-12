"""Compile InsuranceClaims.sol, deploy it to a local Ganache blockchain and run
a full claim scenario between the insurer (receiver) and a policyholder (sender).

Usage:
    python scripts/deploy.py [--rpc http://127.0.0.1:7545]
"""
import argparse
import json
import sys
from pathlib import Path

from solcx import compile_standard, get_installed_solc_versions, install_solc
from web3 import Web3
from web3.exceptions import ContractLogicError

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = ROOT / "contracts" / "InsuranceClaims.sol"
BUILD_DIR = ROOT / "build"
SOLC_VERSION = "0.8.24"


def eth(value):
    return Web3.to_wei(value, "ether")


def compile_contract():
    """Compile the contract with solc and return its ABI and bytecode."""
    if SOLC_VERSION not in {str(v) for v in get_installed_solc_versions()}:
        print(f"Installing solc {SOLC_VERSION} (first run only)...")
        install_solc(SOLC_VERSION)

    source = CONTRACT_FILE.read_text(encoding="utf-8")
    output = compile_standard(
        {
            "language": "Solidity",
            "sources": {CONTRACT_FILE.name: {"content": source}},
            "settings": {
                # Ganache does not support the PUSH0 opcode, so target the Paris EVM
                "evmVersion": "paris",
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
            },
        },
        solc_version=SOLC_VERSION,
    )
    contract = output["contracts"][CONTRACT_FILE.name]["InsuranceClaims"]
    return contract["abi"], contract["evm"]["bytecode"]["object"]


def send(w3, label, call, sender, value=0):
    """Send a transaction, wait for it to be mined and print a one-line summary."""
    tx_hash = call.transact({"from": sender, "value": value})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    status = "OK " if receipt.status == 1 else "FAIL"
    print(f"  [{status}] {label:<38} block {receipt.blockNumber:<3} gas {receipt.gasUsed:<7} tx {Web3.to_hex(tx_hash)[:18]}...")
    return receipt


def expect_revert(label, call, sender):
    """Show that the contract rejects an action that breaks its rules."""
    try:
        call.transact({"from": sender})
    except ContractLogicError as err:
        reason = str(err.message).rsplit("revert ", 1)[-1]
        print(f"  [BLOCKED] {label:<35} reason: {reason}")
        return
    print(f"  [UNEXPECTED] {label} was not rejected")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc", default="http://127.0.0.1:7545", help="Ganache RPC URL")
    args = parser.parse_args()

    w3 = Web3(Web3.HTTPProvider(args.rpc))
    if not w3.is_connected():
        sys.exit(f"Cannot reach Ganache at {args.rpc}. Start Ganache and try again.")

    insurer, policyholder = w3.eth.accounts[0], w3.eth.accounts[1]
    print(f"Connected to Ganache at {args.rpc} (chain id {w3.eth.chain_id})")
    print(f"  Insurer (receiver):      {insurer}")
    print(f"  Policyholder (sender):   {policyholder}\n")

    # 1. Compile and deploy
    print("1. Compile and deploy")
    abi, bytecode = compile_contract()
    factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    receipt = send(w3, "Deploy InsuranceClaims", factory.constructor(), insurer)
    contract = w3.eth.contract(address=receipt.contractAddress, abi=abi)
    print(f"  Contract address: {contract.address}\n")

    BUILD_DIR.mkdir(exist_ok=True)
    (BUILD_DIR / "deployment.json").write_text(
        json.dumps({"address": contract.address, "abi": abi}, indent=2), encoding="utf-8"
    )

    # 2. Policy set-up
    print("2. Policy set-up")
    send(w3, "Insurer funds pool with 10 ETH", contract.functions.fundPool(), insurer, eth(10))
    send(w3, "Insurer creates policy 1",
         contract.functions.createPolicy(policyholder, eth(1), eth(5), 30), insurer)
    send(w3, "Policyholder pays 1 ETH premium", contract.functions.payPremium(1), policyholder, eth(1))
    print(f"  Pool balance: {Web3.from_wei(contract.functions.poolBalance().call(), 'ether')} ETH\n")

    # 3. Claim with a Keccak-256 hash of the evidence
    print("3. Claim")
    invoice = "Claim 1: car repair invoice #INV-2026-1142, 12 Nov 2026"
    evidence = Web3.keccak(text=invoice)
    print(f"  Evidence hash (Keccak-256): {Web3.to_hex(evidence)}")
    send(w3, "Policyholder files a 2 ETH claim", contract.functions.fileClaim(1, eth(2), evidence), policyholder)
    expect_revert("Policyholder approves own claim", contract.functions.approveClaim(1), policyholder)

    before = w3.eth.get_balance(policyholder)
    send(w3, "Insurer approves claim 1", contract.functions.approveClaim(1), insurer)
    paid = w3.eth.get_balance(policyholder) - before
    print(f"  Payout received by policyholder: {Web3.from_wei(paid, 'ether')} ETH")
    expect_revert("Same evidence used again", contract.functions.fileClaim(1, eth(1), evidence), policyholder)

    # 4. Final state
    policy = contract.functions.policies(1).call()
    print("\n4. Final state")
    print(f"  Claim 1 status:     {['Pending', 'Approved', 'Rejected'][contract.functions.claims(1).call()[4]]}")
    print(f"  Coverage remaining: {Web3.from_wei(policy[2], 'ether')} ETH")
    print(f"  Pool balance:       {Web3.from_wei(contract.functions.poolBalance().call(), 'ether')} ETH")
    print(f"\nDeployment saved to {BUILD_DIR.relative_to(ROOT) / 'deployment.json'}")


if __name__ == "__main__":
    main()
