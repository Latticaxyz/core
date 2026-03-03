"""
Tests for the EpochManager (market registry + epoch lifecycle).

Market registry covers:
- onboard_market() only callable by admin
- Per-market params stored: collateral_factor, max_exposure_cap,
  min_liquidity_depth, resolution_time, cutoff
- Cutoff = resolution_time - buffer (computed correctly)
- pause_market() blocks new loans, existing loans settle normally
- deboard_market() only after all loans settled
- Non-registered conditionId rejected by all downstream contracts
- Multiple markets with different parameters

Epoch lifecycle covers:
- Epoch states: OPEN → PAUSED → CUTOFF → EXPIRED
- Epoch duration enforcement
- Effective epoch end = min(epoch_start + duration, cutoff)
- No new loans after cutoff
- No new loans when market is paused
- Roll blocked if next epoch crosses cutoff
- Roll succeeds if next epoch fits before cutoff
- Multiple markets with different resolution times
- Admin can update collateral_factor and max_exposure_cap
"""
