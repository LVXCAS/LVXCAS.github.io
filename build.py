#!/usr/bin/env python3
"""
Builds index.html.

The point of this script: commit counts are READ FROM THE GITHUB API, never typed.
That is what keeps "honestly scaled" true in month six rather than only at launch.
Run it, check the diff, commit the result. No dependencies outside the stdlib.

    python3 build.py            # fetch live counts
    python3 build.py --offline  # reuse counts cached in content/commit-cache.json
"""
import json, os, re, subprocess, sys, html, datetime, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(ROOT, *a)
OFFLINE = "--offline" in sys.argv

# Every git identity the author has committed under. Missing one understates his own work.
AUTHORS = ("LVXCAS", "lucasoghigian@gmail.com", "lucas.390437@nv.ccsd.net")


# ---------------------------------------------------------------- github

def _gh(path):
    """Prefer the gh CLI (authenticated, higher rate limit); fall back to anonymous."""
    try:
        out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=25)
        if out.returncode == 0:
            return json.loads(out.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    try:
        req = urllib.request.Request("https://api.github.com/" + path.lstrip("/"),
                                     headers={"Accept": "application/vnd.github+json",
                                              "User-Agent": "lvxcas-site-build"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"    ! {path}: {e}")
        return None


def _commit_shas_paginated(owner, repo, author, branch=None):
    """All commit SHAs by `author` in `repo` (optionally restricted to `branch`).

    The per-author query reads only one page unless paginated, which silently
    capped `mine` at 100. `gh api --paginate` follows the Link header itself; the
    anonymous fallback below follows it by hand for the same reason `commit_counts`
    does for `total`.
    """
    path = f"repos/{owner}/{repo}/commits?author={author}&per_page=100"
    if branch:
        path += f"&sha={branch}"
    try:
        out = subprocess.run(
            ["gh", "api", "--paginate", "--jq", ".[].sha", path],
            capture_output=True, text=True, timeout=60)
        if out.returncode == 0:
            return [s for s in out.stdout.splitlines() if s.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    shas = []
    url = "https://api.github.com/" + path
    while url:
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "lvxcas-site-build"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode())
                link = r.headers.get("Link", "")
        except Exception as e:
            # A partial list would understate `mine` and then be cached as truth.
            print(f"    ! {url}: {e}")
            return None
        if not isinstance(data, list):
            return None
        shas.extend(c["sha"] for c in data if isinstance(c, dict) and "sha" in c)
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = m.group(1) if m else None
    return shas


def commit_counts(owner, repo, branch=None):
    """(mine, total).

    `gh api -I` does not surface the Link header here, so the pagination trick that
    yields a true total is done with curl. Without it the total silently capped at
    "100+", which reported AIMUX (7,907 commits, a fork of OpenAI Codex) as "100+"
    and understated it by nearly eighty times. `branch` restricts both counts to
    one branch via `sha=<branch>`, for repos whose main branch is not the real one.
    """
    total = None
    sha_q = f"&sha={branch}" if branch else ""
    try:
        tok = subprocess.run(["gh", "auth", "token"], capture_output=True,
                             text=True, timeout=15).stdout.strip()
        hdr = subprocess.run(
            ["curl", "-sI", "-H", f"Authorization: Bearer {tok}",
             "-H", "Accept: application/vnd.github+json",
             f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1{sha_q}"],
            capture_output=True, text=True, timeout=25).stdout
        m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', hdr)
        if m:
            total = int(m.group(1))
    except Exception:
        pass
    if total is None:                       # small repo: one page holds everything
        d = _gh(f"repos/{owner}/{repo}/commits?per_page=100{sha_q}")
        total = len(d) if isinstance(d, list) else None

    # He has committed under more than one identity; querying only the account login
    # reported his own commits as someone else's (Wholesaling-Agents- read 2/4, not 4/4).
    seen = set()
    for who in AUTHORS:
        shas = _commit_shas_paginated(owner, repo, who, branch)
        if shas:
            seen.update(shas)
    mine = len(seen) if seen else None
    return mine, total


def resolve_counts(projects, owner):
    cache_path = P("content", "commit-cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    for p in projects:
        # count_repo reads counts for a repo without rendering a link to it, for
        # private repos; count_branch restricts the read to one branch of it.
        source = p.get("count_repo") or p.get("repo")
        if not source:
            continue                      # private or unpublished: counts are authored
        branch = p.get("count_branch")
        key = f"{source}@{branch}" if branch else source
        if OFFLINE and key in cache:
            p["commits_mine"], p["commits_total"] = cache[key]
            continue
        print(f"  fetching {key} ...")
        mine, total = commit_counts(owner, source, branch)
        if mine is None or total is None:
            if key in cache:
                print(f"    using cached counts for {key}")
                mine, total = cache[key]
            else:
                raise SystemExit(
                    f"\nBuild stopped: could not read commit counts for {key} and no cached "
                    f"value exists.\nThe page states these numbers come from the API, so it "
                    f"must not be built with a placeholder.\nCheck `gh auth status`, or pass "
                    f"--offline once a cache exists.")
        p["commits_mine"], p["commits_total"] = mine, total
        if isinstance(mine, int):
            cache[key] = [mine, total]
    json.dump(cache, open(cache_path, "w"), indent=2)
    return projects


# ---------------------------------------------------------------- markdown

def inline(s):
    """Deliberately small: the only inline syntax the site actually uses.

    Order matters. Escaping runs first, and no blanket text substitution runs after
    code spans and links exist: a global "--" to em-dash pass corrupted `--offline`
    inside <code> and mangled any href containing a double hyphen.
    """
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"~~(.+?)~~", r"<del>\1</del>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


def parse_entry(path):
    raw = open(path, encoding="utf-8").read()
    head, body = raw.split("\n---\n", 1)
    meta, key, buf = {}, None, []
    for line in head.splitlines():
        if key:                                   # inside a "key: |" block
            if line.startswith("  "):
                buf.append(line[2:]); continue
            meta[key] = "\n".join(buf); key, buf = None, []
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            k, v = m.groups()
            if v.strip() == "|":
                key = k
            else:
                meta[k] = v.strip()
    if key:
        meta[key] = "\n".join(buf)
    meta["body"] = [inline(p.strip()) for p in body.strip().split("\n\n") if p.strip()]
    return meta


# ---------------------------------------------------------------- figures

def census_svg():
    """The sorted profile of every variant searched.

    Rank is ordinal, so the x axis is normalised to a 0-1000 span. Drawing it at one
    user unit per variant produced a 27:1 ribbon that rendered as a hairline, and
    sub-pixel pattern tiles were dropped by the renderer outright.
    """
    W, BASE, NOISE, BEST = 1000.0, 75.0, 6.3, 22.1
    real = P("content", "data", "dartboard_sharpes.txt")
    provisional = not os.path.exists(real)
    if provisional:
        pts = open(P("content", "dartboard-envelope.txt")).read().split()
        raw = [(float(a), float(b)) for a, b in (q.split(",") for q in pts)]
        n = max(x for x, _ in raw) or 1.0
    else:
        vals = sorted(float(x) for x in open(real) if x.strip())
        TOP, BOT, H, n = 1.9, -1.9, 150, float(len(vals) - 1)
        y = lambda s: round((TOP - s) / (TOP - BOT) * H, 1)
        idx = sorted(set(list(range(0, len(vals), max(1, len(vals) // 220))) + [len(vals) - 1]))
        raw = [(0.0, y(0))] + [(float(i), y(vals[i])) for i in idx] + [(n, y(0))]
    poly = " ".join(f"{round(x / n * W, 2)},{yy}" for x, yy in raw)
    note = (" The shape here is provisional: it is drawn from a distribution matching the "
            "reported statistics, not from the 5,423 recorded values. Drop those into "
            "<code>content/data/dartboard_sharpes.txt</code> and rebuild to replace it."
            ) if provisional else ""
    return f'''<figure class="fig census" data-r>
  <svg class="strip" viewBox="-8 -22 1030 166" role="img" aria-label="The 5,423 strategy variants ordered by Sharpe ratio. The highest sits below a dashed line marking the best result expected from pure noise.">
    <polygon class="mass" points="{poly}" fill="var(--ink-muted)" fill-opacity="0.4"/>
    <polyline class="trace" pathLength="1" points="{poly}" fill="none" stroke="var(--ink-muted)" stroke-width="1.4" stroke-linejoin="round"/>
    <line x1="0" y1="{BASE}" x2="{W:.0f}" y2="{BASE}" stroke="var(--rule)" stroke-width="1"/>
    <line class="noise" x1="0" y1="{NOISE}" x2="{W:.0f}" y2="{NOISE}" stroke="var(--erratum)" stroke-width="1" stroke-dasharray="6 5"/>
    <text x="0" y="{NOISE - 5:.1f}" font-family="IBM Plex Mono, monospace" font-size="13" fill="var(--erratum)">best expected from pure noise &#160;1.74</text>
    <line class="best" x1="{W:.0f}" y1="{BASE}" x2="{W:.0f}" y2="{BEST}" stroke="var(--erratum)" stroke-width="3"/>
    <text x="{W - 8:.0f}" y="{BEST - 5:.1f}" text-anchor="end" font-family="IBM Plex Mono, monospace" font-size="13" fill="var(--erratum)">best actual 1.34</text>
    <text x="0" y="{BASE + 62:.0f}" font-family="IBM Plex Mono, monospace" font-size="12" fill="var(--ink-muted)">Sharpe 0.00</text>
    <text x="{W:.0f}" y="{BASE + 62:.0f}" text-anchor="end" font-family="IBM Plex Mono, monospace" font-size="12" fill="var(--ink-muted)">rank 5,423</text>
  </svg>
  <figcaption>Every variant tested, ordered by Sharpe, each occupying one column of the 5,423.
  At page width they merge into a single mass, and the mass is the argument: that is the size of
  the search. Of the 5,423, 4,620 scored. The dashed line is the best
  score 4,620 no-skill strategies would be expected to reach on their own; the red mark at the right is the best score actually achieved. It falls below the
  line.{note}</figcaption>
</figure>'''


OVERNIGHT_TABLE = '''<figure class="fig" data-r>
<div class="wide"><table>
  <thead><tr><th>Track</th><th class="num">CAGR</th><th class="num">Sharpe</th><th class="num">Max DD</th><th class="num">Nights</th></tr></thead>
  <tbody>
    <tr><td>Overnight, filtered</td><td class="num">3.09%</td><td class="num">0.66</td><td class="num">&minus;10.4%</td><td class="num">5,443</td></tr>
    <tr><td>Buy &amp; hold SPY</td><td class="num">10.95%</td><td class="num">0.64</td><td class="num">&minus;55.2%</td><td class="num">5,443</td></tr>
  </tbody>
</table></div>
<figcaption>Sorted by the variable under test rather than by date.</figcaption>
</figure>'''

FIGURES = {"census": census_svg, "overnight-table": lambda: OVERNIGHT_TABLE}


# ---------------------------------------------------------------- render
#
# Motion hooks: `data-r` marks an element motion.js reveals when it scrolls into
# view; `count` marks a number it counts up to; `data-stagger` staggers children.
# Every one of them is already in its final state in the HTML, so the page reads
# the same with JavaScript off or prefers-reduced-motion set.

def rail(text):
    return "\n".join(inline(l) for l in text.strip().splitlines()) if text else ""


def entry_html(e, site):
    erratum = e.get("kind") == "erratum"
    cls = " ret" if erratum else ""
    label = "Corrects" if erratum else "Apparatus"
    body = "\n".join(f"<p>{p}</p>" for p in e["body"])
    r = rail(e.get("rail", ""))
    fig = FIGURES[e["figure"]]() if e.get("figure") in FIGURES else ""
    return f'''<article class="row{' erratum' if erratum else ''}" id="{e['id']}" data-r>
<div class="prose">
<div class="tomb"><b>{e['id']}</b> &#160; {e['date']} &#160; <span class="verdict{cls}">{e['verdict']}</span><br>
  {label} &#160; {inline(e.get('apparatus',''))}</div>
<h3>{inline(e['title'])}</h3>
{body}
</div>
<div class="rail">{r}</div>
</article>
{fig}'''


def _n(v):
    return f"{v:,}" if isinstance(v, int) else str(v)


def _has_counts(p):
    return p.get("commits_mine") is not None and p.get("commits_total") is not None


def _counts(p):
    """mine / total, plus a bar whose filled share is mine. AIMUX's 8 of 7,907
    is meant to look as empty as it is."""
    if not _has_counts(p):
        return ""
    mine, total = p["commits_mine"], p["commits_total"]
    share = (mine / total) if isinstance(mine, int) and isinstance(total, int) and total else 0
    return (f'<span class="cm"><b class="count">{_n(mine)}</b>'
            f'<span class="sl"> / </span><span class="tot count">{_n(total)}</span></span>'
            f'<span class="bar" aria-hidden="true"><i style="--r:{share:.4f}"></i></span>'
            f'<span class="lbl">commits mine / total</span>')


def _period(p):
    return "&#8211;".join(p["period"])


def _evidence(p):
    # A leading "!" marks a caveat. A tick means verified-positive, so an
    # absence ("no tests") must not wear one.
    if not p.get("evidence"):
        return ""
    items = "".join(
        (f'<li class="caveat"><span class="vh">Caveat: </span>{inline(e[1:].strip())}</li>'
         if e.startswith("!") else f"<li>{inline(e)}</li>")
        for e in p["evidence"])
    return f'<ul class="ev">{items}</ul>'


def ledger_row(i, p, owner):
    """One project in the ledger. The right-hand columns carry only measured
    quantities; if a project has none worth stating, they stay empty."""
    name = (f'<a href="https://github.com/{owner}/{p["repo"]}">{p["name"]}</a>'
            if p.get("repo") else p["name"])
    priv = f' <span class="priv">{inline(p["note_repo"])}</span>' if p.get("note_repo") else ""
    caveats = sum(1 for e in p.get("evidence", []) if e.startswith("!"))
    cv = (f'<span class="cv">{caveats} caveat{"s" if caveats != 1 else ""}</span>'
          if caveats else "")
    links = ""
    if p.get("links"):
        links = ('<div class="plinks">'
                 + "".join(f'<a href="{u}">{inline(t)}</a>' for t, u in p["links"])
                 + "</div>")
    return (f'<li class="lrow" data-r>'
            f'<div class="lno">{i:02d}{cv}</div>'
            f'<div class="lmain">'
            f'<h3>{name}{priv}</h3>'
            f'<p>{inline(p["what"])}</p>'
            f'<p class="st"><span class="k">Status</span> {inline(p["status"])}</p>'
            f'{_evidence(p)}{links}'
            f'</div>'
            f'<div class="lper"><span class="vh">Period </span>{_period(p)}</div>'
            f'<div class="lcount">{_counts(p)}</div>'
            f'</li>')


# ---------------------------------------------------------------- plates
#
# The playable projects each get a full-bleed plate in the colour of its own
# subject. voidbreaker's values are the literal RGB out of voidbreaker/game/config.py;
# pixel-poker's are sampled from its own table screenshots.

VB_BODY = [
    "A twin-stick arcade roguelite in pygame-ce. Survive escalating waves, draft perks "
    "that compound, and break the Monolith every fifth wave.",
    "<strong>The game ships no art, no audio and no font files.</strong> Every sprite is drawn "
    "with <code>pygame.draw</code> and <code>gfxdraw</code>, every glow and nebula is synthesised "
    "through <code>numpy</code> into a Surface, the soundtrack and effects bank is DSP written from "
    "scratch and handed to <code>pygame.mixer</code> as raw sample buffers, and the type is set in "
    "whatever monospace face the machine already has. The screenshots below are the only images in "
    "the repository, and the game never loads them.",
    "It runs in a browser as the same Python compiled to WebAssembly with pygbag. Browsers "
    "have no hardware SDL renderer, so the web build starts with bloom and scanlines off; the "
    "desktop build is the faster one.",
]

PLATES = {
    "voidbreaker": {
        "cls": "vb", "title": "VOIDBREAKER",
        "body": lambda p: VB_BODY,
        "evidence": False,          # its evidence is the stats strip; none of it is a caveat
        "size": (900, 507),
        "shots": [
            ("combat.webp", "Wave combat. Enemies, bullets, glow and trails are all drawn "
                            "per frame with pygame.draw and gfxdraw."),
            ("boss-monolith.webp", "The Monolith, the wave-five boss. Nebulae are synthesised "
                                   "through numpy into Surfaces."),
            ("launch.webp", "The launch screen. No font files either — the type is set in a "
                            "monospace face the machine already has."),
        ],
        "stats": [("0", "asset files"), ("9,335", "lines of game"),
                  ("3,295", "lines of tests"), ("255", "test functions")],
        "cta": "Play it in your browser",
    },
    "pixel-poker": {
        "cls": "pk", "title": "PIXEL HOLD'EM",
        # The project text opens with the game's name; here that name is the heading.
        "body": lambda p: [inline(re.sub(r"^PIXEL HOLD'EM\.\s*", "", p["what"]))],
        "evidence": True,
        "size": (960, 600),
        "shots": [
            ("poker-table.webp", "A hand in progress. The coach panel on the right reads the "
                                 "hand and says why it would fold."),
            ("poker-setup.webp", "Table setup: opponents, stacks, blinds, and a skill rating "
                                 "for each bot."),
        ],
        "stats": [("12,571", "lines of JavaScript"), ("231", "automated tests"),
                  ("13", "of them cheating attempts"), ("8", "tutorial lessons")],
        "cta": "Play it",
    },
}


def _stat(value, label, led):
    ghost = f' data-ghost="{re.sub(r"[0-9]", "8", value)}"' if led else ""
    return f'<div><b class="count"{ghost}>{value}</b><span>{label}</span></div>'


def plate(i, n, p, owner):
    cfg = PLATES[p["name"]]
    w, h = cfg["size"]
    figs = "".join(
        f'<figure><img src="assets/img/{f}" alt="{html.escape(c)}" loading="lazy" '
        f'decoding="async" width="{w}" height="{h}"><figcaption>{c}</figcaption></figure>'
        for f, c in cfg["shots"])
    body = "".join(f"<p>{x}</p>" for x in cfg["body"](p))
    play = next((u for t, u in p.get("links", []) if t.lower().startswith("play")), None)
    extra = [(t, u) for t, u in p.get("links", []) if u != play]
    if p.get("repo"):
        extra.append(("Source", f"https://github.com/{owner}/{p['repo']}"))
    extra_html = "".join(f'<a href="{u}">{inline(t)}</a>' for t, u in extra)
    counts = (f'<div><dt>Commits</dt><dd class="lcount">{_counts(p)}</dd></div>'
              if _has_counts(p) else "")
    stats = "".join(_stat(v, l, cfg["cls"] == "pk") for v, l in cfg["stats"])
    hid = f'plate-{cfg["cls"]}'
    return f'''<section class="plate plate-{cfg['cls']}" id="{p['name']}" aria-labelledby="{hid}">
<div class="wrap plate-grid">
  <div class="plate-text" data-r>
    <p class="plate-no"><span>Plate {i:02d} / {n:02d}</span><span>{_period(p)}</span></p>
    <h3 id="{hid}">{cfg['title']}</h3>
    {body}
    <dl class="facts">
      <div><dt>Status</dt><dd>{inline(p['status'])}</dd></div>
      {counts}
    </dl>
    {_evidence(p) if cfg['evidence'] else ''}
  </div>
  <div class="shots" data-r data-stagger>{figs}</div>
  <div class="plate-foot" data-r>
    <div class="stats" data-stagger>{stats}</div>
    <div class="ctas">
      <a class="play" href="{play}">{cfg['cta']} <span aria-hidden="true">&#8594;</span></a>
      <div class="plinks">{extra_html}</div>
    </div>
  </div>
</div>
</section>'''


# ---------------------------------------------------------------- page

def hero(site, contents, built):
    words = "".join(f'<span class="w"><span style="--i:{k}">{html.escape(w)}</span></span>'
                    for k, w in enumerate(site["name"].split()))
    tagline = html.escape(site["tagline"]).replace("corrections", "<em>corrections</em>", 1)
    rows = "".join(
        f'<li><a href="#{anchor}"><span class="ix">{k:02d}</span><span class="t">{label}</span>'
        f'<span class="dots" aria-hidden="true"></span><span class="c">{count}</span></a></li>'
        for k, (anchor, label, count) in enumerate(contents, 1))
    return f'''<section class="hero" id="top">
<div class="wrap">
  <p class="kicker"><b>{site['handle']}</b><span>{tagline}</span></p>
  <h1 class="name" aria-label="{html.escape(site['name'])}">{words}</h1>
  <div class="hero-grid">
    <p class="lede">{inline(site['lede'])}</p>
    <nav class="contents" aria-label="Contents">
      <p class="ch">Contents</p>
      <ol>{rows}</ol>
      <p class="built">Built {built}. Commit counts read from the GitHub API.</p>
    </nav>
  </div>
</div>
</section>'''


def section_head(no, anchor, title):
    return (f'<h2 class="sec" id="{anchor}" data-r><span class="no">{no:02d}</span>'
            f'<span>{title}</span></h2>')


def page(site, projects, findings, errata, owner):
    featured = [p for p in projects if p["name"] in PLATES]
    rest = [p for p in projects if p["name"] not in PLATES]
    built = datetime.date.today().isoformat()
    contents = [("play", "Playable", f"{len(featured):02d}"),
                ("projects", "Everything else", f"{len(rest):02d}"),
                ("findings", "Findings", f"{len(findings):02d}"),
                ("errata", "Errata", f"{len(errata):02d}")]
    plates = "\n".join(plate(k, len(featured), p, owner) for k, p in enumerate(featured, 1))
    rows = "\n".join(ledger_row(k, p, owner) for k, p in enumerate(rest, 1))
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site['name']}</title>
<meta name="description" content="Projects, findings, and corrections to them. Every project is listed with the number of commits that are mine against the number in the repository.">
<meta name="color-scheme" content="light dark">
<script>(function(r){{r.classList.add("js");try{{var t=localStorage.getItem("theme");if(t==="light"||t==="dark")r.setAttribute("data-theme",t)}}catch(e){{}}setTimeout(function(){{if(!window.__motion)r.classList.remove("js")}},3000)}})(document.documentElement)</script>
<link rel="preload" href="assets/fonts/IBMPlexSerif-600.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="assets/fonts/IBMPlexSerif-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="assets/fonts/IBMPlexMono-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 16 16%27%3E%3Crect width=%2716%27 height=%2716%27 fill=%27%23A8321E%27/%3E%3C/svg%3E">
<link rel="stylesheet" href="styles.css">
<script src="motion.js" defer></script>
<meta property="og:title" content="{site['name']}">
<meta property="og:description" content="Projects, findings, and corrections to them.">
<meta property="og:type" content="website">
</head>
<body>
<a class="skip" href="#projects">Skip to projects</a>
<header class="top">
<div class="wrap">
  <a class="brand" href="#top">{site['handle']}</a>
  <nav aria-label="Sections">
    <a href="#play">Play</a><a href="#projects">Projects</a><a href="#findings">Findings</a><a class="nav-errata" href="#errata">Errata</a>
    <button class="theme" type="button" hidden><span class="disc" aria-hidden="true"></span></button>
  </nav>
</div>
</header>
<main>
{hero(site, contents, built)}

<section class="block block-play" aria-labelledby="play">
<div class="wrap">{section_head(1, "play", "The two you can actually play")}</div>
{plates}
</section>

<section class="block" aria-labelledby="projects">
<div class="wrap">
{section_head(2, "projects", "Everything else")}
<div class="lhead" aria-hidden="true"><span>No.</span><span>Project</span><span>Period</span><span>Commits mine / total</span></div>
<ol class="ledger">
{rows}
</ol>
<p class="note">{inline(site['forks_note'])}</p>
</div>
</section>

<section class="block" aria-labelledby="findings">
<div class="wrap">
{section_head(3, "findings", "Findings")}
<div class="nb" data-line>
{"".join(entry_html(e, site) for e in findings)}
</div>
</div>
</section>

<section class="block" aria-labelledby="errata">
<div class="wrap">
{section_head(4, "errata", "Errata")}
<div class="nb" data-line>
{"".join(entry_html(e, site) for e in errata)}
</div>
</div>
</section>
</main>

<footer class="colophon">
<div class="wrap">
<p>Every entry: claim &#8594; method &#8594; evidence &#8594; verdict, in that order.<br>
Commit counts for public repositories are read from the GitHub API when this page is built.<br>
Counts for private repositories are read the same way, through my own token, so you cannot check them.<br>
Nothing is deleted. Errors are struck, dated, and left legible.</p>
<p>Set in IBM Plex Serif and IBM Plex Mono, self-hosted. One small script for motion and the theme switch; with it off, the page reads the same.<br>
<a href="{site['github']}">GitHub</a> &#183; <a href="mailto:{site['email']}">{site['email']}</a> &#183; Built {built}.</p>
</div>
</footer>
</body>
</html>
'''


def report_size():
    size = lambda *a: os.path.getsize(P(*a))
    html_kb, css, js = size("index.html"), size("styles.css"), size("motion.js")
    fonts = sum(size("assets", "fonts", f)
                for f in os.listdir(P("assets", "fonts")) if f.endswith(".woff2"))
    imgdir = P("assets", "img")
    imgs = (sum(os.path.getsize(os.path.join(imgdir, f)) for f in os.listdir(imgdir))
            if os.path.isdir(imgdir) else 0)
    first = html_kb + css + js + fonts      # images are lazy
    total = first + imgs
    BUDGET = 250 * 1024                     # first load, images excluded; see README
    print(f"\n  index.html   {html_kb/1024:7.1f} KB")
    print(f"  styles.css   {css/1024:7.1f} KB")
    print(f"  motion.js    {js/1024:7.1f} KB")
    print(f"  fonts        {fonts/1024:7.1f} KB")
    print(f"  ---------------------")
    print(f"  first load   {first/1024:7.1f} KB   budget {BUDGET/1024:.0f} KB   "
          f"{'OK' if first < BUDGET else 'OVER BUDGET'}")
    print(f"  images       {imgs/1024:7.1f} KB   (lazy)")
    print(f"  TOTAL        {total/1024:7.1f} KB")


def main():
    site = json.load(open(P("content", "site.json")))
    projects = json.load(open(P("content", "projects.json")))
    owner = site["github"].rstrip("/").split("/")[-1]

    print("Reading commit counts from the GitHub API (never typed by hand):")
    projects = resolve_counts(projects, owner)

    entries = [parse_entry(P("content", "findings", f))
               for f in sorted(os.listdir(P("content", "findings"))) if f.endswith(".md")]
    findings = [e for e in entries if e.get("kind") != "erratum"]
    errata = [e for e in entries if e.get("kind") == "erratum"]

    doc = page(site, projects, findings, errata, owner)
    open(P("index.html"), "w", encoding="utf-8").write(doc)
    report_size()


if __name__ == "__main__":
    main()
