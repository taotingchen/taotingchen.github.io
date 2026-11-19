#!/usr/bin/env python3
"""Builds index.html (English) and zh/index.html (Traditional Chinese) from content.json.

Usage:
    python3 build.py            # publishable build: placeholders and empty sections are left out
    python3 build.py --drafts   # also show items marked "todo": true, with a striped background

Standard library only.
"""
import hashlib
import html
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
C = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
DRAFTS = "--drafts" in sys.argv
LANGS = {"en": {"dir": "", "html_lang": "en", "other": "zh", "other_label": "中文"},
         "zh": {"dir": "zh", "html_lang": "zh-Hant", "other": "en", "other_label": "EN"}}


def asset_version():
    """Short content hash appended to asset URLs so browsers pick up new CSS/JS."""
    h = hashlib.sha1()
    for name in ("style.css", "main.js"):
        h.update((ROOT / "assets" / name).read_bytes())
    return h.hexdigest()[:8]


VERSION = asset_version()


def live(items):
    """Items to render: everything in a drafts build, otherwise only finished ones."""
    return [x for x in items if DRAFTS or not x.get("todo")]


def real(url):
    return bool(url) and url != "#"


def render(lang):
    L = LANGS[lang]
    base = "../" if L["dir"] else ""
    site = C["site"].get("url", "").rstrip("/")

    def t(v):
        if isinstance(v, dict):
            v = v.get(lang, v.get("en", ""))
        return html.escape(str(v))

    def todo(item):
        return " is-todo" if item.get("todo") else ""

    def linked(text, url):
        """Wrap text in a link only when there is somewhere real to go."""
        if not real(url):
            return text
        target = ' target="_blank" rel="noopener"' if url.startswith("http") else ""
        return f'<a href="{html.escape(url, quote=True)}"{target}>{text}</a>'

    def tags(items):
        return " · ".join(t(s) for s in items)

    def section(sid, heading, body):
        if not body.strip():
            return ""
        return f"""
  <section id="{sid}" class="section">
    <h2>{t(heading)}</h2>{body}
  </section>
"""

    def listing(rows):
        return f"""
    <ul class="list">{rows}
    </ul>""" if rows else ""

    ui, hero, work, res, about, contact = (C[k] for k in ("ui", "hero", "work", "research", "about", "contact"))
    f = work["featured"]
    name = t(C["site"]["name"])

    # Bars are scaled on a log axis so the 691 ms baseline does not flatten the rest.
    top = math.log(max(s["ms"] for s in f["steps"]))
    floor = math.log(20)
    bars = ""
    for i, s in enumerate(f["steps"]):
        pct = max(6, (math.log(s["ms"]) - floor) / (top - floor) * 100)
        last = " is-final" if i == len(f["steps"]) - 1 else ""
        bars += (f'<li class="bar{last}"><span class="bar-label">{t(s["label"])}</span>'
                 f'<span class="bar-track"><span class="bar-fill" style="--w:{pct:.1f}%"></span></span>'
                 f'<span class="bar-value">{s["ms"]:g} ms</span></li>')
    more = f'\n      <p>{linked(t(f["link_label"]) + " →", f["link"]).replace("<a ", "<a class=more ", 1)}</p>' if real(f.get("link")) else ""
    featured = "" if f.get("todo") and not DRAFTS else f"""
    <article class="featured{todo(f)}">
      <h3>{linked(t(f["title"]), f.get("link"))}</h3>
      <p>{t(f["body"])}</p>
      <figure class="chart">
        <figcaption>{t(f["chart_title"])}</figcaption>
        <ol class="bars">{bars}</ol>
      </figure>
      <p class="meta">{t(f["note"])}</p>{more}
    </article>"""

    projects = "".join(f"""
      <li class="item{todo(c)}">
        <h3>{linked(t(c["title"]), c.get("link"))}</h3>
        <p>{t(c["body"])}</p>
        <p class="meta">{tags(c["stack"] + ([c["year"]] if c.get("year") else []))}</p>
      </li>""" for c in live(C["side"]["items"]))

    pubs = "".join(f"""
      <li class="item{todo(p)}">
        <h3>{linked(t(p["title"]), p.get("link"))}</h3>
        <p>{t(p["authors"])}</p>
        <p class="meta">{t(p["venue"])} · {t(p["status"])} · {t(p["year"])}</p>
      </li>""" for p in live(res["items"]))

    awards = "".join(f"""
      <li class="item{todo(a)}">
        <h3>{linked(t(a["title"]), a.get("link"))}</h3>
        <p><strong>{t(a["result"])}</strong></p>
        <p>{t(a["detail"])}</p>
        <p class="meta">{t(a["year"])}</p>
      </li>""" for a in live(C["awards"]["items"]))

    def rows(items):
        return "".join(f"""
      <li class="item{todo(e)}">
        <h3>{t(e["what"])}</h3>
        <p>{t(e["detail"])}</p>
        <p class="meta">{t(e["when"])}</p>
      </li>""" for e in live(items))

    experience, education = rows(C["experience"]["items"]), rows(C["education"]["items"])

    links = "".join(
        f'<li><a class="{todo(l).strip()}" href="{html.escape(l["url"], quote=True)}" target="_blank" rel="noopener">{t(l["label"])}</a></li>'
        for l in live(contact["links"]) if real(l["url"]))
    email = contact.get("email", "")
    email_html = f'\n    <p><a class="email" href="mailto:{t(email)}">{t(email)}</a></p>' if email and "example.com" not in email else ""
    bio = "".join(f"<p>{t(p)}</p>" for p in about["bio"])
    cv = f'\n        <a href="{base}assets/cv.pdf">{t(hero["cta_cv"])}</a>' if (ROOT / "assets/cv.pdf").exists() else ""
    og = f'\n<meta property="og:image" content="{site}/assets/og.png">\n<meta name="twitter:card" content="summary_large_image">' if (ROOT / "assets/og.png").exists() else ""
    work_btn = f'\n        <a class="btn" href="#work">{t(hero["cta_work"])}</a>' if featured else ""
    actions = f'      <p class="actions">{work_btn}{cv}\n      </p>' if work_btn or cv else ""
    canonical = f'{site}/{L["dir"] + "/" if L["dir"] else ""}'

    nav = [("work", ui["nav_work"], featured), ("projects", ui["nav_side"], projects),
           ("research", ui["nav_research"], pubs), ("contact", ui["nav_contact"], True)]
    nav_html = "".join(f'\n    <a href="#{sid}">{t(label)}</a>' for sid, label, shown in nav if shown)

    body = (
        section("about", about["heading"], f"""
    <div class="bio">{bio}</div>
    <p class="meta">{tags(about["skills"])}</p>""")
        + section("work", work["heading"], featured)
        + section("projects", C["side"]["heading"], listing(projects))
        + section("research", res["heading"], listing(pubs))
        + section("awards", C["awards"]["heading"], listing(awards))
        + section("experience", C["experience"]["heading"], listing(experience))
        + section("education", C["education"]["heading"], listing(education))
        + section("contact", contact["heading"], f"""
    <p>{t(contact["body"])}</p>{email_html}
    <ul class="links">{links}</ul>"""))

    return f"""<!doctype html>
<html lang="{L["html_lang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#cdeef3">
<title>{t(C["site"]["title"])}</title>
<meta name="description" content="{t(C["site"]["description"])}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="en" href="{site}/">
<link rel="alternate" hreflang="zh-Hant" href="{site}/zh/">
<meta property="og:type" content="website">
<meta property="og:title" content="{t(C["site"]["title"])}">
<meta property="og:description" content="{t(C["site"]["description"])}">
<meta property="og:url" content="{canonical}">{og}
<link rel="icon" href="{base}assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}assets/style.css?v={VERSION}">
</head>
<body>
<a class="skip" href="#main">{t(ui["skip"])}</a>

<header class="nav">
  <a class="brand" href="{base or "./"}">{name}</a>
  <nav aria-label="Primary">{nav_html}
    <a class="lang" href="{base + "zh/" if lang == "en" else "../"}" hreflang="{LANGS[L["other"]]["html_lang"]}">{L["other_label"]}</a>
  </nav>
</header>

<main id="main">
  <section class="hero">
    <canvas id="water" aria-hidden="true"></canvas>
    <div class="hero-copy">
      <h1>{name}</h1>
      <p class="lede">{t(hero["lede"])}</p>
{actions}
    </div>
  </section>
{body}</main>

<footer class="footer">© <span id="year">2026</span> {name}</footer>
<script src="{base}assets/main.js?v={VERSION}" defer></script>
</body>
</html>
"""


def find_todos(node, path=""):
    out = []
    if isinstance(node, dict):
        if node.get("todo"):
            label = node.get("title") or node.get("what") or node.get("label") or node.get("name") or path
            out.append(label.get("en") if isinstance(label, dict) else label)
        for k, v in node.items():
            out += find_todos(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += find_todos(v, f"{path}[{i}]")
    return out


if __name__ == "__main__":
    for lang, L in LANGS.items():
        out = ROOT / L["dir"] / "index.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(render(lang), encoding="utf-8")
        print("wrote", out.relative_to(ROOT))
    todos = find_todos(C)
    if todos:
        print(f"\n{len(todos)} placeholders in content.json ({'shown' if DRAFTS else 'left out of this build'}):")
        for x in todos:
            print("  -", x)
