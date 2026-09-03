id: E002
date: 2026-09-03
verdict: RETRACTED
kind: erratum
apparatus: this page, as first published on 2026-09-01
title: This page miscounted its own author
rail: |
  **3** numbers struck
  **2** now read, not typed
---
The first version of this page said of the Presidential AI Challenge entry that ~~roughly half of its 59 commits are mine~~, listed ATLAS as ~~1,841 / 1,841 commits~~, and gave it ~~156 test files~~. All three numbers were typed, not read.

The API reads 50 of 59 for the challenge entry. The ATLAS branch reads 1,805 of 1,813 through the same API: 7 commits are a teammate's and 1 is committed as "Claude Code Assistant". My local clone is 28 commits further ahead of that, all mine, none of them pushed. The test count is 370 tracked files named test_*.py; I no longer know how 156 was counted. I undercounted my work in one row and overcounted it in the other, in the same table.

The challenge entry is now listed above with its counts read at build time. ATLAS is now counted from its branch on the private repository through my own token, so it is read too, but you still cannot check it.
