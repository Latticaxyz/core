# @version ^0.4.3

"""
@title Lending Pool
@notice Lending pool for prediction market loans.
        Lenders deposit USDC.e and earn yield from borrower interest.
        Borrowers post CTF outcome tokens as collateral and pay a
        fixed interest rate (lender yield) plus a risk premium
        (priced by WARBIRD) upfront for the epoch.
@dev    Key properties:
        - NOT an ERC4626 vault — epoch-based with fixed pricing.
        - Lenders deposit/withdraw USDC.e. Withdrawals may queue if
          utilization is high.
        - Borrowers borrow USDC.e against CTF collateral. Interest +
          premium deducted at origination.
        - No loans can be opened after the resolution cutoff.
        - All loans expire at min(epoch_end, cutoff). No loan ever
          crosses a market resolution.
        - At expiry: borrower repays, rolls (if next epoch fits
          before cutoff), or gets liquidated.

        ACCOUNTING MODEL (three balances):

        1. AVAILABLE LIQUIDITY
           = total_deposits - active_borrows
           What can be lent out or withdrawn right now.

        2. ACCRUED INTEREST (lender yield)
           Fixed interest rate set by governance (global or per-epoch).
           Deducted from borrower at origination → added to pool.
           Appreciates lender shares pro-rata.
           This IS the lender's return.

        3. PREMIUM RESERVE (risk buffer)
           Per-(conditionId, epoch) premium set by WARBIRD model.
           Deducted from borrower at origination → goes to reserve.
           Does NOT go to lenders directly.
           Purpose: absorb liquidation shortfalls.
             - Liquidation recovers less than debt → shortfall
               covered from reserve.
             - Epoch closes cleanly → surplus stays in reserve.
           Reserve surplus disposition (governance decision):
             a) Stay in reserve (grow buffer over time)
             b) Distribute to lenders as bonus yield
             c) Send to protocol treasury
             d) Some combination of the above

        WHY SEPARATE:
        If premiums went straight to lenders, there's no loss buffer.
        The premium IS the insurance. The interest is the yield.
        Separating them gives clean accounting:
          - Lenders know their guaranteed yield (interest rate).
          - Reserve health is visible on-chain.
          - Governance can tune interest (demand) independently of
            premium (risk) — they serve different purposes.

        CAPITAL ALLOCATION:
        Single pool model. All lender deposits are fungible.
        Per-market exposure capped by EpochManager's market registry
        (max_exposure_cap per conditionId). Borrower calls
        borrow(conditionId, amount) → pool checks:
          1. Market is whitelisted (registered in EpochManager)
          2. Market is not past resolution cutoff
          3. Available liquidity >= amount
          4. Market exposure cap not exceeded
          5. PriceFeed is not stale and circuit breaker not tripped
        If all pass → transfer USDC.e to borrower's Safe.

        Lenders are effectively buying the "Lattica curated basket" —
        they trust admin's market selection + WARBIRD's pricing.
        Isolated per-market pools can be added later if needed.

        WALLET INTEGRATION:
        - All user addresses are Safe wallets (Gnosis Safe).
        - Two onboarding paths produce the same Safe type:
          Path A: browser wallet (MetaMask etc) → deterministic Safe
          Path B: Privy email/social → embedded EOA → deterministic Safe
        - The Safe must have USDC.e approved for this pool (ERC20 approve).
        - Approval is batched with Polymarket's standard approvals
          during user session setup (via Builder Relayer, gasless).
        - All txs can be routed through Polymarket's Builder Relayer
          for gasless execution. The contracts themselves don't need
          gasless awareness — the relayer submits standard txs.
"""
