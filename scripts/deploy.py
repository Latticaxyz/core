import argparse
import os
import sys
from pathlib import Path
from eth_account import Account

import yaml

import boa

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_DIR = ROOT / "settings" / "chains"
DEPLOYMENTS_DIR = ROOT / "deployments"


def load_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        print(f"ERROR: Missing required secret {key}")
        sys.exit(1)
    return value


def load_chain_config(chain_name: str) -> dict:
    config_path = SETTINGS_DIR / f"{chain_name}.yaml"
    if not config_path.exists():
        available = [f.stem for f in SETTINGS_DIR.glob("*.yaml") if f.stem != "example"]
        print(f"ERROR: No config at {config_path}")
        print(f"Available: {available}")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def save_deployment(chain_name: str, addresses: dict) -> None:
    DEPLOYMENTS_DIR.mkdir(exist_ok=True)
    out = DEPLOYMENTS_DIR / f"{chain_name}.yaml"
    with open(out, "w") as f:
        yaml.dump(addresses, f, default_flow_style=False)
    print(f"Deployment saved to {out}")


def deploy(chain_name: str | None) -> None:
    if chain_name is None:
        print("deploying to local pyevm...")
        config = {}
    else:
        config = load_chain_config(chain_name)
        rpc_url = load_env("RPC_URL")
        deployer_key = load_env("DEPLOYER_PRIVATE_KEY")

        print(f"Deploying to {config['network_name']} (chain {config['chain_id']})...")
        print(f"  CTF:  {config.get('ctf', 'N/A')}")
        print(f"  USDC: {config.get('usdc', 'N/A')}")

        boa.set_network_env(rpc_url)
        account = Account.from_key(deployer_key)
        boa.env.add_account(account)
        boa.env.eoa = account.address

    # TODO: Deploy sequence
    # 1. InterestRateModel
    # 2. OracleAdapter (configured with CTF address from chain config)
    # 3. CollateralManager (configured with CTF, oracle)
    # 4. Vault (configured with USDC, collateral manager, interest model)
    # 5. Liquidator (configured with vault, collateral manager, oracle)
    print("(contracts not implemented yet)")

    # if chain_name:
    #     save_deployment(chain_name, {
    #         "vault": str(vault.address),
    #         "collateral_manager": str(cm.address),
    #         "interest_rate_model": str(irm.address),
    #         "oracle_adapter": str(oracle.address),
    #         "liquidator": str(liq.address),
    #     })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Lattica core contracts")
    parser.add_argument(
        "chain",
        nargs="?",
        default=None,
        help="Chain name matching settings/chains/*.yaml (omit for local pyevm)",
    )
    args = parser.parse_args()
    deploy(args.chain)
