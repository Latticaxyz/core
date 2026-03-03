# @version ^0.4.3

"""
@title Liquidator
@notice Liquidates expired or underwater borrower positions by
        selling collateral into Polymarket's orderbook.
@dev    Trigger conditions (ANY of):
        1. Health factor < 1.0 (collateral value dropped)
        2. Epoch expired and loan not repaid
        3. Market hit resolution cutoff and loan not settled

        Liquidation process:
        1. Anyone calls liquidate(borrower, conditionId, epoch)
        2. Contract seizes CTF outcome tokens from CollateralManager
        3. Sells via CTF Exchange (Polymarket orderbook)
           - Binary markets: CTFExchange (0x4bFb41d5...)
           - Multi-outcome (NegRisk): NegRiskCtfExchange (0xC5d563A3...)
           - Order signing uses SignatureType enum:
             EOA (0), POLY_PROXY (1), POLY_GNOSIS_SAFE (2)
        4. Recovered USDC.e returned to LendingPool
        5. Liquidator receives incentive fee
        6. If recovered < debt → shortfall covered from premium reserve
        7. If reserve insufficient → bad debt socialized to lenders
           (should be rare if WARBIRD pricing is accurate)

        Since lending is cut off before resolution, the Liquidator
        never has to handle post-resolution token redemption.

        Liquidation txs can be routed through the Builder Relayer
        for gasless execution (off-chain, no contract awareness needed).
"""
