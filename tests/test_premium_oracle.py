import boa
import pytest
from eth_abi import encode as abi_encode
from eth_utils import keccak


SALT = b"\x01" * 32
PREMIUM = 500


def _commitment(premium: int, salt: bytes) -> bytes:
    return keccak(abi_encode(["uint256", "bytes32"], [premium, salt]))


@pytest.fixture(scope="session")
def test_borrower():
    acc = boa.env.generate_address("test_borrower")
    boa.env.set_balance(acc, 10 * 10**18)
    return acc


def test_initial_state(premium_oracle, condition_id, pricer):
    assert premium_oracle.condition_id() == condition_id
    assert premium_oracle.authorized_pricer() == pricer
    assert premium_oracle.reveal_delay() == 1


def test_commit(premium_oracle, pricer, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(test_borrower, commitment)
    assert premium_oracle.commitments(test_borrower) == commitment
    assert premium_oracle.commit_block(test_borrower) > 0


def test_commit_unauthorized_reverts(premium_oracle, lender, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(lender):
        with boa.reverts("not authorized"):
            premium_oracle.commit(test_borrower, commitment)


def test_commit_duplicate_reverts(premium_oracle, pricer, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(test_borrower, commitment)
        with boa.reverts("already committed"):
            premium_oracle.commit(test_borrower, commitment)


def test_commit_empty_hash_reverts(premium_oracle, pricer, test_borrower):
    with boa.env.prank(pricer):
        with boa.reverts("empty commitment"):
            premium_oracle.commit(test_borrower, b"\x00" * 32)


def test_reveal(premium_oracle, pricer, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(test_borrower, commitment)

    boa.env.time_travel(blocks=1)

    with boa.env.prank(pricer):
        premium_oracle.reveal(test_borrower, PREMIUM, SALT)

    assert premium_oracle.premiums(test_borrower) == PREMIUM
    assert premium_oracle.is_active(test_borrower) is True


def test_reveal_too_early_reverts(premium_oracle, pricer, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(test_borrower, commitment)
        with boa.reverts("reveal too early"):
            premium_oracle.reveal(test_borrower, PREMIUM, SALT)


def test_reveal_wrong_hash_reverts(premium_oracle, pricer, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(test_borrower, commitment)

    boa.env.time_travel(blocks=1)

    with boa.env.prank(pricer):
        with boa.reverts("hash mismatch"):
            premium_oracle.reveal(test_borrower, 999, SALT)


def test_reveal_already_revealed_reverts(premium_oracle, pricer, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(test_borrower, commitment)

    boa.env.time_travel(blocks=1)

    with boa.env.prank(pricer):
        premium_oracle.reveal(test_borrower, PREMIUM, SALT)
        with boa.reverts("already revealed"):
            premium_oracle.reveal(test_borrower, PREMIUM, SALT)


def test_get_premium(premium_oracle, pricer, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(test_borrower, commitment)

    boa.env.time_travel(blocks=1)

    with boa.env.prank(pricer):
        premium_oracle.reveal(test_borrower, PREMIUM, SALT)

    assert premium_oracle.get_premium(test_borrower) == PREMIUM


def test_get_premium_not_active_reverts(premium_oracle, borrower):
    with boa.reverts("premium not active"):
        premium_oracle.get_premium(borrower)


def test_clear_premium(premium_oracle, pricer, deployer, test_borrower):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(test_borrower, commitment)
    boa.env.time_travel(blocks=1)
    with boa.env.prank(pricer):
        premium_oracle.reveal(test_borrower, PREMIUM, SALT)

    mock_pool = boa.env.generate_address("mock_pool")
    with boa.env.prank(deployer):
        premium_oracle.set_authorized_pool(mock_pool)
    with boa.env.prank(mock_pool):
        premium_oracle.clear_premium(test_borrower)

    assert premium_oracle.is_active(test_borrower) is False
    assert premium_oracle.commitments(test_borrower) == b"\x00" * 32


def test_clear_premium_unauthorized_reverts(premium_oracle, lender, test_borrower):
    with boa.reverts("not authorized"):
        with boa.env.prank(lender):
            premium_oracle.clear_premium(test_borrower)
