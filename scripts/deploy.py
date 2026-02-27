import argparse
import os
import sys

import boa


def load_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Error: {name} not set.")
        sys.exit(1)
    return value


def deploy(broadcast: bool = False):
    rpc_url = load_env("RPC_URL")

    if broadcast:
        deployer_key = load_env("DEPLOYER_KEY")
        boa.env.add_account(boa.AccountFactory.from_key(deployer_key))
        boa.set_network_env(rpc_url)
