"""
Tests for the PriceFeed (VWAP + deviation-based).

Covers:
- Push new price
- Only authorized updater can push
- Price bounded to [0, 1e18]
- Deviation check: update rejected if delta < threshold
- Staleness: price older than limit → stale flag
- Cannot open new borrows with stale price
- Can still liquidate with stale price (conservative)
- Circuit breaker: >Y% move in Z blocks → trips
- Circuit breaker: no new loans while tripped
- Circuit breaker: liquidations still execute while tripped
- Circuit breaker: auto-resets after cooldown
- Price for unknown conditionId → reverts
"""
