"""
Tests for the Liquidator.

- Liquidation trigger when collateral value < threshold
- Partial and full liquidation
- Liquidation discount / incentive
- Edge case: market resolves during liquidation
- Edge case: outcome token goes to 0 (total loss)
"""
