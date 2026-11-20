# Personal site

Source for https://taotingchen.github.io: static, bilingual (English at `/`, Traditional Chinese at `/zh/`), no dependencies.

## Edit

All text lives in `content.json`. Every field has an `en` and a `zh` value. Items marked `"todo": true` are placeholders and are left out of the published pages, along with any section that has no finished items. Remove the flag once an item is real.

```bash
python3 build.py             # publishable build
python3 build.py --drafts    # also show placeholders, with a striped background
python3 -m http.server 8931  # preview at http://localhost:8931
```

To add a project, put a new object at the top of `side.items`. Give it `topics` to place it under the filter chips on the home page.

To give a project its own page, add a `slug` to it and write `pages/projects/<slug>.en.md` (and `.zh.md`). A line containing only `{{chart}}` inserts the project's latency chart.

To write a blog post, add `posts/YYYY-MM-DD-slug.en.md` (and optionally `.zh.md`) starting with:

```
---
title: Post title
summary: One sentence shown in lists and search
tags: VLA, Inference
draft: true
---
```

Posts with `draft: true` only appear in a `--drafts` build. The Blog section and nav link appear once one post is published. Markdown support is a small subset: `##` headings, paragraphs, lists, pipe tables, fenced code, `inline code`, `**bold**` and links.

These appear automatically once the file exists or the value is real:

- `assets/cv.pdf`: adds a "Download CV" link to the hero
- `assets/og.png`: 1200×630 preview image for link shares
- `contact.email`: shown once it is no longer the example address

## Deploy

GitHub Pages serves the branch root. `index.html` and `zh/index.html` are committed, so run `python3 build.py` before committing; `.nojekyll` turns off Jekyll processing.

## Files

- `content.json`: all copy
- `build.py`: generates every page and the search index (`assets/search-*.json`)
- `pages/`, `posts/`: Markdown for project pages and blog posts
- `assets/style.css`, `assets/main.js`: styles and the water animation in the hero
