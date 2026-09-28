"""Static site generator for Yitian's AIDD Blog.

No external dependencies: standard library only. Content lives in content/posts/*.md
with a small YAML-ish front matter block; the generated site is written to docs/,
which GitHub Pages serves directly (branch main, folder /docs).

Usage:
    python build.py            # build into docs/
    python build.py --serve    # build, then serve docs/ at http://127.0.0.1:8080
"""

from __future__ import annotations

import html
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
POSTS = CONTENT / "posts"
PAGES = CONTENT / "pages"
THEME = ROOT / "theme"
DOCS = ROOT / "docs"

SITE = {
    "url": "https://yitian12321.github.io/yitian-aidd-blog",
    "title": "Yitian's AIDD Blog",
    "author": "Yitian Xiao",
    "tagline": "AI4Protein: generative protein and antibody design, structure prediction, and what the models still get wrong.",
    "blurb": "English versions of my Chinese notes on AI-driven protein and antibody design, with the figures carried over from WeChat.",
    "github": "https://github.com/Yitian12321",
    "wechat_account": "AIDD小白随想录",
}

TAG_LABELS = {
    "protein-design": "Protein design",
    "binder-design": "Binder design",
    "hallucination-design": "Hallucination design",
    "diffusion-models": "Diffusion models",
    "structure-prediction": "Structure prediction",
    "alphafold": "AlphaFold",
    "paper-notes": "Paper notes",
    "review": "Review",
    "antibody": "Antibody",
    "enzyme-design": "Enzyme design",
    "protein-language-models": "Protein language models",
    "esm": "ESM",
    "world-model": "World models",
}


# --------------------------------------------------------------------------- #
# front matter + markdown
# --------------------------------------------------------------------------- #

def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.lstrip().startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, parts[2].strip()


def pretty_date_short(value) -> str:
    return f"{value.strftime('%b')} {value.day}, {value.year}"


def pretty_date(value) -> str:
    """Portable month-day-year formatting: Windows strftime has no %-d."""
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    return text


