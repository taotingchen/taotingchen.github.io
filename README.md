# Personal site

Source for https://taotingchen.github.io: static, bilingual (English at `/`, Traditional Chinese at `/zh/`), no dependencies.

## Edit

All text lives in `content.json`. Every field has an `en` and a `zh` value. Items marked `"todo": true` are placeholders and are left out of the published pages, along with any section that has no finished items. Remove the flag once an item is real.

```bash
python3 build.py             # publishable build
python3 build.py --drafts    # also show placeholders, with a striped background
python3 -m http.server 8931  # preview at http://localhost:8931
```

To add a side project, put a new object at the top of `side.items`.

These appear automatically once the file exists or the value is real:

- `assets/cv.pdf`: adds a "Download CV" link to the hero
- `assets/og.png`: 1200×630 preview image for link shares
- `contact.email`: shown once it is no longer the example address

## Deploy

GitHub Pages serves the branch root. `index.html` and `zh/index.html` are committed, so run `python3 build.py` before committing; `.nojekyll` turns off Jekyll processing.

## Files

- `content.json`: all copy
- `build.py`: generates the two pages
- `assets/style.css`, `assets/main.js`: styles and the water animation in the hero
