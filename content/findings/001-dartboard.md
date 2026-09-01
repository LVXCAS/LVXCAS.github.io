id: 001
date: 2026-08
verdict: FOUND NOTHING
apparatus: ATLAS / atlas-dartboard
title: 5,423 strategies, and the best one is worse than luck
figure: census
rail: |
  **5,423** variants
  best   **1.34**
  E[best] 1.74
  RC p   1.000
---
I ran every variant through Deflated Sharpe, PBO/CSCV, White's Reality Check, Hansen's SPA, and BH–FDR on SPY, 1993 to 2026.

The best variant scored 1.34. Searching 5,423 times through pure noise is expected to produce a best of about 1.74. The winner did not clear the bar that randomness alone sets, so there is no strategy here to report, and reporting that is the result.

One variant did clear it, and it was a bug. `gap_fade` was reading `close_to_open[t]`, which is the exact return it was trading. Every statistical test passed it. The fix was not statistical: nothing in the gauntlet can see an anchor sitting on the outcome, so the guard has to be structural and sit upstream of the search.
