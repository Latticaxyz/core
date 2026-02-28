import boa
import pytest

# Accounts


@pytest.fixture(scope="session")
def deployer():
    """Account used to deploy contracts."""
    acc = boa.env.generate_address("deployer")
    boa.env.set_balance(acc, 10 * 10**18)
    return acc


@pytest.fixture(scope="session")
def lender():
    """Account that deposits USDC into the vault."""
    acc = boa.env.generate_address("lender")
    boa.env.set_balance(acc, 10 * 10**18)
    return acc


@pytest.fixture(scope="session")
def borrower():
    """Account that borrows against outcome token collateral."""
    acc = boa.env.generate_address("borrower")
    boa.env.set_balance(acc, 10 * 10**18)
    return acc


@pytest.fixture(scope="session")
def liquidator():
    """Account that liquidates underwater positions."""
    acc = boa.env.generate_address("liquidator")
    boa.env.set_balance(acc, 10 * 10**18)
    return acc


# EVM Isolation


@pytest.fixture(autouse=True)
def isolate():
    """Snapshot and revert EVM state between tests."""
    with boa.env.anchor():
        yield


# Mock Tokens
# TODO: Add fixtures for:
# - mock USDC (ERC20)
# - mock ConditionalTokens (ERC1155 CTF)
# - mock outcome token positions (YES/NO for a test condition)
# - mock oracle adapter returning configurable prices
