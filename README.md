# lvxcas.github.io

Personal site. Static, no JavaScript, no framework. Served by GitHub Pages.

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
supply `commits_mine` / `commits_total` yourself.

## Design

The reasoning behind every value — typeface, contrast ratio, measure, the rail,
what was deliberately left out — is in `research/DESIGN-SPEC.md`, kept locally and gitignored by default.

Budget: under 100KB total. Currently about 62KB, of which 41KB is fonts.

## Local preview

```bash
python3 -m http.server 8377
```
