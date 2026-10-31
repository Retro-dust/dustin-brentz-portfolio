#!/usr/bin/env python3
"""Download portfolio media and write the static site."""

import html
import json
import os
import re
import struct
import subprocess
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
WORK = ASSETS / "work"
VIDEO = ASSETS / "video"
FFMPEG = ROOT / ".tmp-tools/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

PNG_ORIGINALS = {
    "9598c7_fd5d9017d05745269485c5dcdf139f59~mv2.png": "logo.png",
    "9598c7_96fc30e3b83d4343a00dd5ae25188df2~mv2.png": "wordmark.png",
    "9598c7_a37f22f2d2234b9fb0ac58d7f49bc075~mv2.png": "swoosh.png",
    "9598c7_0d9da4cc45de443985676f8e1ce89c36~mv2.png": "icon-team.png",
    "9598c7_2258960450be4eb2b5e0de27a741b80f~mv2.png": "icon-brain.png",
    "9598c7_b8de840bff9b4df4a79304f476a6278f~mv2.png": "icon-palette.png",
}


def esc(value):
    return html.escape(value or "", quote=True)


def slug(title):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower())).strip("-")


def image_size(path):
    data = path.read_bytes()[:64]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        blob = path.read_bytes()
        i = 2
        while i < len(blob) - 8:
            if blob[i] != 0xFF:
                i += 1
                continue
            marker = blob[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", blob[i + 5 : i + 9])
                return w, h
            if marker == 0xD8 or marker == 0xD9:
                i += 2
                continue
            length = struct.unpack(">H", blob[i + 2 : i + 4])[0]
            i += 2 + length
    return None, None


def crop_transparent_png(path):
    """Trim the soft transparent padding Wix adds around screenshots."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return
    idat = b""
    i = 8
    width = height = None
    while i < len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        kind = data[i + 4 : i + 8]
        chunk = data[i + 8 : i + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", chunk[:8])
            if chunk[8] != 8 or chunk[9] != 6:
                return
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
        i += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4
    pos = 0
    prev = bytearray(stride)
    rows = []

    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

    for _ in range(height):
        filt = raw[pos]
        pos += 1
        row = bytearray(raw[pos : pos + stride])
        pos += stride
        if filt == 1:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                row[x] = (row[x] + left) & 255
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 255
        elif filt == 3:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 255
        elif filt == 4:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                row[x] = (row[x] + paeth(left, prev[x], prev[x - 4] if x >= 4 else 0)) & 255
        elif filt != 0:
            return
        prev = row
        rows.append(row)

    def opaque(x, y):
        return rows[y][x * 4 + 3] > 220

    top = next((y for y in range(height) if any(opaque(x, y) for x in range(width))), None)
    if top is None:
        return
    bottom = next(y for y in range(height - 1, -1, -1) if any(opaque(x, y) for x in range(width)))
    left = next(x for x in range(width) if any(opaque(x, y) for y in range(top, bottom + 1)))
    right = next(x for x in range(width - 1, -1, -1) if any(opaque(x, y) for y in range(top, bottom + 1)))
    if top == 0 and left == 0 and bottom == height - 1 and right == width - 1:
        return

    import zlib as zlib_mod

    out_rows = []
    crop_w = right - left + 1
    for y in range(top, bottom + 1):
        row = bytearray(b"\x00")
        src = rows[y]
        for x in range(left, right + 1):
            row.extend(src[x * 4 : x * 4 + 4])
        out_rows.append(row)
    compressed = zlib_mod.compress(b"".join(out_rows), 9)

    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib_mod.crc32(kind + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", crop_w, bottom - top + 1, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b""))


def fetch(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/jpeg,image/png,*/*"})
    with urllib.request.urlopen(req, timeout=60) as response:
        dest.write_bytes(response.read())


def wix_jpg(file_id, width):
    return (
        f"https://static.wixstatic.com/media/{file_id}/v1/fit/w_{width},h_{width},q_90/{file_id}.jpg"
    )


def wix_png(file_id, width):
    return (
        f"https://static.wixstatic.com/media/{file_id}/v1/fit/w_{width},h_{width},q_90/{file_id}.png"
    )


def wix_original(file_id):
    return f"https://static.wixstatic.com/media/{file_id}"


class Library:
    def __init__(self):
        self.jobs = []
        self.paths = {}

    def add_png(self, file_id, name):
        rel = f"assets/{name}"
        self.paths[file_id] = rel
        self.jobs.append((wix_original(file_id), ROOT / rel))
        return "/" + rel

    def add_jpg(self, file_id, width=2000, name=None):
        if file_id in self.paths:
            return "/" + self.paths[file_id]
        stem = Path(file_id.split("~")[0].split("_", 1)[-1]).stem
        use_png = name is None and file_id.endswith(".png")
        rel = name or f"assets/work/{stem}.{'png' if use_png else 'jpg'}"
        self.paths[file_id] = rel
        url = wix_png(file_id, width) if use_png else wix_jpg(file_id, width)
        self.jobs.append((url, ROOT / rel))
        return "/" + rel

    def download(self):
        refreshed = 0
        for url, dest in self.jobs:
            if not dest.exists() or "assets/work/" not in str(dest):
                continue
            width, height = image_size(dest)
            if width and width < 900:
                dest.unlink()
                refreshed += 1
        if refreshed:
            print(f"refreshing {refreshed} low-resolution images")
        print(f"downloading {len(self.jobs)} images")
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(fetch, url, dest): dest for url, dest in self.jobs}
            for future in as_completed(futures):
                future.result()
        for url, dest in self.jobs:
            if dest.suffix == ".png" and not dest.name.startswith("hero-"):
                crop_transparent_png(dest)

    def add_asset(self, file_id, rel, kind="jpg", width=2000):
        url = wix_png(file_id, width) if kind == "png" else wix_jpg(file_id, width)
        self.jobs.append((url, ROOT / rel))
        return "/" + rel


def dims(src):
    path = ROOT / src.lstrip("/")
    if not path.exists():
        return "", ""
    w, h = image_size(path)
    if not w:
        return "", ""
    return f' width="{w}" height="{h}"', ""


ARROW_NEXT = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ARROW_PREV = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def strip_wrap(cards, extra_class=""):
    klass = f"strip-wrap {extra_class}".strip()
    return f"""<div class="{klass}" data-strip>
      <button class="strip-arrow strip-prev" type="button" aria-label="Previous item" hidden>{ARROW_PREV}</button>
      <ul class="strip">
        {''.join(cards)}
      </ul>
      <button class="strip-arrow strip-next" type="button" aria-label="Next item">{ARROW_NEXT}</button>
    </div>"""


def gallery_html(items, lib):
    cards = []
    for item in items:
        src = lib.add_jpg(item["file"])
        title = item.get("title") or ""
        description = item.get("description") or ""
        alt = title or "Portfolio image"
        cards.append(
            f"""<li>
            <button class="shot" type="button" data-full="{esc(src)}" data-title="{esc(title)}" data-text="{esc(description)}">
              <img src="{esc(src)}" alt="{esc(alt)}" loading="lazy">
            </button>
            {f"<h3>{esc(title)}</h3>" if title else ""}
            {f"<p>{esc(description)}</p>" if description else ""}
          </li>"""
        )
    return strip_wrap(cards)


def videos_html(clips, lib):
    blocks = []
    for clip in clips:
        poster = lib.add_jpg(clip["cover"], width=960)
        src = "/" + clip["local"]
        blocks.append(
            f"""<li class="clip">
            <video controls preload="none" poster="{esc(poster)}" playsinline>
              <source src="{esc(src)}" type="video/mp4">
            </video>
            <h3>{esc(clip["title"])}</h3>
          </li>"""
        )
    return strip_wrap(blocks, "videos")


def chrome(title, description, path, current, body):
    nav = [
        ("Home", "/", "home"),
        ("Product Design", "/product-design", "product"),
        ("Graphic Design", "/graphic-design", "graphic"),
        ("Resume", "/resume.pdf", "resume"),
    ]
    links = []
    for label, href, key in nav:
        current_attr = ' aria-current="page"' if key == current else ""
        extra = ' target="_blank" rel="noopener"' if key == "resume" else ""
        links.append(f'<a href="{href}"{current_attr}{extra}>{label}</a>')
    canonical = "https://www.dustinbrentz.com" + path
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <link rel="icon" href="/assets/logo.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Mulish:wght@300;400;700&family=Oxanium:wght@200;400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/css/styles.css?v=8">
</head>
<body>
  <a class="skip" href="#main">Skip to main content</a>
  <header class="site-header">
    <a class="brand" href="/" aria-label="Dustin Brentz home">
      <img src="/assets/logo.png" alt="">
    </a>
    <a class="brand-email" href="mailto:dustinbrentz@gmail.com">dustinbrentz@gmail.com</a>
    <nav class="site-nav" aria-label="Site">
      {''.join(links)}
    </nav>
  </header>
  {body}
  <footer class="site-footer">
    <h2>I hope you enjoyed my work.</h2>
    <p class="anytime">Message me anytime!</p>
    <a class="mail" href="mailto:dustinbrentz@gmail.com">dustinbrentz@gmail.com</a>
    <div>
      <a class="social" href="https://www.linkedin.com/in/dustinbrentz/" aria-label="LinkedIn">
        <svg width="25" height="25" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M4.98 3.5C4.98 4.88 3.88 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1s2.48 1.12 2.48 2.5zM.5 8.5h4V24h-4V8.5zM8.5 8.5h3.8v2.1h.05c.53-1 1.84-2.1 3.79-2.1 4.05 0 4.8 2.67 4.8 6.14V24h-4v-7.7c0-1.84-.03-4.2-2.56-4.2-2.56 0-2.95 2-2.95 4.06V24h-4V8.5z"/></svg>
      </a>
    </div>
    <p class="copy">© 2026 by Dustin Brentz</p>
  </footer>
  <dialog class="lightbox">
    <button class="lightbox-close" type="button" aria-label="Close">×</button>
    <button class="lightbox-nav lightbox-prev" type="button" aria-label="Previous image"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
    <button class="lightbox-nav lightbox-next" type="button" aria-label="Next image"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
    <figure>
      <img alt="">
      <figcaption>
        <h3></h3>
        <p></p>
      </figcaption>
    </figure>
  </dialog>
  <script src="/js/site.js?v=7"></script>
</body>
</html>
"""


def project(lead, gallery):
    label, text = lead.split(" - ", 1)
    return f'<p class="project-lead"><strong>{esc(label)}</strong> - {esc(text)}</p>\n{gallery}'


def company(name, role, years, bio, inner, soft=False):
    klass = "company soft" if soft else "company"
    return f"""<section class="{klass}" id="{slug(name)}">
      <h2>{esc(name)}</h2>
      <p class="role">{esc(role)}</p>
      <p class="years">{esc(years)}</p>
      {f'<p class="bio">{esc(bio)}</p>' if bio else ''}
      {inner}
    </section>"""


def cta(label, href):
    return f'<div class="cta-row"><a class="btn" href="{href}">{esc(label)}</a></div>'


READ_MORE = (
    '<span class="more">Read More '
    '<svg viewBox="20 72 162 52" aria-hidden="true"><path d="M154.8 72.3l-2 2L174 94.9 21.1 95v2.7l153-.1-22.2 22.5 1.9 2 25.4-25.8-24.4-24z"/></svg>'
    "</span>"
)


def case_card(href, image, title, role, text, shade):
    return f"""<a class="case" href="{href}">
          <img src="{image}" alt="{esc(title)}">
          <span class="shade {shade}"></span>
          <span class="copy">
            <h3>{esc(title)}</h3>
            <span class="role">{esc(role)}</span>
            <span class="blurb">{esc(text)}</span>
            {READ_MORE}
          </span>
        </a>"""


def case_hero(lib, file_id, name):
    rel = f"assets/{name}"
    url = (
        f"https://static.wixstatic.com/media/{file_id}/v1/fill/w_1440,h_344,al_t,q_90/{file_id}"
    )
    lib.jobs.append((url, ROOT / rel))
    return "/" + rel


def study_figure(lib, file_id, title, text):
    src = lib.add_jpg(file_id, 1600)
    return f"""<figure>
      <button class="study-shot" type="button" data-full="{esc(src)}" data-title="{esc(title)}" data-text="{esc(text)}">
        <img src="{esc(src)}" alt="{esc(title)}">
      </button>
      <figcaption><strong>{esc(title)}</strong><span>{esc(text)}</span></figcaption>
    </figure>"""


def study_row(lib, items, columns):
    klass = "trio" if columns == 3 else "pair"
    return f'<div class="{klass}">{"".join(study_figure(lib, *item) for item in items)}</div>'


def study_show(lib, slides):
    frames = []
    for file_id, title, text in slides:
        src = lib.add_jpg(file_id, 1600)
        frames.append(
            f"""<figure class="slide">
            <button class="slide-shot" type="button" data-full="{esc(src)}" data-title="{esc(title)}" data-text="{esc(text)}">
              <img src="{esc(src)}" alt="{esc(title)}">
            </button>
            <figcaption><strong>{esc(title)}</strong><span>{esc(text)}</span></figcaption>
          </figure>"""
        )
    return f"""<div class="slideshow" data-slideshow>
      <button class="slide-arrow slide-prev" type="button" aria-label="Previous">{ARROW_PREV}</button>
      <div class="slide-frame"><div class="slide-track">{''.join(frames)}</div></div>
      <button class="slide-arrow slide-next" type="button" aria-label="Next">{ARROW_NEXT}</button>
      <p class="slide-count"></p>
    </div>"""


def study_band(inner, soft=False):
    klass = "study-band soft" if soft else "study-band"
    return f'<section class="{klass}"><div class="study">{inner}</div></section>'


def study_page(kicker, title, role, year, hero, body, cta_label, cta_href):
    return f"""
  <main id="main">
    <section class="page-hero case-hero">
      <img src="{hero}" alt="">
      <div class="case-hero-copy">
        <p class="kicker">{esc(kicker)}</p>
        <h1>{esc(title)}</h1>
        <p class="role">{esc(role)}</p>
        <p class="year">{esc(year)}</p>
      </div>
    </section>
    {body}
    <div class="study-cta"><a class="btn pill" href="{cta_href}">{esc(cta_label)}</a></div>
  </main>"""


def download_videos(videos):
    jobs = []
    for group in videos.values():
        for clip in group:
            dest = ROOT / clip["local"]
            if dest.exists() and dest.stat().st_size > 1000:
                continue
            jobs.append((clip["hls"], dest, clip["title"]))
    print(f"encoding {len(jobs)} videos")

    def run(job):
        hls, dest, title = job
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(FFMPEG), "-y", "-loglevel", "error", "-i", hls,
            "-c:v", "libx264", "-crf", "27", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dest),
        ]
        subprocess.run(cmd, check=True)
        print("video", title, dest.stat().st_size)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(run, jobs))


