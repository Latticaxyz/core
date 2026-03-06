import boa
import pytest
from eth_abi import encode as abi_encode
from eth_utils import keccak as keccak256

LIQUIDATOR_ROLE: bytes = keccak256(b"LIQUIDATOR_ROLE")
MAX_BPS = 10000


def setup_premium(premium_oracle, pricer, borrower, premium_bps=200):
    salt = b"\x01" * 32
    commitment = keccak256(abi_encode(["uint256", "bytes32"], [premium_bps, salt]))
    with boa.env.prank(pricer):
        premium_oracle.commit(borrower, commitment)
    boa.env.time_travel(seconds=15)
    with boa.env.prank(pricer):
        premium_oracle.reveal(borrower, premium_bps, salt)


def do_deposit(lending_pool, lender, amount):
    with boa.env.prank(lender):
        lending_pool.deposit(amount)


def setup_borrow_prerequisites(
    lending_pool,
    collateral_manager,
    mock_ctf,
    price_feed,
    premium_oracle,
    pricer,
    deployer,
    borrower,
    lender,
    token_id,
    deposit_amount,
    collateral_amount=500 * 10**18,
    price=7 * 10**17,
    premium_bps=200,
):
    do_deposit(lending_pool, lender, deposit_amount)
    setup_premium(premium_oracle, pricer, borrower, premium_bps)
    with boa.env.prank(deployer):
        mock_ctf.mint(borrower, token_id, collateral_amount)
    with boa.env.prank(borrower):
        mock_ctf.setApprovalForAll(collateral_manager.address, True)
    with boa.env.prank(lending_pool.address):
        collateral_manager.deposit_collateral(borrower, collateral_amount, token_id)
    with boa.env.prank(pricer):
        price_feed.push_price(price)


def do_borrow(lending_pool, borrower, amount, duration=604800):
    with boa.env.prank(borrower):
        lending_pool.borrow(amount, borrower, duration)


# --- Deposit / Withdraw ---


def test_deposit(lending_pool, mock_usdc, lender, deployer, funded_lender):
    deposit_amount = 100_000 * 10**6
    pool_balance_before = mock_usdc.balanceOf(lending_pool.address)
    do_deposit(lending_pool, lender, deposit_amount)

    assert lending_pool.total_deposits() == deposit_amount
    assert lending_pool.shares(lender) > 0
    assert lending_pool.total_shares() > 0
    assert mock_usdc.balanceOf(lending_pool.address) == pool_balance_before + deposit_amount


def test_deposit_zero_reverts(lending_pool, lender):
    with boa.reverts("zero amount"):
        with boa.env.prank(lender):
            lending_pool.deposit(0)


def test_withdraw(lending_pool, mock_usdc, lender, deployer, funded_lender):
    deposit_amount = 100_000 * 10**6
    do_deposit(lending_pool, lender, deposit_amount)

    lender_shares = lending_pool.shares(lender)
    lender_balance_before = mock_usdc.balanceOf(lender)

    with boa.env.prank(lender):
        lending_pool.withdraw(lender_shares)

    assert lending_pool.total_deposits() == 0
    assert lending_pool.shares(lender) == 0
    assert mock_usdc.balanceOf(lender) == lender_balance_before + deposit_amount


def test_withdraw_insufficient_shares_reverts(lending_pool, lender):
    with boa.reverts("insufficient shares"):
        with boa.env.prank(lender):
            lending_pool.withdraw(1)


# --- Share value ---


def test_get_share_value(lending_pool, mock_usdc, lender, deployer, funded_lender):
    deposit_amount = 100_000 * 10**6
    do_deposit(lending_pool, lender, deposit_amount)

    lender_shares = lending_pool.shares(lender)
    value = lending_pool.get_share_value(lender_shares)
    assert value == deposit_amount


# --- Borrow ---


