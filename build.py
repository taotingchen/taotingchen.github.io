#!/usr/bin/env python3
"""Builds the whole site from content.json and the Markdown files in pages/ and posts/.

Usage:
    python3 build.py            # publishable build: placeholders, drafts and empty sections are left out
    python3 build.py --drafts   # also show items marked "todo": true and posts marked "draft: true"

Output: index.html, projects/<slug>/, blog/, blog/<slug>/, the same under zh/, and
assets/search-<lang>.json. Standard library only.
"""
import hashlib
import html
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
C = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
DRAFTS = "--drafts" in sys.argv
LANGS = {"en": {"dir": "", "html_lang": "en", "other": "zh", "other_label": "中文"},
         "zh": {"dir": "zh/", "html_lang": "zh-Hant", "other": "en", "other_label": "EN"}}
SITE = C["site"].get("url", "").rstrip("/")
SHOWN = 4  # projects visible before "Show more"


def asset_version():
    """Short content hash appended to asset URLs so browsers pick up new CSS/JS."""
    h = hashlib.sha1()
    for name in ("style.css", "main.js"):
        h.update((ROOT / "assets" / name).read_bytes())
    return h.hexdigest()[:8]


VERSION = asset_version()

# ---------- GitHub repo cards for Picks ----------
# Repo facts (stars, language, licence) are fetched once and kept in picks-cache.json,
# so ordinary builds work offline. `python3 build.py --refresh` fetches them again.
CACHE = ROOT / "picks-cache.json"


def repo_info(repo):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if repo not in cache or "--refresh" in sys.argv:
        import urllib.request
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}",
                                         headers={"User-Agent": "static-site-build", "Accept": "application/vnd.github+json"})
            d = json.load(urllib.request.urlopen(req, timeout=10))
            cache[repo] = {"description": d.get("description") or "", "stars": d.get("stargazers_count", 0),
                           "language": d.get("language") or "", "license": (d.get("license") or {}).get("spdx_id") or ""}
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception as e:  # offline: build the card without numbers
            print(f"could not fetch {repo}: {e}")
    return cache.get(repo, {})


def stars(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def live(items):
    """Items to render: everything in a drafts build, otherwise only finished ones."""
    return [x for x in items if DRAFTS or not x.get("todo")]


def real(url):
    return bool(url) and url != "#"


def tr(v, lang):
    if isinstance(v, dict):
        v = v.get(lang, v.get("en", ""))
    return html.escape(str(v))


# ---------- Markdown (the small subset the pages use) ----------

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: f'<a href="{m.group(2)}"' + (' target="_blank" rel="noopener"' if m.group(2).startswith("http") else "") + f">{m.group(1)}</a>", s)
    return s