def main():
    product = json.loads((DATA / "product-galleries.json").read_text())
    graphic = json.loads((DATA / "graphic-galleries.json").read_text())
    videos = json.loads((DATA / "videos.json").read_text())
    lib = Library()

    for file_id, name in PNG_ORIGINALS.items():
        lib.add_png(file_id, name)

    hero_product = "/assets/hero-product.png"
    hero_graphic = "/assets/hero-graphic.jpg"
    lib.jobs.append((
        "https://static.wixstatic.com/media/9598c7_91ec771544044a96ba49776fd48f6de4~mv2.png/v1/fill/w_1600,h_381,al_c,q_90/9598c7_91ec771544044a96ba49776fd48f6de4~mv2.png",
        ROOT / "assets/hero-product.png",
    ))
    lib.jobs.append((
        "https://static.wixstatic.com/media/9598c7_38ed91fbb5aa425ab9f9536eaf849af7~mv2.jpg/v1/fill/w_1600,h_381,al_c,q_85/9598c7_38ed91fbb5aa425ab9f9536eaf849af7~mv2.jpg",
        ROOT / "assets/hero-graphic.jpg",
    ))
    card_product = lib.add_jpg("9598c7_91ec771544044a96ba49776fd48f6de4~mv2.png", 1200)
    card_graphic = lib.add_jpg("9598c7_23c81532b4db4c7caf3cf91431f3d879~mv2.jpg", 1200)
    card_animation = lib.add_jpg("9598c7_d5ba1e1bc6e54f3498e3a5c2e8abdee6~mv2.png", 1200, "assets/card-animation.jpg")
    case_whiteboard = lib.add_jpg("9598c7_851d3e69f1d04f599efa92a33f658152~mv2.jpg", 1200, "assets/case-whiteboard.jpg")
    case_editors = lib.add_jpg("9598c7_899355bf001c4733ab9fa0070bf20732~mv2.jpg", 1200, "assets/case-editors.jpg")

    for group in videos.values():
        for clip in group:
            clip["local"] = f"assets/video/{slug(clip['title'])}.mp4"

    pg = lambda key: gallery_html(product[key], lib)
    gg = lambda key: gallery_html(graphic[key], lib)
    vg = lambda key: videos_html(videos[key], lib)

    home = f"""
  <main id="main">
    <section class="hero">
      <img class="wordmark" src="/assets/wordmark.png" alt="Dustin Brentz">
      <p class="eyebrow"><span>Design Leader</span><img src="/assets/swoosh.png" alt=""><span>Versatile Creative</span></p>
      <h1><span>Crafting </span><span class="strong">Creative</span><span>, </span><span class="strong">Empowering</span><span> Experiences</span></h1>
      <a class="btn lime" href="/product-design">View Portfolio</a>
    </section>
    <section class="section">
      <h2>Areas of Creative Experience</h2>
      <div class="areas">
        <a class="area" href="/product-design"><img src="{card_product}" alt=""><span>Product Design</span></a>
        <a class="area" href="/graphic-design"><img src="{card_graphic}" alt=""><span>Graphic Design</span></a>
        <div class="area"><img src="{card_animation}" alt=""><span>Animation and Video Games (Coming Soon)</span></div>
      </div>
    </section>
    <section class="section soft">
      <h2>A bit about me:</h2>
      <div class="about">
        <article>
          <img src="/assets/icon-team.png" alt="">
          <h3>Team Player</h3>
          <p>Great design comes from great teams. I care a lot about building the kind of environment where designers feel trusted, take risks, and do their best work. To build a structure that helps people grow into strategic thinkers is one of my favorite parts of leading.</p>
        </article>
        <article>
          <img src="/assets/icon-brain.png" alt="">
          <h3>Process Thinker</h3>
          <p>Good process creates momentum, not bottlenecks. I focus on clear priorities, strong stakeholder alignment, and systems that help teams move efficiently. AI and modern tools are leveraged to accelerate everything from research to delivery.</p>
        </article>
        <article>
          <img src="/assets/icon-palette.png" alt="">
          <h3>Versatile by Design</h3>
          <p>15+ years across product, graphic design, gaming, and animation. I aim to bring my full range to every project. Hands-on from start to finish, and always happy to dive in wherever I'm needed.</p>
        </article>
      </div>
    </section>
    {cta("View Portfolio", "/product-design")}
  </main>"""

    product_page = f"""
  <main id="main">
    <section class="page-hero product">
      <img src="{hero_product}" alt="">
      <h1>Product Design</h1>
    </section>
    <section class="section">
      <div class="intro">
        <p class="lead">Great products combine powerful technology with thoughtful design to solve meaningful problems.</p>
        <p>I focus on creating experiences that are useful, simple, and well-crafted—while also delivering measurable outcomes such as growth, engagement, and retention. By grounding vision in research and leveraging new technologies like AI, design can shape products that are both human-centered and forward-looking.</p>
      </div>
    </section>
    <section class="section soft">
      <h2>Case Studies</h2>
      <div class="cases">
        {case_card("/brightidea-whiteboard-case-study", case_whiteboard, "Brightidea - Whiteboard AI", "Senior Product Designer", "Discover the project that brought robust AI features to Brightidea's white-boarding tool.", "green")}
        {case_card("/marketo-editors-case-study", case_editors, "Adobe - Editors", "Product Designer III", "Marketo needed modernized email editors, and a combination of products provided the solution.", "blue")}
      </div>
    </section>
    {company("Brightidea", "Senior Product Designer", "2022 - 2026",
      "For the majority of my time at Brightidea I was the sole product designer. I worked closely with Product Management, Engineering, and QA on a multitude of areas across the product.",
      project("Hackathon - Event management product to run successful, end-to-end hackathons.", pg("comp-mn2wtb61"))
      + project("Whiteboard - Multi-feature zoomable canvas for easy collaboration.", pg("comp-mn2xqq1x"))
      + project("Project Room - A space for teams to house project assets such as tasks, files, Whiteboards, and more.", pg("comp-mn2xup22"))
      + project("Commercialization - Projects to benefit the growth and understanding of the products.", pg("comp-mn2y04bp1")))}
    {company("Adobe/Marketo", "Product Designer III", "2018 - 2022",
      "With Marketo my initial focus was on converting the product from the original design system to the new version. After the acquisition by Adobe, I worked deeply on revamping the design process to integrate with Adobe's processes. I also spent time working on motion guidelines, interactive prototypes, and maintaining the Pendo tagging duties for all areas.",
      project("Icon Refresh - Many of Marketo's icons were outdated and statuses were difficult to understand.", pg("comp-mn2zw80m"))
      + project("Motion & Prototyping - Created motion guideline standards and worked on numerous interactive prototypes.", vg("marketo"))
      + project("Other Projects - Various other projects from around the entire product.", pg("comp-mn309lj1")), soft=True)}
    {company("Weedmaps", "Senior Interaction Designer", "2015 - 2018",
      "During my time at Weedmaps I worked on many projects focused on bringing an updated experience to users from mobile to responsive web. Focus was heavily placed on user research and discovering optimal ways for business owners and admins to easily use the product. I eventually began to focus on motion and micro-interactions for all areas of Weedmaps.",
      project("Motion & Prototyping - Led a team to bring motion to Weedmaps and create interactive prototypes.", vg("weedmaps")))}
    {company("Fusion of Ideas", "Lead Digital Designer", "2013 - 2015",
      "Fusion of Ideas creates full branding experiences from hardware to software customization. We worked directly with Apple BDMs on a multitude of projects for some of the largest brands in the world.",
      project("Audi - We built a custom hardware ordering portal and a maintenance history POC for Audi.", pg("comp-mn3tnvlg"))
      + project("Targa Trophy - This app was created for Targa Trophy rally navigators to keep track of all parts of the event.", pg("comp-mn3ts3l6"))
      + project("NCE/NRE - Timesheet and safety protocol apps plus a backend portal for two energy companies.", pg("comp-mn4crehm"))
      + project("Other Projects - These screens are quick glances at other projects worked on at Fusion.", pg("comp-mn3ttq97")), soft=True)}
    {company("Scareproof", "Personal Project - Creator/Designer", "2013",
      "This was an original idea of mine that I created with a mobile developer. It aimed to show kids that there are no monsters or bad things in their room at night. It also acted as a nightlight for extra security.",
      pg("comp-mn3tziur"))}
    {cta("View Graphic Design", "/graphic-design")}
  </main>"""

    graphic_page = f"""
  <main id="main">
    <section class="page-hero graphic">
      <img src="{hero_graphic}" alt="">
      <h1>Graphic Design</h1>
    </section>
    <section class="section">
      <div class="intro">
        <p class="lead">Graphic Design was my foray into a creative career and was the basis of my art experience.</p>
        <p>While I have been on the UX/UI side of design for a good while, Graphic Design was the first passion in my career. The problems and solutions may be different, but working with the right team can make visual design an event within itself.</p>
      </div>
    </section>
    {company("The Dabbing Specialist", "Creative Director", "2017 - 2018",
      "The Dabbing Specialist was a startup with a 3-man crew. I wore many hats at the company. Aside from design duties I assisted in sales, marketing, product photography and editing, setting up and running trade shows, and much more.",
      project("Social Posts - My goal was to make unique posts that kept our products at the heart of the designs.", gg("social"))
      + project("Apparel - Early apparel was simple, but we ramped up the visual style as we went along.", gg("apparel"))
      + project("Other Designs - Various print, digital, and other designs.", gg("other")), soft=True)}
    {company("Fusion of Ideas", "Lead Digital Designer", "2013 - 2015",
      "",
      project("Service Posters - Blending 80's goodness with Fusion's offerings turned out to be an incredible match.", gg("fusion")))}
    {company("New Leaf Insurance", "Designer", "2017",
      "New Leaf was in need of branding, so I worked up cohesive designs for their initial needs. Working closely with the owners, I delivered them a logo, collateral pieces, and social media posts.",
      gg("newleaf"), soft=True)}
    {company("Freelance & Personal", "Graphic Designer", "2008 - 2016",
      "Many of these personal designs are much older, but they tell part of the story. Whether freelance or personal so many of these projects come with stellar memories of their creation.",
      project("Various Designs - Random designs from the way back.", gg("freelance")))}
    {cta("View Product Design", "/product-design")}
  </main>"""

    whiteboard_hero = case_hero(lib, "9598c7_0fc777304a684b649c4ce12933ded7e2~mv2.png", "hero-case-whiteboard.png")
    marketo_hero = case_hero(lib, "9598c7_a4c2a87e841b467385c54ee51bba76d5~mv2.png", "hero-case-marketo.png")
    whiteboard_page = study_page(
        "Case Study",
        "Whiteboard AI",
        "Senior Product Designer",
        "2024",
        whiteboard_hero,
        study_band(f"""
      <h2>The Challenge</h2>
      <p>Brightidea's Whiteboard tool had AI features but usage was not where it needed to be. The existing implementation let users generate a handful of sticky notes from a text prompt, and that was it. As competitors began shipping richer AI-powered collaboration features, the gap was becoming a liability.</p>
      <p>The business goal was clear: make Whiteboard's AI genuinely useful so that customers would see it as a reason to remain on the platform, and not leave for a competing tool.</p>
      {study_figure(lib, "9598c7_7ff540f6279d4f63b35748fead2af460~mv2.png", "Initial AI Tool", "The previous AI option was only to create idea stickies in a limited manner.")}
        """)
        + study_band("""
      <h2>My Role</h2>
      <p>As the sole product designer at Brightidea for most of my tenure, I owned the design side of this project end-to-end from initial research through release. I partnered closely with a product manager, customer success, and engineering team throughout.</p>
        """, soft=True)
        + study_band(f"""
      <h2>Understanding the Problem</h2>
      <p>Before laying out a single thing, we started researching. The existing AI tools had low engagement, but we didn't know why. Discoverability, trust, relevance, friction? All were on the table.</p>
      <p>Working with the PM and customer success team, we ran user interviews and quickly found the real culprit: the experience dead-ended upon their initial prompt. There were no ways to expand ideas, no clustering for organization, and no path to prioritization.</p>
      <p>That reframed everything. It was a rethink of how AI should live inside the whiteboard workflow.</p>
      {study_row(lib, [
          ("9598c7_59d0312e40894321aa185f1c5f2e5bf9~mv2.jpg", "Previous AI Feature", "The breakdown of previous AI tools."),
          ("9598c7_02b819fff4fc4d3c925b71530fd71dc8~mv2.png", "User Research", "We talked with users and bucketed their needs into several areas of interest and feasibility."),
      ], 2)}
        """)
        + study_band(f"""
      <h2>Exploring the Solution Space</h2>
      <p>An audit of Miro, FigJam, Mural, and other emerging zoomable UI AI-native tools revealed a clear pattern: the best implementations felt like a collaborator on the canvas, not a separate tool you had to go find.</p>
      <p>I explored two directions. An AI panel accessed from the left nav that utilized our original space for the tool, and a context based menu that responded to whatever was selected on the canvas.</p>
      {study_figure(lib, "9598c7_9d0a91f7ba684c5bbd6ad01769f81806~mv2.png", "Competitive Research", "Research from various canvas based competitors and other AI offerings.")}
        """, soft=True)
        + study_band(f"""
      <h2>The Solution</h2>
      <p>The revamped AI system shipped as a two-pronged experience:</p>
      <h3>AI Panel (Left Navigation)</h3>
      <p>Upon deeper testing, the original location was a dedicated, always-visible space for generating ideas, expanding thinking, and running AI-assisted sessions. Designed to be discoverable without dominating the canvas.</p>
      <h3>Contextual AI Menu</h3>
      <p>When a user selects a sticky, cluster, or group of objects, relevant AI actions surface via a context menu.</p>
      <ul>
        <li>Select five stickies and get the option to synthesize them into themes and other options.</li>
        <li>Select one idea and expand it into numerous, corresponding ideas and related concepts.</li>
      </ul>
      <p>The AI reads what you're doing and responds accordingly.</p>
      <p>Key capabilities shipped: idea expansion from a single prompt, smart matrix generation from a cluster of stickies, AI-powered grouping and labeling, and image generation for team branding within the hackathon flow.</p>
      {study_show(lib, [
          ("9598c7_12387047be4e4076889d3f682f2f1932~mv2.png", "Whiteboard AI Iteration", "This design showcased a prompt in the lower left."),
          ("9598c7_d419777c5b2c4296837c85e150a6fecf~mv2.png", "Whiteboard AI Iteration", "This design utilized a prompt that derived from the left toolbar."),
          ("9598c7_979507e1055a461ba70296bbb7df3d5d~mv2.png", "Whiteboard AI Iteration", "This iteration featured a voice-to-UI variation."),
          ("9598c7_05dc41330e8c4cc6a650a5586b06b4d7~mv2.png", "Whiteboard AI Context Menu", "Initial pass at the context menu for the updated AI features."),
          ("9598c7_47b27735c6cb47beb646e099377dc84b~mv2.png", "Whiteboard AI Canvas Document", "PRD styled document on Whiteboard canvas."),
          ("9598c7_70d2ec3b0e844ea4bf8a08046d7db89b~mv2.png", "Whiteboard AI Canvas Document", "PRD styled document on Whiteboard canvas."),
          ("9598c7_7ba9408d2cb443e3aa660dd6f71123e0~mv2.png", "Whiteboard AI Canvas Document", "PRD styled document on Whiteboard canvas."),
      ])}
        """)
        + study_band(f"""
      <h2>The Solution</h2>
      <p>The final design used a two-pronged approach: a main panel in the left navigation and a context menu that adapted based on what was selected on the canvas.</p>
      <p>Post-launch results were strongly positive. Time spent in the tool increased, ideas generated per session rose measurably, and users described the AI features as "actually useful". It was exactly the bar we'd set out to clear. The project also laid the foundation for how Brightidea would approach AI integration across the rest of the product.</p>
      {study_show(lib, [
          ("9598c7_d087462a71804b2cb5aff0106a86db99~mv2.png", "AI Panel in Left Navigation", "Made to be easily discoverable and to also not distract the users."),
          ("9598c7_e24fa0aa633b453aa0c7840dff016994~mv2.png", "AI Created Stickie Notes", "From one idea to many in just a click."),
          ("9598c7_3d85c08a94554aabbe046a755b726e0f~mv2.png", "AI Chatbot", "Initial empty state."),
          ("9598c7_a1142e9d43fe458f98460eaee8734e06~mv2.png", "AI Chatbot", "Gives the user the ability to convert any chat info into notes or stickies."),
          ("9598c7_057827252ec34d77b450f7da0112b6b1~mv2.png", "AI Chatbot", "Chat converted into stickie form."),
          ("9598c7_81b626ef993c4ee5b7a9c5db2391bf6b~mv2.png", "AI Context Menu", "Another method for the user to interact and use AI tools based on item selection."),
          ("9598c7_7712e4cbd9bd4d82ba0b512bcdf87edb~mv2.png", "AI Context Menu", "When more than one item is selected the options adjust automatically."),
          ("9598c7_0fc777304a684b649c4ce12933ded7e2~mv2.png", "AI Context Menu", "Options for a selected block of text."),
          ("9598c7_9921ca75d5734d2d97376bb0b5003878~mv2.png", "AI Context Menu", "Organization options to cluster items."),
          ("9598c7_fe91f021b7df428a9715a8204230a67e~mv2.png", "AI Generated Smart Matrix", "A matrix created from an array of stickies based on user-set parameters."),
      ])}
        """, soft=True),
        "View Marketo Editors Case Study",
        "/marketo-editors-case-study",
    )
    marketo_page = study_page(
        "Case Study",
        "Marketo Editors",
        "Product Designer 3 (Lead)",
        "2021 - 2022",
        marketo_hero,
        study_band(f"""
      <h2>The Challenge</h2>
      <p>When Adobe acquired Marketo, it inherited a product with deeply entrenched workflows and editors that hadn't kept pace with modern UX standards. Marketo's email, form, and landing page editors were functional, but clunky and dated. They didn't align with Adobe's design system, and they created friction for the power users who lived inside them every day.</p>
      <p>The goal was to modernize all three editors not by building from scratch, but by finding the right Adobe-native editor foundations and adapting them to Marketo's specific needs.</p>
      {study_row(lib, [
          ("9598c7_7116b695832d4162a077bb6d1d0126d0~mv2.png", "Old Marketo Email Editor", "The original Marketo email editor experience."),
          ("9598c7_f84c234be9ed4292a7e16f838399c924~mv2.png", "Adobe's Spectrum Editor", "One of Adobe's current editors using the Spectrum design system."),
      ], 2)}
        """)
        + study_band("""
      <h2>My Role</h2>
      <p>I led Marketo's side of design for this initiative, working across multiple Adobe product teams to source existing editor components. Also, I worked with the research team to conduct user testing with Marketo's power users, built full-scale prototypes in XD, and drove alignment between Marketo and the Adobe teams whose technology we were adopting.</p>
        """, soft=True)
        + study_band(f"""
      <h2>The Constraint That Changed Everything</h2>
      <p>We weren't starting with a blank canvas. Adobe already had editors in production that were built, tested, and maintained by other teams. The challenge wasn't inventing something new; it was navigating a complex internal ecosystem to find the right foundation, then proving that it would actually work for Marketo's users.</p>
      <p>This meant doing real cross-functional work: relationship building, technical scoping, user validation, and design translation all at once.</p>
      {study_figure(lib, "9598c7_50ad39b9a47c4c9ba32b583b4a10b750~mv2.png", "Adobe Spectrum Editor Structure", "Adobe had a basic structure their editors would follow, and we used this as a foundation.")}
        """)
        + study_band(f"""
      <h2>The Process</h2>
      <h3>Step 1: Editor Landscape Across Adobe</h3>
      <p>I reached out to multiple product teams across Adobe to map what editors already existed, how they were structured, and which might be a fit. This surfaced two strong candidates. One used in Adobe Journey Optimizer (AJO) and another from the Adobe Experience Manager (AEM) with a more flexible content structure that aligned with Marketo's email templating model.</p>
      {study_row(lib, [
          ("9598c7_15edba79d17d4c8fa5b26dc115375610~mv2.png", "Adobe AJO Editor", "One of Adobe's newer editors for journey optimization."),
          ("9598c7_2f470df658f34e4792d4ae285f75b23e~mv2.png", "Adobe AJO/Experience Platform Editor", "Adobe editor for the Experience Cloud Platform."),
          ("9598c7_cb3d167b0a814f5daf0d3f495d97e765~mv2.png", "Adobe Editor Flow", "The basic flow for editors in several Adobe products."),
      ], 3)}
      <h3>Step 2: User Testing and Internal/Competitor Research</h3>
      <p>Rather than assume which editor would work best, we brought our Adobe-based options to Marketo's heaviest editor users. What we heard shaped the direction: users needed robust template management, inline image editing, version history, and a cleaner content structure panel.</p>
      <p>We also audited all Marketo editors, their features, and functions, and we did research and analysis of competitors in the editor space.</p>
      {study_row(lib, [
          ("9598c7_06d3757cb2584b568f65e9390288a714~mv2.png", "Competitor Editors", "Competitive research of other editors that were highly utilized at the time."),
          ("9598c7_45ed57985bfa442793a23269569e52f1~mv2.png", "Internal Editor Audit", "Internal editor audit and analysis to determine full scope of needs."),
      ], 2)}
      <h3>Step 3: Adapting the Foundation</h3>
      <p>Working closely with the Adobe editor teams, I designed Marketo-specific adaptations with component modifications, new interaction patterns, and UI adjustments to bring the editors in line with Marketo's workflows while staying within Adobe's Spectrum design system. This required constant negotiation between what was technically feasible and what users actually needed.</p>
      {study_row(lib, [
          ("9598c7_bf5c314304514a3a8da22e22532544aa~mv2.png", "Old Marketo Email Editor", "The original editor for building and updating emails and templates."),
          ("9598c7_3b1137b6335c4ac28f049a0ed15712de~mv2.png", "Updated Marketo Email Editor", "The updated editor with Adobe editor elements grounding the Marketo user needs."),
      ], 2)}
      <h3>Step 4: Full-Fidelity Prototyping and Validation</h3>
      <p>I built complete end-to-end prototypes in XD for all three editors (email, landing page, and form) and ran a second round of user testing to validate the adapted designs before dev handoff.</p>
      <h3>Email Editor</h3>
      {study_show(lib, [
          ("9598c7_9d9085e4e7244e00be80c18afa647085~mv2.png", "Marketo Email Editor", "Full editor flow."),
          ("9598c7_ea18a12a320c4bcf997423085a96ce6b~mv2.png", "Marketo Email Editor", "Template selection."),
          ("9598c7_7cbfd9a87e7f42469578820c73024c54~mv2.png", "Marketo Email Editor", "Main editor empty state."),
          ("9598c7_3b1137b6335c4ac28f049a0ed15712de~mv2.png", "Marketo Email Editor", "Main editor with email loaded."),
          ("9598c7_59bcf173731045f3a2b17a5b7cfa106b~mv2.png", "Marketo Email Editor", "Main editor with object selection."),
          ("9598c7_d3c6cae3d7574d48be1bd6995e7d4468~mv2.png", "Marketo Email Editor", "Left rail variation."),
          ("9598c7_affdff5ae11549808d1331a8ce6fe7bf~mv2.png", "Marketo Email Editor", "HTML mode."),
          ("9598c7_4d33478cb4fb4dc4a7dc63d615e2f451~mv2.png", "Marketo Email Editor", "Adding elements via drag and drop."),
          ("9598c7_9882b2589cf14f248bf349a8d4e9ebd5~mv2.png", "Marketo Email Editor", "Send sample email modal."),
          ("9598c7_924ce1ec974a49fda9d4d3ac05018c8b~mv2.png", "Marketo Email Editor", "Add assets modal."),
          ("9598c7_444df88d502e439ea49945ecd9d5d9ac~mv2.png", "Marketo Email Editor", "Image editor."),
      ])}
      <h3>Landing Page Editor</h3>
      {study_show(lib, [
          ("9598c7_ffddf505a81145ea8bc8fa9ac2e6c6d9~mv2.png", "Marketo Landing Page Editor", "Full landing page editor flow."),
          ("9598c7_901a08b5692f46f2892e765abe72fd5e~mv2.png", "Marketo Landing Page Editor", "Template selection."),
          ("9598c7_6ff029b6856b4c81a3ba9e25dfb97ec5~mv2.png", "Marketo Landing Page Editor", "Main view empty state."),
          ("9598c7_7b0ffadb55fc44378c0d6f759fa89e16~mv2.png", "Marketo Landing Page Editor", "Element selection on left rail."),
          ("9598c7_9630a88d7bf1427c82835a38cae2b89c~mv2.png", "Marketo Landing Page Editor", "Asset selection in left rail."),
          ("9598c7_3ac706b5978c44cbb84d3f2790f6b5dd~mv2.png", "Marketo Landing Page Editor", "Main view"),
          ("9598c7_384d8efae3f948afac3e403f9eb117cb~mv2.png", "Marketo Landing Page Editor", "Breakpoint editor."),
          ("9598c7_e3a3d1961a354737a6f978545f5347a6~mv2.png", "Marketo Landing Page Editor", "Element selection on canvas."),
          ("9598c7_c1f1d6d7e92b453ab57e8bfd466f3eec~mv2.png", "Marketo Landing Page Editor", "Editor history."),
      ])}
      <h3>Form Editor</h3>
      {study_show(lib, [
          ("9598c7_f084a418de834a9d998c0c42b0cce262~mv2.png", "Marketo Form Editor", "Form editor full flow."),
          ("9598c7_980f955769c747d7aa08cbea6d01ea49~mv2.png", "Marketo Form Editor", "Template selection."),
          ("9598c7_4958e02addd94bbfa73963fffd9c29f4~mv2.png", "Marketo Form Editor", "Main view empty state."),
          ("9598c7_444b755d655149f8861049482ec5ac74~mv2.png", "Marketo Form Editor", "Main view with form elements."),
          ("9598c7_f47020d812674777bd41a95b0381baca~mv2.png", "Marketo Form Editor", "Moving elements around in the left rail via drag and drop."),
          ("9598c7_4bd8cc68a6bc4c908a63ac87a94a2f7d~mv2.png", "Marketo Form Editor", "Publish settings."),
          ("9598c7_16af54c930084ed69a9596e6792fa95e~mv2.png", "Marketo Form Editor", "Editor history."),
      ])}
      <h2>The Outcome</h2>
      <p>The editors were fully implemented after I transitioned out of Adobe. Early user testing results, however, were strongly positive. Users responded well to the improved structure, cleaner interface, and alignment with the Adobe ecosystem they were increasingly working within.</p>
      <p>This project was one of the most complex cross-functional design challenges of my career. No single team owned the full problem, stakeholders spanned multiple product orgs, and the constraints were real. Navigating all of that while keeping user needs at the center is what I'm most proud of.</p>
        """, soft=True),
        "View Product Design",
        "/product-design",
    )

    pages = {
        ROOT / "index.html": chrome(
            "Home | Dustin Brentz",
            "Dustin Brentz is a design leader and versatile creative with 15+ years across product design, graphic design, gaming, and animation.",
            "/",
            "home",
            home,
        ),
        ROOT / "product-design/index.html": chrome(
            "Product Design | Dustin Brentz",
            "Product design work by Dustin Brentz, including Brightidea, Adobe/Marketo, Weedmaps, Fusion of Ideas, and Scareproof.",
            "/product-design",
            "product",
            product_page,
        ),
        ROOT / "graphic-design/index.html": chrome(
            "Graphic Design | Dustin Brentz",
            "Graphic design work by Dustin Brentz, including The Dabbing Specialist, Fusion of Ideas, New Leaf Insurance, and freelance projects.",
            "/graphic-design",
            "graphic",
            graphic_page,
        ),
        ROOT / "brightidea-whiteboard-case-study/index.html": chrome(
            "Brightidea Whiteboard Case Study | Dustin Brentz",
            "Case study of the Brightidea Whiteboard AI project by Dustin Brentz, senior product designer.",
            "/brightidea-whiteboard-case-study",
            "",
            whiteboard_page,
        ),
        ROOT / "marketo-editors-case-study/index.html": chrome(
            "Marketo Editors Case Study | Dustin Brentz",
            "Case study of the Marketo email, landing page, and form editors by Dustin Brentz.",
            "/marketo-editors-case-study",
            "",
            marketo_page,
        ),
    }

    lib.download()
    fetch(
        "https://www.dustinbrentz.com/_files/ugd/9598c7_1bf5117a75624b198027a940bb67287f.pdf",
        ROOT / "resume.pdf",
    )
    download_videos(videos)

    for path, markup in pages.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markup)
        print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