def render_markdown(text: str, prefix: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Return (html, toc) where toc is a list of (level, anchor, title)."""
    lines = text.split("\n")
    out: list[str] = []
    toc: list[tuple[int, str, str]] = []
    used: dict[str, int] = {}
    i = 0

    def flush_paragraph(buffer: list[str]) -> None:
        if buffer:
            out.append(f"<p>{inline(' '.join(buffer))}</p>")
            buffer.clear()

    paragraph: list[str] = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph(paragraph)
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            code = html.escape("\n".join(block))
            out.append(f"<pre><code>{code}</code></pre>")
            continue

        if not stripped:
            flush_paragraph(paragraph)
            i += 1
            continue

        image_only = re.fullmatch(r"!\[([^\]]*)\]\(([^)\s]+)\)", stripped)
        if image_only:
            flush_paragraph(paragraph)
            alt, src = image_only.group(1), image_only.group(2)
            src = f"{prefix}{src}" if not src.startswith(("http", "/")) else src
            caption = f"<figcaption>{inline(alt)}</figcaption>" if alt else ""
            out.append(f'<figure><img src="{src}" alt="{html.escape(alt)}" loading="lazy">{caption}</figure>')
            i += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush_paragraph(paragraph)
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 1:
                i += 1
                continue
            anchor = slugify(title)
            if anchor in used:
                used[anchor] += 1
                anchor = f"{anchor}-{used[anchor]}"
            else:
                used[anchor] = 0
            out.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>')
            if level == 2:
                toc.append((level, anchor, title))
            i += 1
            continue

        if re.fullmatch(r"(-{3,}|\*{3,})", stripped):
            flush_paragraph(paragraph)
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith("> "):
            flush_paragraph(paragraph)
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            body = " ".join(q for q in quote if q)
            out.append(f"<blockquote><p>{inline(body)}</p></blockquote>")
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            flush_paragraph(paragraph)
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head_html = "".join(f"<th>{inline(c)}</th>" for c in header)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in rows
            )
            out.append(
                '<div class="table-scroll"><table><thead><tr>'
                f"{head_html}</tr></thead><tbody>{body_html}</tbody></table></div>"
            )
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if bullet or numbered:
            flush_paragraph(paragraph)
            ordered = bool(numbered)
            items: list[str] = []
            pattern = r"^\d+[.)]\s+(.*)$" if ordered else r"^[-*]\s+(.*)$"
            while i < len(lines):
                match = re.match(pattern, lines[i].strip())
                if not match:
                    break
                items.append(inline(match.group(1)))
                i += 1
            tag = "ol" if ordered else "ul"
            body = "".join(f"<li>{item}</li>" for item in items)
            out.append(f"<{tag}>{body}</{tag}>")
            continue

        paragraph.append(stripped)
        i += 1

    flush_paragraph(paragraph)
    return "\n".join(out), toc


# --------------------------------------------------------------------------- #
# templates
# --------------------------------------------------------------------------- #

BASE = """<!DOCTYPE html>
<html lang="en" data-theme="">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
<meta name="description" content="{{description}}">
<meta name="author" content="{{author}}">
<meta property="og:title" content="{{title}}">
<meta property="og:description" content="{{description}}">
<meta property="og:type" content="{{og_type}}">
<meta property="og:url" content="{{canonical}}">
<link rel="alternate" type="application/rss+xml" title="{{site_title}}" href="{{prefix}}feed.xml">
<link rel="icon" href="{{prefix}}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{{prefix}}assets/css/main.css">
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="profile">
    <a href="{{prefix}}index.html"><img class="avatar" src="{{prefix}}images/avatar.png" alt="{{author}}"></a>
    <div class="name">{{author}}</div>
    <p class="tagline">{{tagline}}</p>
  </div>
  <div class="social">
    <a href="{{github}}" title="GitHub" aria-label="GitHub">{{icon_github}}</a>
    <a href="{{prefix}}feed.xml" title="RSS" aria-label="RSS feed">{{icon_rss}}</a>
  </div>
  <nav>
    <a href="{{prefix}}index.html"{{nav_home}}>Posts</a>
    <a href="{{prefix}}tags.html"{{nav_tags}}>Tags</a>
    <a href="{{prefix}}about.html"{{nav_about}}>About</a>
  </nav>
  <div class="recent">
    <h2>Recent posts</h2>
    <ul>
{{recent}}
    </ul>
  </div>
  <div class="sidebar-foot">
    Chinese originals on WeChat<br><em>{{wechat_account}}</em>
    <button class="theme-toggle" id="theme-toggle" type="button">Toggle theme</button>
  </div>
</aside>
<main class="main">
  <div class="wrap">
{{content}}
  </div>
</main>
</div>
<script src="{{prefix}}assets/js/main.js"></script>
</body>
</html>
"""

INDEX = """<div class="page-head">
  <h1>{{site_title}}</h1>
  <p class="lede">{{blurb}}</p>
</div>
<div class="post-list">
{{items}}
</div>
"""

POST = """<article class="post">
  <h1 class="post-title">{{title}}</h1>
  <div class="post-meta">
    <time datetime="{{iso}}">{{date_display}}</time>
    <span class="dot">·</span><span>{{reading_time}} min read</span>
{{tags}}
  </div>
<div class="toc">
  <h2>Contents</h2>
  <ol>
{{toc}}
  </ol>
</div>
  <div class="post-body">
{{body}}
  </div>
  <div class="post-foot">
    <p class="source">Originally published in Chinese on WeChat, {{date_display}}, as
      <a href="{{source_url}}" rel="noopener">{{source_title}}</a>.</p>
    <p>Translation and figures by {{author}}. Corrections are welcome by
      <a href="{{github}}/yitian-aidd-blog/issues">opening an issue</a>.</p>
  </div>
  <nav class="post-nav">
{{post_nav}}
  </nav>
</article>
"""

PAGE = """<article class="post">
  <h1 class="post-title">{{title}}</h1>
  <div class="post-body">
{{body}}
  </div>
</article>
"""

TAG_PAGE = """<div class="page-head">
  <h1>Posts tagged “{{tag_label}}”</h1>
  <p class="lede">{{count}} post(s). <a href="{{prefix}}tags.html">All tags</a></p>
</div>
<div class="post-list">
{{items}}
</div>
"""

TAGS_INDEX = """<div class="page-head">
  <h1>Tags</h1>
  <p class="lede">{{count}} tags across {{post_count}} posts.</p>
</div>
<div class="tags" style="gap:10px">
{{items}}
</div>
"""

ICON_GITHUB = (
    '<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">'
    '<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 '
    "0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 "
    "1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 "
    "0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.42 7.42 0 0 1 2-.27c.68 0 "
    "1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 "
    "3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 "
    '8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>'
)
ICON_RSS = (
    '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
    '<path d="M6.18 17.82a2.18 2.18 0 1 1-4.36 0 2.18 2.18 0 0 1 4.36 0Z"/>'
    '<path d="M1.82 8.4v3.05c5.93 0 10.73 4.8 10.73 10.73h3.05c0-7.6-6.18-13.78-13.78-13.78Z"/>'
    '<path d="M1.82 1.82v3.05C10.5 4.87 17.5 11.87 17.5 20.55h3.05c0-11.98-9.75-21.73-21.73-21.73Z"/>'
    "</svg>"
)


def fill(template: str, **values: object) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def load_posts() -> list[dict]:
    posts: list[dict] = []
    for path in sorted(POSTS.glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        post_date = datetime.strptime(meta.get("date", "1970-01-01"), "%Y-%m-%d").date()
        tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
        words = len(re.findall(r"[A-Za-z0-9']+", body))
        posts.append(
            {
                "slug": path.stem,
                "title": meta.get("title", path.stem),
                "date": post_date,
                "tags": tags,
                "summary": meta.get("summary", ""),
                "source_url": meta.get("source_url", ""),
                "source_title": meta.get("source_title", ""),
                "body": body,
                "reading_time": max(1, round(words / 200)),
            }
        )
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def post_list_items(posts: list[dict], prefix: str) -> str:
    blocks = []
    for post in posts:
        tags = "".join(
            f'<a class="tag" href="{prefix}tags/{t}.html">{TAG_LABELS.get(t, t)}</a>' for t in post["tags"]
        )
        blocks.append(
            '<article class="post-item">'
            f'<h2><a href="{prefix}posts/{post["slug"]}.html">{html.escape(post["title"])}</a></h2>'
            '<div class="meta">'
            f'<time datetime="{post["date"].isoformat()}">{pretty_date(post["date"])}</time>'
            '<span class="dot">·</span>'
            f'<span>{post["reading_time"]} min read</span>'
            "</div>"
            f'<p class="summary">{inline(post["summary"])}</p>'
            f'<div class="tags" style="margin-top:10px">{tags}</div>'
            "</article>"
        )
    return "\n".join(blocks)


def recent_sidebar(posts: list[dict], prefix: str) -> str:
    items = []
    for post in posts[:6]:
        items.append(
            f'<li><a href="{prefix}posts/{post["slug"]}.html">{html.escape(post["title"])}</a>'
            f'<time>{pretty_date_short(post["date"])}</time></li>'
        )
    return "\n".join(items)


def page_shell(content: str, prefix: str, *, title: str, description: str, canonical: str,
               og_type: str, nav: str, posts: list[dict]) -> str:
    return fill(
        BASE,
        title=html.escape(title),
        description=html.escape(description),
        canonical=canonical,
        og_type=og_type,
        prefix=prefix,
        site_title=SITE["title"],
        author=SITE["author"],
        tagline=SITE["tagline"],
        github=SITE["github"],
        wechat_account=SITE["wechat_account"],
        icon_github=ICON_GITHUB,
        icon_rss=ICON_RSS,
        nav_home=' class="active"' if nav == "home" else "",
        nav_tags=' class="active"' if nav == "tags" else "",
        nav_about=' class="active"' if nav == "about" else "",
        recent=recent_sidebar(posts, prefix),
        content=content,
    )


def build() -> int:
    posts = load_posts()
    if not posts:
        print("no posts found in content/posts", file=sys.stderr)
        return 1

    if DOCS.exists():
        for child in DOCS.iterdir():
            if child.name == ".git":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "posts").mkdir(exist_ok=True)
    (DOCS / "tags").mkdir(exist_ok=True)

    shutil.copytree(THEME / "static", DOCS / "assets", dirs_exist_ok=True)
    if (ROOT / "images").exists():
        shutil.copytree(ROOT / "images", DOCS / "images", dirs_exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    favicon = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="7" fill="#1f7a6d"/>'
        '<text x="16" y="22" font-family="Georgia, serif" font-size="17" fill="#fff" '
        'text-anchor="middle">Y</text></svg>'
    )
    (DOCS / "assets" / "favicon.svg").write_text(favicon, encoding="utf-8")

    # index
    index = fill(
        INDEX,
        site_title=SITE["title"],
        blurb=SITE["blurb"],
        items=post_list_items(posts, ""),
    )
    (DOCS / "index.html").write_text(
        page_shell(index, "", title=SITE["title"], description=SITE["blurb"],
                   canonical=f"{SITE['url']}/", og_type="website", nav="home", posts=posts),
        encoding="utf-8",
    )

    # posts
    for position, post in enumerate(posts):
        body_html, toc = render_markdown(post["body"], "../")
        toc_html = "\n".join(
            f'<li><a href="#{anchor}">{html.escape(title)}</a></li>' for _, anchor, title in toc
        )
        prev_post = posts[position + 1] if position + 1 < len(posts) else None
        next_post = posts[position - 1] if position > 0 else None
        nav_parts = []
        nav_parts.append(
            f'<a href="../posts/{next_post["slug"]}.html">← {html.escape(next_post["title"])}</a>'
            if next_post else "<span></span>"
        )
        nav_parts.append(
            f'<a href="../posts/{prev_post["slug"]}.html">{html.escape(prev_post["title"])} →</a>'
            if prev_post else "<span></span>"
        )
        tags_html = "".join(
            f'<a class="tag" href="../tags/{t}.html">{TAG_LABELS.get(t, t)}</a>' for t in post["tags"]
        )
        article = fill(
            POST,
            title=html.escape(post["title"]),
            iso=post["date"].isoformat(),
            date_display=pretty_date(post["date"]),
            reading_time=post["reading_time"],
            tags=f'<span class="dot">·</span><span class="tags">{tags_html}</span>' if tags_html else "",
            toc=toc_html or f'<li><a href="#">{html.escape(post["title"])}</a></li>',
            body=body_html,
            source_url=post["source_url"] or SITE["github"],
            source_title=html.escape(post["source_title"] or post["title"]),
            author=SITE["author"],
            github=SITE["github"],
            post_nav="\n".join(nav_parts),
        )
        (DOCS / "posts" / f"{post['slug']}.html").write_text(
            page_shell(article, "../", title=f"{post['title']} · {SITE['title']}",
                       description=post["summary"], canonical=f"{SITE['url']}/posts/{post['slug']}.html",
                       og_type="article", nav="home", posts=posts),
            encoding="utf-8",
        )

    # tags
    tag_map: dict[str, list[dict]] = {}
    for post in posts:
        for tag in post["tags"]:
            tag_map.setdefault(tag, []).append(post)
    for tag, tagged in sorted(tag_map.items()):
        label = TAG_LABELS.get(tag, tag)
        content = fill(
            TAG_PAGE,
            tag_label=html.escape(label),
            count=len(tagged),
            prefix="../",
            items=post_list_items(tagged, "../"),
        )
        (DOCS / "tags" / f"{tag}.html").write_text(
            page_shell(content, "../", title=f"{label} · {SITE['title']}",
                       description=f"Posts tagged {label}", canonical=f"{SITE['url']}/tags/{tag}.html",
                       og_type="website", nav="tags", posts=posts),
            encoding="utf-8",
        )

    tags_index = fill(
        TAGS_INDEX,
        count=len(tag_map),
        post_count=len(posts),
        items="\n".join(
            f'<a class="tag" href="tags/{tag}.html">{TAG_LABELS.get(tag, tag)} '
            f'<span style="color:var(--text-faint)">{len(items)}</span></a>'
            for tag, items in sorted(tag_map.items())
        ),
    )
    (DOCS / "tags.html").write_text(
        page_shell(tags_index, "", title=f"Tags · {SITE['title']}", description="All tags",
                   canonical=f"{SITE['url']}/tags.html", og_type="website", nav="tags", posts=posts),
        encoding="utf-8",
    )

    # about / profile page (content lives in profile.py)
    try:
        from profile import PROFILE_HTML as _profile_html
        content = _profile_html
    except Exception as exc:  # noqa: BLE001
        print(f"warning: profile.py unavailable ({exc}); using the simple about page")
        content = fill(PAGE, title="About", body=f"<p>{html.escape(SITE['blurb'])}</p>")
    (DOCS / "about.html").write_text(
        page_shell(content, "", title=f"About · {SITE['title']}", description=SITE["blurb"],
                   canonical=f"{SITE['url']}/about.html", og_type="website", nav="about", posts=posts),
        encoding="utf-8",
    )

    # 404
    not_found = (
        '<div class="page-head"><h1>Page not found</h1>'
        '<p class="lede">That link does not exist. Try the <a href="index.html">post list</a>.</p></div>'
    )
    (DOCS / "404.html").write_text(
        page_shell(not_found, "", title=f"Not found · {SITE['title']}", description="Not found",
                   canonical=f"{SITE['url']}/404.html", og_type="website", nav="", posts=posts),
        encoding="utf-8",
    )

    # feed
    items = []
    for post in posts[:20]:
        url = f"{SITE['url']}/posts/{post['slug']}.html"
        body_html, _ = render_markdown(post["body"], SITE["url"] + "/")
        items.append(
            "<item>"
            f"<title>{html.escape(post['title'])}</title>"
            f"<link>{url}</link>"
            f"<guid isPermaLink=\"true\">{url}</guid>"
            f"<pubDate>{post['date'].strftime('%a, %d %b %Y 00:00:00 +0800')}</pubDate>"
            f"<description>{html.escape(post['summary'])}</description>"
            f"<content:encoded><![CDATA[{body_html}]]></content:encoded>"
            "</item>"
        )
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">\n<channel>'
        f"<title>{html.escape(SITE['title'])}</title>"
        f"<link>{SITE['url']}/</link>"
        f"<description>{html.escape(SITE['blurb'])}</description>"
        f"<language>en</language>"
        + "".join(items)
        + "</channel></rss>\n"
    )
    (DOCS / "feed.xml").write_text(feed, encoding="utf-8")

    # sitemap
    urls = [f"{SITE['url']}/", f"{SITE['url']}/about.html", f"{SITE['url']}/tags.html"]
    urls += [f"{SITE['url']}/posts/{p['slug']}.html" for p in posts]
    urls += [f"{SITE['url']}/tags/{t}.html" for t in tag_map]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{u}</loc></url>" for u in urls)
        + "</urlset>\n"
    )
    (DOCS / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    print(f"built {len(posts)} posts, {len(tag_map)} tags -> {DOCS}")
    return 0


def serve() -> None:
    import functools
    import http.server
    import socketserver

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    with socketserver.TCPServer(("127.0.0.1", 8080), handler) as httpd:
        print("serving docs/ at http://127.0.0.1:8080 (ctrl-c to stop)")
        httpd.serve_forever()


if __name__ == "__main__":
    code = build()
    if code == 0 and "--serve" in sys.argv:
        serve()
    raise SystemExit(code)
