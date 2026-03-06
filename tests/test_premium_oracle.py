import boa
import pytest
from eth_abi import encode as abi_encode
from eth_utils import keccak


SALT = b"\x01" * 32
PREMIUM = 500


def _commitment(premium: int, salt: bytes) -> bytes:
    return keccak(abi_encode(["uint256", "bytes32"], [premium, salt]))


def test_initial_state(premium_oracle, condition_id, pricer):
    assert premium_oracle.condition_id() == condition_id
    assert premium_oracle.authorized_pricer() == pricer
    assert premium_oracle.reveal_delay() == 1


def test_commit(premium_oracle, pricer):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(1, commitment)
    assert premium_oracle.commitments(1) == commitment
    assert premium_oracle.commit_block(1) > 0


def test_commit_unauthorized_reverts(premium_oracle, lender):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(lender):
        with boa.reverts("not authorized"):
            premium_oracle.commit(1, commitment)


def test_commit_duplicate_reverts(premium_oracle, pricer):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(1, commitment)
        with boa.reverts("already committed"):
            premium_oracle.commit(1, commitment)


def test_commit_empty_hash_reverts(premium_oracle, pricer):
    with boa.env.prank(pricer):
        with boa.reverts("empty commitment"):
            premium_oracle.commit(1, b"\x00" * 32)


def test_reveal(premium_oracle, pricer):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(1, commitment)

    boa.env.time_travel(blocks=1)

    with boa.env.prank(pricer):
        premium_oracle.reveal(1, PREMIUM, SALT)

    assert premium_oracle.premiums(1) == PREMIUM
    assert premium_oracle.is_active(1) is True


def test_reveal_too_early_reverts(premium_oracle, pricer):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(1, commitment)
        with boa.reverts("reveal too early"):
            premium_oracle.reveal(1, PREMIUM, SALT)


def test_reveal_wrong_hash_reverts(premium_oracle, pricer):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(1, commitment)

    boa.env.time_travel(blocks=1)

    with boa.env.prank(pricer):
        with boa.reverts("hash mismatch"):
            premium_oracle.reveal(1, 999, SALT)


def test_reveal_already_revealed_reverts(premium_oracle, pricer):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(1, commitment)

    boa.env.time_travel(blocks=1)

    with boa.env.prank(pricer):
        premium_oracle.reveal(1, PREMIUM, SALT)
        with boa.reverts("already revealed"):
            premium_oracle.reveal(1, PREMIUM, SALT)


def test_get_premium(premium_oracle, pricer):
    commitment = _commitment(PREMIUM, SALT)
    with boa.env.prank(pricer):
        premium_oracle.commit(1, commitment)

    boa.env.time_travel(blocks=1)

    with boa.env.prank(pricer):
        premium_oracle.reveal(1, PREMIUM, SALT)

    assert premium_oracle.get_premium(1) == PREMIUM


def test_get_premium_not_active_reverts(premium_oracle):
    with boa.reverts("premium not active"):
        premium_oracle.get_premium(99)
