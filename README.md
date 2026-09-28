# Yitian's AIDD Blog

English notes on AI-driven protein and binder design, translated from the Chinese WeChat posts published under **AIDD小白随想录**.

Live site: <https://yitian12321.github.io/yitian-aidd-blog/>

## What is in here

```
content/posts/*.md      one Markdown file per post (front matter + body)
content/pages/about.md  the About page
images/<slug>/          figures for each post, referenced as images/<slug>/<file>.png
theme/static/           css and js copied into the build
build.py                the whole site generator (standard library only)
docs/                   generated output, served by GitHub Pages
```

## Writing a post

Create `content/posts/<slug>.md`:

```markdown
---
title: The English title
date: 2025-09-05
tags: binder-design, paper-notes
summary: One or two sentences shown in the post list and the RSS feed.
source_url: https://mp.weixin.qq.com/s/xxxxxxxx
source_title: 中文原标题
---

Body. Markdown subset supported: ## / ### headings, paragraphs, **bold**,
*italic*, `code`, [links](https://example.com), - and 1. lists, > quotes,
```code fences```, pipe tables, --- rules, and standalone images:

![caption text](images/<slug>/figure.png)
```

A standalone image line becomes a `<figure>` with the alt text as the caption.
Relative image paths are rewritten per page automatically, so always write them
as `images/<slug>/<file>.png` regardless of where the post lives.

## Building

```bash
python build.py            # writes docs/
python build.py --serve    # writes docs/ and serves it on http://127.0.0.1:8080
```

No dependencies beyond Python 3.9+. The generator produces the index, post pages
with a table of contents, tag pages, an About page, `feed.xml`, `sitemap.xml`,
a 404 page and `.nojekyll`.

## Deployment

GitHub Pages serves `docs/` from the `main` branch, so publishing is:

```bash
python build.py
git add -A && git commit -m "publish: <what changed>"
git push
```

GitHub Pages build type is set to "deploy from a branch" (main, `/docs`), which
needs no Actions workflow and no extra token scopes.

## Translation notes

Posts are translated from the Chinese originals, keeping the author's voice,
section structure and figures. Technical terms stay in English as used in the
literature; Chinese institution names are glossed on first use. Each post links
back to the WeChat original, which remains the authoritative version if wording
differs. Chinese asides that were set as italic quotes on WeChat become
blockquotes here.

## Template

Site shell, layout and generator by the author, styled after academic ML blogs
(a fixed sidebar with profile and recent posts, a single reading column, light
and dark themes).

## License

Text and figures are the author's own. Please cite the original WeChat post when
quoting. Code in this repository is MIT.
