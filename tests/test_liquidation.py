"""
Tests for the Liquidator.

Covers:
- Trigger: health factor < 1.0
- Trigger: epoch expired, loan not repaid
- Trigger: resolution cutoff hit, loan not settled
- Partial liquidation
- Full liquidation
- Sells collateral via CTF Exchange (Polymarket orderbook)
  - Binary: CTFExchange at 0x4bFb41d5...
  - NegRisk: NegRiskCtfExchange at 0xC5d563A3...
  - Signature types: EOA, POLY_PROXY, POLY_GNOSIS_SAFE
- Recovered USDC.e returned to pool
- Liquidator fee/discount
- Shortfall: recovered < debt → difference drawn from premium reserve
- Shortfall: reserve sufficient → pool whole, lenders unaffected
- Shortfall: reserve insufficient → bad debt socialized to lenders
- Edge: no orderbook liquidity → graceful handling
- Edge: borrower repays just before liquidation
"""