def test_borrow(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    interest_rate_model,
    funded_lender,
    setup_market,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    borrow_amount = 10_000 * 10**6
    premium_bps = 200

    setup_borrow_prerequisites(
        lending_pool, collateral_manager, mock_ctf, price_feed,
        premium_oracle, pricer, deployer, borrower, lender, token_id,
        deposit_amount, premium_bps=premium_bps,
    )

    borrower_balance_before = mock_usdc.balanceOf(borrower)

    utilization = (borrow_amount * MAX_BPS) // deposit_amount
    rate_bps = interest_rate_model.get_rate(utilization)
    interest = (borrow_amount * rate_bps) // MAX_BPS
    premium = (borrow_amount * premium_bps) // MAX_BPS
    net = borrow_amount - interest - premium

    do_borrow(lending_pool, borrower, borrow_amount)

    assert lending_pool.total_borrowed() == borrow_amount
    assert mock_usdc.balanceOf(borrower) == borrower_balance_before + net

    loan = lending_pool.loans(borrower)
    assert loan[0] == borrow_amount  # principal
    assert loan[1] == interest  # interest_paid
    assert loan[2] == premium  # premium_paid
    assert loan[3] == rate_bps  # rate_bps
    assert loan[5] is True  # is_active


def test_borrow_no_liquidity_reverts(
    lending_pool,
    mock_usdc,
    deployer,
    borrower,
    pricer,
    premium_oracle,
    setup_market,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
    funded_borrower,
):
    setup_premium(premium_oracle, pricer, borrower)
    with boa.env.prank(pricer):
        price_feed.push_price(7 * 10**17)
    with boa.env.prank(lending_pool.address):
        collateral_manager.deposit_collateral(borrower, 500 * 10**18, token_id)

    with boa.reverts("insufficient liquidity"):
        do_borrow(lending_pool, borrower, 10_000 * 10**6)


def test_borrow_when_paused_reverts(lending_pool, deployer, borrower, setup_market):
    with boa.env.prank(deployer):
        lending_pool.pause()

    with boa.reverts("not open"):
        do_borrow(lending_pool, borrower, 10_000 * 10**6)


def test_borrow_duration_too_short_reverts(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    funded_lender,
    setup_market,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    setup_borrow_prerequisites(
        lending_pool, collateral_manager, mock_ctf, price_feed,
        premium_oracle, pricer, deployer, borrower, lender, token_id,
        deposit_amount,
    )

    with boa.reverts("duration too short"):
        do_borrow(lending_pool, borrower, 10_000 * 10**6, duration=100)


def test_borrow_duration_too_long_reverts(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    funded_lender,
    setup_market,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    setup_borrow_prerequisites(
        lending_pool, collateral_manager, mock_ctf, price_feed,
        premium_oracle, pricer, deployer, borrower, lender, token_id,
        deposit_amount,
    )

    with boa.reverts("duration too long"):
        do_borrow(lending_pool, borrower, 10_000 * 10**6, duration=604800 + 1)


# --- Repay ---


def test_repay(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
    funded_lender,
    setup_market,
):
    deposit_amount = 100_000 * 10**6
    borrow_amount = 10_000 * 10**6

    setup_borrow_prerequisites(
        lending_pool, collateral_manager, mock_ctf, price_feed,
        premium_oracle, pricer, deployer, borrower, lender, token_id,
        deposit_amount,
    )

    do_borrow(lending_pool, borrower, borrow_amount)

    loan = lending_pool.loans(borrower)
    principal = loan[0]

    with boa.env.prank(deployer):
        mock_usdc.mint(borrower, principal)
    with boa.env.prank(borrower):
        mock_usdc.approve(lending_pool.address, principal)
        lending_pool.repay(borrower)

    loan_after = lending_pool.loans(borrower)
    assert loan_after[5] is False  # is_active
    assert lending_pool.total_borrowed() == 0


# --- Pool state management ---


def test_pause_unpause(lending_pool, deployer):
    with boa.env.prank(deployer):
        lending_pool.pause()
    assert lending_pool.pool_state() == 2  # PAUSED flag

    with boa.env.prank(deployer):
        lending_pool.unpause()
    assert lending_pool.pool_state() == 1  # OPEN flag


def test_set_loan_duration_bounds(lending_pool, deployer):
    with boa.env.prank(deployer):
        lending_pool.set_loan_duration_bounds(3600, 2592000)
    assert lending_pool.min_loan_duration() == 3600
    assert lending_pool.max_loan_duration() == 2592000


def test_set_loan_duration_bounds_non_admin_reverts(lending_pool, lender):
    with boa.reverts():
        with boa.env.prank(lender):
            lending_pool.set_loan_duration_bounds(3600, 2592000)


# --- Handle liquidation proceeds ---


def test_handle_liquidation_proceeds(
    lending_pool,
    mock_usdc,
    deployer,
    lender,
    borrower,
    pricer,
    premium_oracle,
    funded_lender,
    setup_market,
    liquidator_contract,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    borrow_amount = 10_000 * 10**6

    setup_borrow_prerequisites(
        lending_pool, collateral_manager, mock_ctf, price_feed,
        premium_oracle, pricer, deployer, borrower, lender, token_id,
        deposit_amount,
    )

    do_borrow(lending_pool, borrower, borrow_amount)

    loan = lending_pool.loans(borrower)
    principal = loan[0]
    premium_paid = loan[2]

    premium_reserve_before = lending_pool.premium_reserve()
    assert premium_reserve_before == premium_paid

    recovered = principal - 500 * 10**6
    shortfall = principal - recovered

    with boa.env.prank(deployer):
        mock_usdc.mint(liquidator_contract.address, recovered)
    with boa.env.prank(liquidator_contract.address):
        mock_usdc.approve(lending_pool.address, recovered)
        lending_pool.handle_liquidation_proceeds(borrower, recovered)

    loan_after = lending_pool.loans(borrower)
    assert loan_after[5] is False  # is_active
    assert lending_pool.total_borrowed() == 0

    if premium_reserve_before >= shortfall:
        assert lending_pool.premium_reserve() == premium_reserve_before - shortfall
    else:
        assert lending_pool.premium_reserve() == 0


# --- Borrow edge cases ---


def test_borrow_stale_price_reverts(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    funded_lender,
    setup_market,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    setup_borrow_prerequisites(
        lending_pool, collateral_manager, mock_ctf, price_feed,
        premium_oracle, pricer, deployer, borrower, lender, token_id,
        deposit_amount,
    )
    boa.env.time_travel(seconds=3601)

    with boa.reverts("price is stale"):
        do_borrow(lending_pool, borrower, 10_000 * 10**6)


def test_borrow_circuit_breaker_reverts(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    funded_lender,
    setup_market,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    do_deposit(lending_pool, lender, deposit_amount)
    setup_premium(premium_oracle, pricer, borrower)

    with boa.env.prank(deployer):
        mock_ctf.mint(borrower, token_id, 500 * 10**18)
    with boa.env.prank(borrower):
        mock_ctf.setApprovalForAll(collateral_manager.address, True)
    with boa.env.prank(lending_pool.address):
        collateral_manager.deposit_collateral(borrower, 500 * 10**18, token_id)

    with boa.env.prank(pricer):
        price_feed.push_price(5 * 10**17)
    with boa.env.prank(pricer):
        price_feed.push_price(2 * 10**17)

    with boa.reverts("circuit breaker active"):
        do_borrow(lending_pool, borrower, 10_000 * 10**6)


def test_borrow_no_collateral_reverts(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    funded_lender,
    setup_market,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    do_deposit(lending_pool, lender, deposit_amount)
    setup_premium(premium_oracle, pricer, borrower)
    with boa.env.prank(pricer):
        price_feed.push_price(7 * 10**17)

    with boa.reverts():
        do_borrow(lending_pool, borrower, 10_000 * 10**6)


def test_borrow_past_cutoff_reverts(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    funded_lender,
    setup_market,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    setup_borrow_prerequisites(
        lending_pool, collateral_manager, mock_ctf, price_feed,
        premium_oracle, pricer, deployer, borrower, lender, token_id,
        deposit_amount,
    )

    boa.env.time_travel(seconds=2_000_000_000)

    with boa.reverts("past cutoff"):
        do_borrow(lending_pool, borrower, 10_000 * 10**6)


def test_withdraw_insufficient_liquidity_reverts(
    lending_pool,
    mock_usdc,
    lender,
    borrower,
    deployer,
    pricer,
    premium_oracle,
    funded_lender,
    setup_market,
    collateral_manager,
    mock_ctf,
    price_feed,
    token_id,
):
    deposit_amount = 100_000 * 10**6
    borrow_amount = 80_000 * 10**6

    setup_borrow_prerequisites(
        lending_pool, collateral_manager, mock_ctf, price_feed,
        premium_oracle, pricer, deployer, borrower, lender, token_id,
        deposit_amount, collateral_amount=2000 * 10**18,
    )

    do_borrow(lending_pool, borrower, borrow_amount)

    lender_shares = lending_pool.shares(lender)

    with boa.reverts("insufficient liquidity"):
        with boa.env.prank(lender):
            lending_pool.withdraw(lender_shares)
