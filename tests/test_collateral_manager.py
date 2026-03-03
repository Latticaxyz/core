"""
Tests for the CollateralManager.

Covers:
- Deposit CTF ERC1155 outcome tokens as collateral
- Withdraw collateral after repayment
- Collateral factor per conditionId (read from EpochManager registry)
- Health factor calculation (reads PriceFeed VWAP)
- Position tracking: (borrower, conditionId, indexSet, epoch)
- Reject collateral for non-whitelisted markets (not registered)
- Reject collateral for paused markets
- Reject collateral for markets past resolution cutoff
- Max exposure cap per market enforcement (from EpochManager registry)
- onERC1155Received hook
- Health factor transitions: healthy → buffer → liquidatable
"""
