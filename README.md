# lvxcas.github.io

Personal site. Static, no framework, one small vanilla script for motion. Served by GitHub Pages.

## How it works

`build.py` reads content from `content/` and writes `index.html`. There is no
runtime dependency and nothing outside the Python standard library.

The one thing worth knowing: **commit counts in the project table are read from
the GitHub API at build time, never typed by hand.** That is what keeps the
`mine / total` column honest in month six rather than only on launch day.

```bash
python3 build.py             # fetch live counts, then rebuild
python3 build.py --offline   # rebuild using content/commit-cache.json
```

Then check the diff and commit `index.html`.

## Adding a finding

Drop a Markdown file in `content/findings/`. Files are ordered by filename.

```
id: 003
date: 2026-09
verdict: FOUND NOTHING
apparatus: ATLAS / some-package
title: What the claim is
rail: |
  n        1,204
  p        0.31
---
Body paragraphs. Blank line between them.

Supports `code`, **bold**, [links](https://example.com), and ~~struck text~~.
```

`kind: erratum` puts the entry in the Errata section and turns the verdict red.
The `rail` block is the right-hand column: put measured quantities there and
nothing else. If nothing was measured, leave it out — the blank is the point.

## Adding a project

Edit `content/projects.json`. Set `"repo"` to the GitHub repository name and the
commit counts fill themselves in. Set `"repo": null` for anything private and
supply `commits_mine` / `commits_total` yourself, or set `"count_repo"` (and
optionally `"count_branch"`) to have counts read from a private repo's API
without rendering a link to it.

## Design

A lab notebook that is alive: paper, ink, and one red pencil for corrections.
The original reasoning behind the type, contrast, measure and the rail is in
`research/DESIGN-SPEC.md`, kept locally and gitignored by default.

- **Plates.** The playable projects (`voidbreaker`, `pixel-poker`) are full-bleed
  plates in the colours of their own subjects, configured in `PLATES` in
  `build.py`. A project named there is shown as a plate and left out of the
  ledger. voidbreaker's palette is the literal RGB from its `config.py`;
  pixel-poker's is sampled from its table screenshots.
- **Ledger.** Every other project is a row with its period, its `mine / total`
  commit counts, and a bar whose filled share is `mine`. Caveats (`!` lines)
  get a red mark and are counted per row.
- **Motion.** `motion.js` (vanilla, no library) reveals sections on scroll,
  counts numbers up to the value already in the HTML, fills the commit bars,
  rules the notebook rail, stamps verdicts, traces the census figure and draws
  each erratum's strike-through. Everything starts from its final state in the
  HTML, so with JavaScript off or `prefers-reduced-motion: reduce` the page is
  complete and still. The script also adds a light/dark switch (saved in
  `localStorage`); without it the page follows the system theme.

Budget: first load (HTML, CSS, JS, fonts) under 250KB. Currently about 106KB,
of which 41KB is fonts. The screenshots (about 133KB) are lazy-loaded on top.

## Local preview

```bash
python3 -m http.server 8377
```
