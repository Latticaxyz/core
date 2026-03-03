"""
Tests for the LendingPool.

Covers:
- Lender deposit / withdraw USDC.e
- Share accounting (pro-rata yield from interest, NOT premiums)
- Borrower opens loan: posts CTF collateral, pays interest + premium, receives USDC.e
- Interest deducted at origination → added to pool (lender yield)
- Premium deducted at origination → added to reserve (risk buffer)
- Interest rate set by governance, can be updated
- Borrower repays at epoch end → reclaims collateral
- Borrower cannot borrow after resolution cutoff
- Borrower cannot borrow on non-whitelisted market
- Borrower cannot borrow exceeding market exposure cap
- Borrower cannot borrow with stale PriceFeed
- Withdrawal queue when utilization is high
- Pool accounting: available liquidity, accrued interest, premium reserve
- Reserve: shortfall deducted after liquidation
- Reserve: surplus accumulates across epochs
- Reserve: governance can trigger surplus disposition
"""
