"""
Tests for the Oracle Adapter.

- Price fetch for active (unresolved) outcome tokens
- Price after market resolution (winning token → 1, losing → 0)
- Stale price handling
- Invalid conditionId / positionId
- Price bounds (0 ≤ price ≤ 1 USDC per outcome token)
"""
