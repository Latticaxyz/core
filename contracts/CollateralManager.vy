# @version ^0.4.3

"""
@title Collateral Manager
@notice Accepts and tracks CTF ERC1155 outcome tokens posted as
        collateral by borrowers.
@dev    - Each position: (borrower, conditionId, indexSet, epoch).
        - Reads per-market parameters from EpochManager's market registry:
          collateral_factor, max_exposure_cap. Rejects conditionIds
          that are not registered (not whitelisted).
        - Health factor = (collateral_value * collateral_factor) / debt.
          Reads price from PriceFeed (VWAP).
          Reads collateral_factor from EpochManager (per-market).
        - Buffer zone: healthy > 1.2, liquidatable < 1.0, buffer
          between 1.0-1.2 triggers warnings.
        - Rejects collateral for markets past resolution cutoff
          (reads EpochManager).
        - Rejects collateral for paused markets (reads EpochManager).
        - Max collateral per market: enforces max_exposure_cap from
          EpochManager's market registry (Mango-style attack mitigation).
        - Implements onERC1155Received to accept CTF token deposits.

        WALLET INTEGRATION:
        - The borrower address is a Safe wallet (Gnosis Safe).
        - Users who connect the same EOA they use on Polymarket.com
          get the same deterministic Safe, so their existing CTF
          positions are already in the Safe — no transfers needed.
        - The Safe must have setApprovalForAll on the CTF contract
          granting this CollateralManager as operator. This approval
          is batched with Polymarket's standard approvals during the
          user session setup (via Builder Relayer, gasless).
        - The contract transfers CTF tokens FROM the Safe on deposit
          and TO the Safe on withdrawal (after repayment).
"""
