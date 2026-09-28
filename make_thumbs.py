"""Generate the square cover thumbnails used by the post list.

For every content/posts/*.md the source is the front matter ``cover:`` path when
it is set, otherwise the first image in the body. Output goes to
images/thumbs/<slug>.jpg as a 320x320 centre crop, so the index and tag pages
never load a full-size figure.

Usage:  python make_thumbs.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
POSTS = ROOT / "content" / "posts"
THUMBS = ROOT / "images" / "thumbs"
SIZE = 320
QUALITY = 82


def split_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta, parts[2]


def first_image(body: str) -> str:
    """Return the path of the first markdown image in the body."""
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("!["):
            open_at = line.find("](")
            close_at = line.find(")", open_at + 2)
            if open_at != -1 and close_at != -1:
                return line[open_at + 2 : close_at]
    return ""


def centre_square(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side)).resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    THUMBS.mkdir(parents=True, exist_ok=True)
    for markdown in sorted(POSTS.glob("*.md")):
        meta, body = split_front_matter(markdown.read_text(encoding="utf-8"))
        source = meta.get("cover") or first_image(body)
        if not source:
            print(f"{markdown.stem}: no cover source")
            continue
        path = ROOT / source
        if not path.exists():
            print(f"{markdown.stem}: {source} missing")
            continue
        out = THUMBS / f"{markdown.stem}.jpg"
        centre_square(path).save(out, quality=QUALITY, optimize=True)
        print(f"{markdown.stem}: {source} -> thumbs/{out.name} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
