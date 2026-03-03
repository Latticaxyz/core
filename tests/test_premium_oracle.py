"""
Tests for the PremiumOracle (commit-reveal + signed quotes).

Covers:
- commit() stores hash
- reveal() matches hash, activates premium
- Reveal before REVEAL_DELAY blocks → reverts
- Reveal with wrong salt → reverts
- Only authorized pricer can commit/reveal
- Stale premium (committed but never revealed) → expires
- EIP-712 signed quote verification
- Signed quote must match on-chain revealed premium
- Signed quote with tampered premium → reverts
- Signed quote with expired deadline → reverts
- Pricer rotation by governance
"""
