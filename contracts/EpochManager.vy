# @version ^0.4.3

"""
@title Epoch Manager
@notice Manages epoch lifecycle, resolution cutoffs, and the
        market registry (whitelist) for approved markets.
@dev    MARKET REGISTRY:
        Admin-gated onboarding. Only markets explicitly registered
        by the admin (or governance multisig) can be used as
        collateral. Registration stores per-market parameters:

        onboard_market(conditionId, resolution_time, params):
          - collateral_factor: LTV ratio (e.g. 70% for liquid markets,
            50% for thin ones). Read by CollateralManager.
          - max_exposure_cap: maximum USDC.e lent against this market.
            Prevents any single conditionId from dominating the pool.
            Read by LendingPool on borrow().
          - min_liquidity_depth: minimum Polymarket orderbook depth
            required. Below this, market is paused for new borrows.
            Checked off-chain by backend, enforced via pause_market().
          - resolution_time: when the market resolves (from Polymarket).
          - cutoff: resolution_time - buffer. Computed on registration.

        Markets can be paused (pause_market) or decommissioned
        (deboard_market) by admin. Pausing blocks new loans but
        lets existing loans settle. Deboarding after all loans
        are settled removes the market entirely.

        If a conditionId is not registered, ALL downstream contracts
        reject it: CollateralManager won't accept the tokens,
        LendingPool won't originate, PriceFeed has no price.

        EPOCH LIFECYCLE:
        Epochs are bounded by two constraints:
        1. Epoch duration (e.g. 7 days) — the default lending period.
        2. Resolution cutoff — (resolution_time - buffer). Hard wall.

        Effective epoch end = min(epoch_start + duration, cutoff).

        States per market:
        - OPEN: loans can be created, rolled.
        - PAUSED: no new loans, existing loans can settle normally.
        - CUTOFF: no new loans. Existing loans must settle.
        - EXPIRED: all loans past expiry, liquidation enforced.

        Roll logic: a borrower can roll into a new epoch ONLY if
        the new epoch's end is before the cutoff. Otherwise the
        roll is rejected and borrower must repay.
"""
