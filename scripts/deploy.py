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

    # Deploy sequence (6 contracts, no on-chain gasless contract):
    #
    # 1. EpochManager(admin, default_epoch_duration, resolution_cutoff_buffer)
    #    - Admin-gated market registry. Markets must be onboarded before
    #      any other contract will accept their conditionId.
    #    - Per-market params: collateral_factor, max_exposure_cap,
    #      min_liquidity_depth, resolution_time → cutoff.
    # 2. PremiumOracle(authorized_pricer=backend_wallet, reveal_delay=N)
    #    - Premiums go to pool's premium reserve, not to lenders.
    # 3. PriceFeed(authorized_updater=backend_wallet, deviation_threshold, staleness_limit, circuit_breaker_threshold)
    # 4. CollateralManager(ctf, epoch_manager, price_feed)
    #    - Reads collateral_factor + max_exposure_cap from EpochManager.
    # 5. LendingPool(usdc_e, epoch_manager, premium_oracle, collateral_manager, fixed_interest_rate_bps)
    #    - Three-part accounting: available liquidity, accrued interest
    #      (→ lender yield), premium reserve (→ risk buffer).
    #    - fixed_interest_rate_bps set by governance (can be updated).
    # 6. Liquidator(pool, collateral_manager, price_feed, ctf_exchange, neg_risk_ctf_exchange)
    #    - Shortfalls covered from premium reserve.
    #
    # Wire permissions:
    #    - pool → collateral_manager (can seize on liquidation)
    #    - liquidator → collateral_manager (can seize)
    #    - liquidator → pool (can return recovered USDC.e)
    #    - liquidator needs ERC1155 approval on CTF for ctf_exchange
    #    - liquidator needs ERC1155 approval on CTF for neg_risk_ctf_exchange
    #
    # Gasless: NOT deployed on-chain. The backend routes user txs through
    # Polymarket's Builder Relayer (https://relayer-v2.polymarket.com/)
    # using HMAC auth with POLY_BUILDER_API_KEY / SECRET / PASSPHRASE.
    # Users interact via Safe wallets deployed through the relayer.
    #
    # USER-SIDE APPROVALS (batched during session setup, via RelayClient):
    # These are NOT done in this deploy script — they happen per-user in
    # the frontend when a user first connects. Added to the standard
    # Polymarket approval batch:
    #    - USDC.e → LendingPool (so pool can pull USDC.e for deposits)
    #    - USDC.e → CollateralManager (so CM can pull premium payments)
    #    - CTF (ERC1155) → CollateralManager (so CM can pull collateral)
    # These are appended to the standard Polymarket approvals (CTF Exchange,
    # NegRisk Exchange, NegRisk Adapter) in a single batch tx.
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
