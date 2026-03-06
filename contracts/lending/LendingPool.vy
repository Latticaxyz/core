# pragma version ~=0.4.3

from snekmate.auth import access_control

initializes: access_control

exports: (
    access_control.hasRole,
    access_control.getRoleAdmin,
    access_control.grantRole,
    access_control.revokeRole,
    access_control.renounceRole,
    access_control.set_role_admin,
    access_control.supportsInterface,
    access_control.DEFAULT_ADMIN_ROLE,
)

interface IERC20:
    def transfer(_to: address, _amount: uint256) -> bool: nonpayable
    def transferFrom(_from: address, _to: address, _amount: uint256) -> bool: nonpayable
    def balanceOf(_account: address) -> uint256: view

interface ICollateralManager:
    def deposit_collateral(_borrower: address, _amount: uint256, _token_id: uint256): nonpayable
    def release_collateral(_borrower: address): nonpayable
    def set_debt(_borrower: address, _debt: uint256): nonpayable
    def get_health_factor(_borrower: address) -> uint256: view

interface IPremiumOracle:
    def get_premium(_epoch: uint256) -> uint256: view

interface IInterestRateModel:
    def get_rate(_utilization_bps: uint256) -> uint256: view

interface IMarketRegistry:
    def get_market_params(_condition_id: bytes32) -> (uint256, uint256, uint256, uint256, uint256, bool, bool): view
    def get_cutoff(_condition_id: bytes32) -> uint256: view

flag EpochState:
    OPEN
    PAUSED
    CUTOFF
    EXPIRED

struct Loan:
    principal: uint256
    interest_paid: uint256
    premium_paid: uint256
    rate_bps: uint256
    epoch: uint256
    epoch_end: uint256
    is_active: bool

event Deposit:
    lender: address
    amount: uint256
    shares: uint256

event Withdraw:
    lender: address
    amount: uint256
    shares: uint256

event Borrow:
    borrower: address
    amount: uint256
    interest: uint256
    premium: uint256
    rate_bps: uint256

event Repay:
    borrower: address
    amount: uint256

event LiquidationSettled:
    borrower: address
    recovered: uint256

event ShortfallCovered:
    borrower: address
    shortfall: uint256

event EpochAdvanced:
    epoch: uint256

LIQUIDATOR_ROLE: constant(bytes32) = keccak256("LIQUIDATOR_ROLE")
MAX_BPS: constant(uint256) = 10000

condition_id: public(bytes32)
usdc_e: public(address)
collateral_manager: public(address)
premium_oracle: public(address)
interest_rate_model: public(address)
market_registry: public(address)
total_deposits: public(uint256)
total_borrowed: public(uint256)
premium_reserve: public(uint256)
shares: public(HashMap[address, uint256])
total_shares: public(uint256)
loans: public(HashMap[address, Loan])
current_epoch: public(uint256)
epoch_start: public(uint256)
epoch_duration: public(uint256)
epoch_state: public(EpochState)


@deploy
def __init__(
    _condition_id: bytes32,
    _usdc_e: address,
    _collateral_manager: address,
    _premium_oracle: address,
    _interest_rate_model: address,
    _market_registry: address,
    _epoch_duration: uint256,
):
    access_control.__init__()
    assert _usdc_e != empty(address), "empty usdc_e"
    assert _collateral_manager != empty(address), "empty collateral_manager"
    assert _premium_oracle != empty(address), "empty premium_oracle"
    assert _interest_rate_model != empty(address), "empty interest_rate_model"
    assert _market_registry != empty(address), "empty market_registry"
    assert _epoch_duration > 0, "zero epoch_duration"
    self.condition_id = _condition_id
    self.usdc_e = _usdc_e
    self.collateral_manager = _collateral_manager
    self.premium_oracle = _premium_oracle
    self.interest_rate_model = _interest_rate_model
    self.market_registry = _market_registry
    self.epoch_duration = _epoch_duration
    self.current_epoch = 1
    self.epoch_start = block.timestamp
    self.epoch_state = EpochState.OPEN


@external
def deposit(amount: uint256):
    assert amount > 0, "zero amount"
    assert (
        self.epoch_state == EpochState.OPEN
        or self.epoch_state == EpochState.PAUSED
    ), "deposits disabled"
    extcall IERC20(self.usdc_e).transferFrom(msg.sender, self, amount)
    new_shares: uint256 = 0
    if self.total_shares == 0:
        new_shares = amount
    else:
        new_shares = (amount * self.total_shares) // self.total_deposits
    self.shares[msg.sender] += new_shares
    self.total_shares += new_shares
    self.total_deposits += amount
    log Deposit(lender=msg.sender, amount=amount, shares=new_shares)


@external
def withdraw(share_amount: uint256):
    assert share_amount > 0, "zero shares"
    assert self.shares[msg.sender] >= share_amount, "insufficient shares"
    value: uint256 = (share_amount * self.total_deposits) // self.total_shares
    available: uint256 = self.total_deposits - self.total_borrowed
    assert value <= available, "insufficient liquidity"
    self.shares[msg.sender] -= share_amount
    self.total_shares -= share_amount
    self.total_deposits -= value
    extcall IERC20(self.usdc_e).transfer(msg.sender, value)
    log Withdraw(lender=msg.sender, amount=value, shares=share_amount)