def markdown(text, inserts=None):
    """Headings (##, ###), paragraphs, - and 1. lists, pipe tables, ``` code, and {{name}} inserts."""
    out, lines, i = [], text.strip("\n").split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
        elif ln.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1
        elif re.fullmatch(r"\{\{(\w+)\}\}", ln.strip()):
            out.append((inserts or {}).get(ln.strip()[2:-2], ""))
            i += 1
        elif ln.startswith("#"):
            level = min(max(len(ln) - len(ln.lstrip("#")), 2), 3)
            out.append(f"<h{level}>{inline(ln.lstrip('#').strip())}</h{level}>")
            i += 1
        elif ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(f'<div class="table"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>')
        elif re.match(r"\s*(-|\d+\.)\s+", ln):
            tag = "ol" if re.match(r"\s*\d+\.", ln) else "ul"
            items = []
            while i < len(lines) and re.match(r"\s*(-|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*(-|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"(#|```|\s*\||\s*(-|\d+\.)\s+|\{\{)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


def read_md(path):
    """Returns (front matter dict, body). Front matter is 'key: value' lines between --- markers."""
    text = path.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---"):
        head, _, text = text[3:].partition("\n---")
        for ln in head.strip().split("\n"):
            k, _, v = ln.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text


def localized(folder, stem, lang):
    """pages/x.zh.md if it exists, otherwise pages/x.en.md, otherwise None."""
    for l in (lang, "en"):
        p = ROOT / folder / f"{stem}.{l}.md"
        if p.exists():
            return p
    return None


def posts(lang):
    """Published posts, newest first. File name: posts/YYYY-MM-DD-slug.<lang>.md"""
    out = []
    for p in sorted((ROOT / "posts").glob("*.en.md"), reverse=True):
        stem = p.name[:-len(".en.md")]
        meta, body = read_md(localized("posts", stem, lang))
        if meta.get("draft", "").lower() == "true" and not DRAFTS:
            continue
        out.append({"slug": stem[11:], "date": stem[:10], "title": meta.get("title", stem), "summary": meta.get("summary", ""),
                    "tags": [x.strip() for x in meta.get("tags", "").split(",") if x.strip()], "body": body,
                    "draft": meta.get("draft", "").lower() == "true"})
    return out


# ---------- Shared page shell ----------

def shell(lang, depth, path, title, desc, main, has):
    """depth: how many folders below the site root this page sits. path: its address inside the language root."""
    L, ui = LANGS[lang], C["ui"]
    t = lambda v: tr(v, lang)
    root = "../" * depth
    home = (root + L["dir"]) or "./"
    name = t(C["site"]["name"])
    here = "" if not path else None  # on the home page, section links stay on the page
    sec = (lambda sid: f"#{sid}") if here == "" else (lambda sid: f"{home}#{sid}")
    nav = [(sec("work"), ui["nav_work"], has["work"]), (sec("research"), ui["nav_research"], has["research"]),
           (f"{home}picks/", ui["nav_picks"], has.get("picks")), (f"{home}blog/", ui["nav_blog"], has["blog"]), (sec("contact"), ui["nav_contact"], True)]
    nav_html = "".join(f'\n    <a href="{href}">{t(label)}</a>' for href, label, shown in nav if shown)
    other = root + LANGS[L["other"]]["dir"] + path
    og = f'\n<meta property="og:image" content="{SITE}/assets/og.png">\n<meta name="twitter:card" content="summary_large_image">' if (ROOT / "assets/og.png").exists() else ""
    return f"""<!doctype html>
<html lang="{L["html_lang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#cdeef3">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{SITE}/{L["dir"]}{path}">
<link rel="alternate" hreflang="en" href="{SITE}/{path}">
<link rel="alternate" hreflang="zh-Hant" href="{SITE}/zh/{path}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{SITE}/{L["dir"]}{path}">{og}
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="preload" href="{root}assets/fonts/newsreader.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{root}assets/fonts/figtree.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{root}assets/style.css?v={VERSION}">
</head>
<body data-search="{root}assets/search-{lang}.json?v={VERSION}" data-root="{root}">
<a class="skip" href="#main">{t(ui["skip"])}</a>

<header class="nav">
  <a class="brand" href="{home}">{name}</a>
  <nav aria-label="Primary">{nav_html}
    <button class="search-btn" type="button" data-search-open aria-label="{t(ui["search"])}">{t(ui["search"])} <kbd>Ctrl K</kbd></button>
    <a class="lang" href="{other or "./"}" hreflang="{LANGS[L["other"]]["html_lang"]}">{L["other_label"]}</a>
  </nav>
</header>

<main id="main">
{main}</main>

<footer class="footer">© <span id="year">2026</span> {name}</footer>

<dialog class="search" aria-label="{t(ui["search"])}">
  <input type="search" placeholder="{t(ui["search_placeholder"])}" aria-label="{t(ui["search"])}" autocomplete="off">
  <ul class="results" data-empty="{t(ui["search_empty"])}"></ul>
</dialog>
<script src="{root}assets/main.js?v={VERSION}" defer></script>
</body>
</html>
"""


# ---------- Site ----------

def build(lang):
    L, ui = LANGS[lang], C["ui"]
    t = lambda v: tr(v, lang)
    hero, work, res, about, contact = (C[k] for k in ("hero", "work", "research", "about", "contact"))
    name = t(C["site"]["name"])
    pages, index = {}, []  # pages: path inside the language root -> html.  index: search entries
    abs_home = "/" + L["dir"]

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

    def listing(rows, attrs=""):
        return f"""
    <ul class="list"{attrs}>{rows}
    </ul>""" if rows else ""

    def chart(f):
        # Bars are scaled on a log axis so the large baseline does not flatten the rest.
        top, floor, bars = math.log(max(s["ms"] for s in f["steps"])), math.log(20), ""
        for i, s in enumerate(f["steps"]):
            pct = max(6, (math.log(s["ms"]) - floor) / (top - floor) * 100)
            last = " is-final" if i == len(f["steps"]) - 1 else ""
            bars += (f'<li class="bar{last}"><span class="bar-label">{t(s["label"])}</span>'
                     f'<span class="bar-track"><span class="bar-fill" style="--w:{pct:.1f}%"></span></span>'
                     f'<span class="bar-value">{s["ms"]:g} ms</span></li>')
        return f"""<figure class="chart">
        <figcaption>{t(f["chart_title"])}</figcaption>
        <ol class="bars">{bars}</ol>
      </figure>"""

    # ----- Projects: the featured one first, then the rest -----
    f = work["featured"]
    projects = live([dict(f, featured=True)] + C["side"]["items"])
    topics = []
    for p in projects:
        for tp in p.get("topics", []):
            if tp["en"] not in [x["en"] for x in topics]:
                topics.append(tp)

    def project_href(p, prefix):
        """A project's own page when it has one, otherwise its outside link."""
        if p.get("slug") and localized("pages/projects", p["slug"], lang):
            return f'{prefix}projects/{p["slug"]}/'
        return p.get("link")

    cards, rows = "", ""
    for i, p in enumerate(projects):
        href = project_href(p, "")
        data = f' data-topics="{html.escape("|".join(x["en"] for x in p.get("topics", [])))}"'
        extra = " extra" if i >= SHOWN else ""
        if p.get("featured"):
            more = f'\n      <p><a class="more" href="{href}">{t(p["link_label"])} →</a></p>' if real(href) else ""
            cards += f"""
    <article class="featured{todo(p)}"{data}>
      <h3>{linked(t(p["title"]), href)}</h3>
      <p>{t(p["body"])}</p>
      {chart(p)}
      <p class="meta">{t(p["note"])}</p>{more}
    </article>"""
        else:
            rows += f"""
      <li class="item{todo(p)}{extra}"{data}>
        <h3>{linked(t(p["title"]), href)}</h3>
        <p>{t(p["body"])}</p>
        <p class="meta">{tags(p["stack"] + ([p["year"]] if p.get("year") else []))}</p>
      </li>"""
        index.append({"t": tr(p["title"], lang), "d": tr(p["body"], lang), "k": tr(ui["nav_work"], lang),
                      "u": (abs_home + href) if href and not href.startswith("http") else (href if real(href) else abs_home + "#work")})
    chips = ""
    if len(projects) >= 3 and len(topics) >= 2:
        chips = f'\n    <div class="chips" role="group" aria-label="{t(ui["filter"])}">' + \
                f'<button type="button" class="chip" data-topic="" aria-pressed="true">{t(ui["all"])}</button>' + \
                "".join(f'<button type="button" class="chip" data-topic="{html.escape(x["en"])}" aria-pressed="false">{t(x)}</button>' for x in topics) + "</div>"
    hidden = max(0, len(projects) - SHOWN)
    more_btn = f'\n    <button type="button" class="more-btn" data-more>{t(ui["more"]).replace("{n}", str(hidden))}</button>' if hidden else ""
    work_html = (chips + cards + listing(rows) + more_btn) if projects else ""

    # ----- Project pages -----
    for p in projects:
        src = p.get("slug") and localized("pages/projects", p["slug"], lang)
        if not src:
            continue
        _, body = read_md(src)
        ext = f'\n      <p>{linked(t(p["link_label"]) + " →", p["link"]).replace("<a ", "<a class=more ", 1)}</p>' if real(p.get("link")) else ""
        main = f"""  <article class="page">
    <p class="back"><a href="../../#work">← {t(ui["nav_work"])}</a></p>
    <h1>{t(p["title"])}</h1>
    <p class="lede">{t(p["body"])}</p>
    <p class="meta">{tags(p["stack"])}</p>
    <div class="prose">
{markdown(body, {"chart": chart(p) if p.get("steps") else ""})}
    </div>{ext}
  </article>
"""
        pages[f'projects/{p["slug"]}/'] = (f'{t(p["title"])} · {name}', t(p["body"]), main)

    # ----- Blog -----
    plist = posts(lang)

    def post_row(p, prefix):
        draft = " is-todo" if p["draft"] else ""
        return f"""
      <li class="item{draft}">
        <h3><a href="{prefix}{p["slug"]}/">{html.escape(p["title"])}</a></h3>
        <p>{html.escape(p["summary"])}</p>
        <p class="meta">{" · ".join([p["date"]] + [html.escape(x) for x in p["tags"]])}</p>
      </li>"""

    blog_home = ""
    if plist:
        view_all = f'\n    <p class="view-all"><a class="more" href="blog/">{t(ui["view_all"])} →</a></p>' if len(plist) > 3 else ""
        blog_home = listing("".join(post_row(p, "blog/") for p in plist[:3])) + view_all
        pages["blog/"] = (f'{t(ui["nav_blog"])} · {name}', t(C["site"]["description"]), f"""  <article class="page">
    <p class="back"><a href="../">← {name}</a></p>
    <h1>{t(ui["nav_blog"])}</h1>{listing("".join(post_row(p, "") for p in plist))}
  </article>
""")
        for p in plist:
            pages[f'blog/{p["slug"]}/'] = (f'{html.escape(p["title"])} · {name}', html.escape(p["summary"]), f"""  <article class="page">
    <p class="back"><a href="../">← {t(ui["nav_blog"])}</a></p>
    <h1>{html.escape(p["title"])}</h1>
    <p class="meta">{" · ".join([p["date"]] + [html.escape(x) for x in p["tags"]])}</p>
    <div class="prose">
{markdown(p["body"])}
    </div>
  </article>
""")
            index.append({"t": p["title"], "d": p["summary"], "k": tr(ui["nav_blog"], lang), "u": f'{abs_home}blog/{p["slug"]}/'})

    # ----- Home page lists -----
    pubs = "".join(f"""
      <li class="item{todo(p)}">
        <h3>{linked(t(p["title"]), p.get("link"))}</h3>
        <p>{t(p["authors"])}</p>
        <p class="meta">{t(p["venue"])} · {t(p["status"])} · {t(p["year"])}</p>
      </li>""" for p in live(res["items"]))
    index += [{"t": tr(p["title"], lang), "d": tr(p["venue"], lang), "k": tr(ui["nav_research"], lang), "u": p["link"] if real(p.get("link")) else abs_home + "#research"} for p in live(res["items"])]

    awards = "".join(f"""
      <li class="item{todo(a)}">
        <h3>{linked(t(a["title"]), a.get("link"))}</h3>
        <p><strong>{t(a["result"])}</strong></p>
        <p>{t(a["detail"])}</p>
        <p class="meta">{t(a["year"])}</p>
      </li>""" for a in live(C["awards"]["items"]))
    index += [{"t": tr(a["title"], lang), "d": tr(a["result"], lang), "k": tr(C["awards"]["heading"], lang), "u": abs_home + "#awards"} for a in live(C["awards"]["items"])]

    pk = C.get("picks", {"items": []})
    cats = pk.get("categories", {})
    pick_items = sorted(live(pk["items"]), key=lambda x: x["added"], reverse=True)
    rootp = "../" * (1 + (1 if L["dir"] else 0))  # from picks/ back to the site root, for assets

    def src(x):  # the README in this page's language when the project has one, else the project page
        return t(x["readme"]) if x.get("readme") else html.escape(x["url"], quote=True)

    def repo_card(x):
        if not x.get("repo"):
            return f'<p class="meta"><a href="{html.escape(x["url"], quote=True)}" target="_blank" rel="noopener">{html.escape(x["url"])}</a></p>'
        info = repo_info(x["repo"])
        facts = [f for f in (f'★ {stars(info["stars"])}' if info.get("stars") else "", info.get("language", ""), info.get("license", "")) if f]
        return f"""<a class="repo" href="{src(x)}" target="_blank" rel="noopener">
          <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
          <span class="repo-name">{html.escape(x["repo"])}</span>
          <span class="repo-facts">{" · ".join(html.escape(f) for f in facts)}</span>
        </a>"""

    def pick_full(x, i):
        mine = [c for c in x.get("categories", []) if c in cats]
        imgs = "".join(f'<img src="{rootp}{html.escape(im["src"])}" alt="{t(im["alt"])}" loading="lazy" decoding="async">' for im in x.get("images", []))
        fig = f'\n        <figure class="shots">{imgs}<figcaption>{t(x.get("credit", pk["credit"]))}</figcaption></figure>' if imgs else ""
        how = "".join(f"<li>{t(h)}</li>" for h in x.get("how", []))
        how = f'\n        <h4>{t(pk["how_label"])}</h4>\n        <ol class="how">{how}</ol>' if how else ""
        c = x.get("cite")
        cite = ""
        if c:
            doi = f' <a href="https://doi.org/{html.escape(c["doi"])}" target="_blank" rel="noopener">doi:{html.escape(c["doi"])}</a>' if c.get("doi") else ""
            links = " · ".join(f'<a href="{html.escape(l["url"], quote=True)}" target="_blank" rel="noopener">{t(l["label"])}</a>' for l in c.get("links", []))
            cite = f'\n        <div class="cite"><h4>{t(pk["cite_label"])}</h4><p>{t(c["text"])}{doi}</p>' + (f'<p class="cite-links">{links}</p>' if links else "") + "</div>"
        note = f'\n        <p class="note"><strong>{t(pk["note_label"])}</strong>{t(x["note"])}</p>' if x.get("note") else ""
        extra = " extra" if i >= 12 else ""
        return f"""
      <li class="pick{todo(x)}{extra}" id="{x["slug"]}" data-topics="{"|".join(mine)}">{fig}
        <h3><a href="{src(x)}" target="_blank" rel="noopener">{t(x["name"])}</a> <span class="by">{t(pk["by"])} {html.escape(x["by"])}</span></h3>
        <p>{t(x["summary"])}</p>{note}{how}
        {repo_card(x)}{cite}
        <p class="meta">{" · ".join([t(cats[c]) for c in mine] + [t(pk["status"][x.get("state", "want")]), x["added"]])}</p>
      </li>"""

    def pick_tile(x):
        im = x.get("images", [])
        thumb = x.get("thumb") or (im[0]["src"] if im else "")
        img = f'<img src="{"../" if L["dir"] else ""}{html.escape(thumb)}" alt="" loading="lazy" decoding="async">' if im else '<span class="tile-blank"></span>'
        return f"""
      <li><a class="tile" href="picks/#{x["slug"]}">{img}<span class="tile-name">{t(x["name"])}</span><span class="tile-text">{t(x["summary"])}</span></a></li>"""

    picks_home = ""
    if pick_items:
        used = [c for c in cats if any(c in x.get("categories", []) for x in pick_items)]
        chips_p = ""
        if len(pick_items) >= 3 and len(used) >= 2:
            chips_p = f'\n    <div class="chips" role="group" aria-label="{t(ui["filter"])}">' + \
                      f'<button type="button" class="chip" data-topic="" aria-pressed="true">{t(ui["all"])}</button>' + \
                      "".join(f'<button type="button" class="chip" data-topic="{c}" aria-pressed="false">{t(cats[c])}</button>' for c in used) + "</div>"
        more_n = max(0, len(pick_items) - 12)
        more_p = f'\n    <button type="button" class="more-btn" data-more>{t(ui["more"]).replace("{n}", str(more_n))}</button>' if more_n else ""
        pages["picks/"] = (f'{t(pk["heading"])} · {name}', t(pk["intro"]), f"""  <section class="page">
    <p class="back"><a href="../">← {name}</a></p>
    <h1>{t(pk["heading"])}</h1>
    <p class="lede">{t(pk["intro"])}</p>{chips_p}
    <ul class="picks">{"".join(pick_full(x, i) for i, x in enumerate(pick_items))}
    </ul>{more_p}
  </section>
""")
        shown = pick_items[:pk.get("home_count", 3)]
        picks_home = (f'\n    <p class="intro">{t(pk["intro"])}</p>\n    <ul class="tiles">{"".join(pick_tile(x) for x in shown)}\n    </ul>'
                      f'\n    <p class="view-all"><a class="more" href="picks/">{t(pk["view_all"]).replace("{n}", str(len(pick_items)))} →</a></p>')
        index += [{"t": tr(x["name"], lang), "d": tr(x["summary"], lang), "k": tr(pk["heading"], lang), "u": f'{abs_home}picks/#{x["slug"]}'} for x in pick_items]

    def rows_of(items):
        return "".join(f"""
      <li class="item{todo(e)}">
        <h3>{t(e["what"])}</h3>
        <p>{t(e["detail"])}</p>
        <p class="meta">{t(e["when"])}</p>
      </li>""" for e in live(items))

    experience, education = rows_of(C["experience"]["items"]), rows_of(C["education"]["items"])
    for key, sid in (("experience", "experience"), ("education", "education")):
        index += [{"t": tr(e["what"], lang), "d": tr(e["detail"], lang), "k": tr(C[key]["heading"], lang), "u": abs_home + "#" + sid} for e in live(C[key]["items"])]
    index += [{"t": tr(about["heading"], lang), "d": tr(about["bio"][0], lang), "k": "", "u": abs_home + "#about"},
              {"t": tr(contact["heading"], lang), "d": tr(contact["body"], lang), "k": "", "u": abs_home + "#contact"}]

    links = "".join(
        f'<li><a class="{todo(l).strip()}" href="{html.escape(l["url"], quote=True)}" target="_blank" rel="noopener">{t(l["label"])}</a></li>'
        for l in live(contact["links"]) if real(l["url"]))
    email = contact.get("email", "")
    email_html = f'\n    <p><a class="email" href="mailto:{t(email)}">{t(email)}</a></p>' if email and "example.com" not in email else ""
    bio = "".join(f"<p>{t(p)}</p>" for p in about["bio"])
    if picks_home:  # the bio mentions Picks by name; link it
        bio = bio.replace(t(pk["heading"]), f'<a href="picks/">{t(pk["heading"])}</a>', 1)
    root = "../" if L["dir"] else ""
    cv = f'\n        <a href="{root}assets/cv.pdf">{t(hero["cta_cv"])}</a>' if (ROOT / "assets/cv.pdf").exists() else ""
    work_btn = f'\n        <a class="btn" href="#work">{t(hero["cta_work"])}</a>' if work_html else ""
    actions = f'      <p class="actions">{work_btn}{cv}\n      </p>' if work_btn or cv else ""

    home = f"""  <section class="hero">
    <canvas id="water" aria-hidden="true"></canvas>
    <div class="hero-copy">
      <h1>{name}</h1>
      <p class="lede">{t(hero["lede"])}</p>
{actions}
    </div>
  </section>
""" + (
        section("about", about["heading"], f"""
    <div class="bio">{bio}</div>
    <p class="meta">{tags(about["skills"])}</p>""")
        + section("work", work["heading"], work_html)
        + section("research", res["heading"], listing(pubs))
        + section("awards", C["awards"]["heading"], listing(awards))
        + section("blog", ui["nav_blog"], blog_home)
        + section("picks", pk["heading"], picks_home)
        + section("experience", C["experience"]["heading"], listing(experience))
        + section("education", C["education"]["heading"], listing(education))
        + section("contact", contact["heading"], f"""
    <p>{t(contact["body"])}</p>{email_html}
    <ul class="links">{links}</ul>"""))
    pages[""] = (t(C["site"]["title"]), t(C["site"]["description"]), home)

    has = {"work": bool(work_html), "research": bool(pubs), "blog": bool(plist), "picks": bool(picks_home)}
    base_depth = 1 if L["dir"] else 0
    for path, (title, desc, main) in pages.items():
        out = ROOT / L["dir"] / path / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(shell(lang, base_depth + path.count("/"), path, title, desc, main, has), encoding="utf-8")
        print("wrote", out.relative_to(ROOT))
    (ROOT / "assets" / f"search-{lang}.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


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
    for lang in LANGS:
        build(lang)
    todos = find_todos(C)
    if todos:
        print(f"\n{len(todos)} placeholders in content.json ({'shown' if DRAFTS else 'left out of this build'}):")
        for x in todos:
            print("  -", x)