@external
def borrow(amount: uint256, borrower: address):
    assert self.epoch_state == EpochState.OPEN, "not open"
    assert amount > 0, "zero amount"
    assert not self.loans[borrower].is_active, "loan exists"

    cutoff: uint256 = staticcall IMarketRegistry(self.market_registry).get_cutoff(
        self.condition_id
    )
    assert block.timestamp < cutoff, "past cutoff"

    params: (uint256, uint256, uint256, uint256, uint256, bool, bool) = staticcall IMarketRegistry(
        self.market_registry
    ).get_market_params(self.condition_id)
    assert params[5], "market not active"
    assert not params[6], "market paused"
    assert self.total_borrowed + amount <= params[1], "exposure cap exceeded"

    available: uint256 = self.total_deposits - self.total_borrowed
    assert amount <= available, "insufficient liquidity"

    new_borrowed: uint256 = self.total_borrowed + amount
    utilization: uint256 = (new_borrowed * MAX_BPS) // self.total_deposits
    rate_bps: uint256 = staticcall IInterestRateModel(self.interest_rate_model).get_rate(
        utilization
    )
    interest: uint256 = (amount * rate_bps) // MAX_BPS

    premium_bps: uint256 = staticcall IPremiumOracle(self.premium_oracle).get_premium(
        self.current_epoch
    )
    premium: uint256 = (amount * premium_bps) // MAX_BPS

    net: uint256 = amount - interest - premium
    assert net > 0, "net zero"

    self.total_borrowed += amount
    self.total_deposits += interest
    self.premium_reserve += premium

    epoch_end: uint256 = self.epoch_start + self.epoch_duration
    if epoch_end > cutoff:
        epoch_end = cutoff

    self.loans[borrower] = Loan(
        principal=amount,
        interest_paid=interest,
        premium_paid=premium,
        rate_bps=rate_bps,
        epoch=self.current_epoch,
        epoch_end=epoch_end,
        is_active=True,
    )

    extcall IERC20(self.usdc_e).transfer(borrower, net)
    log Borrow(
        borrower=borrower,
        amount=amount,
        interest=interest,
        premium=premium,
        rate_bps=rate_bps,
    )


@external
def repay(borrower: address):
    loan: Loan = self.loans[borrower]
    assert loan.is_active, "no active loan"
    self.total_borrowed -= loan.principal
    self.loans[borrower].is_active = False
    extcall IERC20(self.usdc_e).transferFrom(msg.sender, self, loan.principal)
    extcall ICollateralManager(self.collateral_manager).release_collateral(borrower)
    log Repay(borrower=borrower, amount=loan.principal)


@external
def handle_liquidation_proceeds(borrower: address, recovered: uint256):
    access_control._check_role(LIQUIDATOR_ROLE, msg.sender)
    loan: Loan = self.loans[borrower]
    assert loan.is_active, "no active loan"
    self.loans[borrower].is_active = False
    self.total_borrowed -= loan.principal
    extcall IERC20(self.usdc_e).transferFrom(msg.sender, self, recovered)
    if recovered < loan.principal:
        shortfall: uint256 = loan.principal - recovered
        if self.premium_reserve >= shortfall:
            self.premium_reserve -= shortfall
        else:
            self.total_deposits -= (shortfall - self.premium_reserve)
            self.premium_reserve = 0
    log LiquidationSettled(borrower=borrower, recovered=recovered)


@external
def cover_shortfall(borrower: address, shortfall: uint256):
    access_control._check_role(LIQUIDATOR_ROLE, msg.sender)
    if self.premium_reserve >= shortfall:
        self.premium_reserve -= shortfall
    else:
        self.total_deposits -= (shortfall - self.premium_reserve)
        self.premium_reserve = 0
    log ShortfallCovered(borrower=borrower, shortfall=shortfall)


@view
@external
def get_share_value(share_amount: uint256) -> uint256:
    if self.total_shares == 0:
        return 0
    return (share_amount * self.total_deposits) // self.total_shares


@external
def advance_epoch():
    access_control._check_role(access_control.DEFAULT_ADMIN_ROLE, msg.sender)
    self.current_epoch += 1
    self.epoch_start = block.timestamp
    cutoff: uint256 = staticcall IMarketRegistry(self.market_registry).get_cutoff(
        self.condition_id
    )
    if block.timestamp >= cutoff:
        self.epoch_state = EpochState.CUTOFF
    else:
        self.epoch_state = EpochState.OPEN
    log EpochAdvanced(epoch=self.current_epoch)


@external
def pause():
    access_control._check_role(access_control.DEFAULT_ADMIN_ROLE, msg.sender)
    self.epoch_state = EpochState.PAUSED


@external
def unpause():
    access_control._check_role(access_control.DEFAULT_ADMIN_ROLE, msg.sender)
    self.epoch_state = EpochState.OPEN
