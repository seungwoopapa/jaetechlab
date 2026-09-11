#!/usr/bin/env python3
"""아카이브(raw/all_html.json)에서 글 35편을 뽑아 content/posts.json 으로 저장한다.

- 제목, 작성일, 수정일, 카테고리, 요약, 본문 HTML, 대표 이미지, 본문 이미지 목록
- 본문은 공유 버튼·스크립트·광고·목차 플러그인·lazy-load 껍데기를 제거하고 정리한다.
- 이미지 다운로드는 fetch_images.py 가 따로 한다.
"""
import hashlib
import html
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = json.load(open(ROOT / "raw" / "all_html.json"))
ROWS = json.load(open(ROOT / "raw" / "cdx_rows.json"))

CAT_NAME = {"stock-invest": "주식투자", "loan": "대출", "real-estate": "부동산",
            "tax": "세금", "book-review": "도서리뷰", "etc": "기타"}
# 옛 사이트 카테고리 목록 페이지 -> 통합 카테고리. 나중 시기(머니 가이드) 페이지가 우선한다.
LISTING_CAT = {"/category/stock-invest/": "stock-invest", "/category/stock-invest/page/2/": "stock-invest",
               "/stock-invest/": "stock-invest", "/stock-invest/page/2/": "stock-invest",
               "/category/loan/": "loan", "/loan/": "loan", "/credit/": "loan", "/mortgage/": "loan",
               "/rent/": "loan", "/tip/": "loan",
               "/category/real-estate/": "real-estate", "/real-estate/": "real-estate",
               "/category/tax/": "tax", "/tax/": "tax",
               "/category/book-review/": "book-review", "/book-review/": "book-review",
               "/category/etc/": "etc", "/etc/": "etc"}
# 목록 페이지에 안 잡힌 글
MANUAL_CAT = {"키움증권-계좌-개설": "stock-invest", "키움증권-계좌-이체": "stock-invest",
              "해외주식-사는법": "stock-invest", "키움증권-계좌-개설-이벤트": "stock-invest",
              "군적금-매칭지원금-수령": "etc", "p2p-대출이란": "loan"}
IMG_DIR = "images"


def build_category_map():
    cat = {}
    for url, doc in RAW.items():
        path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
        if path not in LISTING_CAT:
            continue
        for l in re.findall(r'<(?:h1|h2|h3)[^>]*entry-title[^>]*>\s*<a[^>]*href="([^"]+)"', doc):
            slug = urllib.parse.unquote(urllib.parse.urlparse(l).path).strip("/")
            cat.setdefault(slug, LISTING_CAT[path])
    cat.update(MANUAL_CAT)
    return cat


CATEGORY_OF = build_category_map()


def local_image_name(url: str) -> str:
    ext = (re.findall(r"\.(jpe?g|png|gif|webp|svg)$", url.split("?")[0], re.I) or ["jpg"])[0].lower()
    return f"{hashlib.md5(url.encode()).hexdigest()[:12]}.{ext}"


def balanced_div(src: str, start: int) -> str:
    """start 위치의 <div ...> 부터 짝이 맞는 </div> 까지 내부 HTML을 돌려준다."""
    depth = 0
    for m in re.finditer(r"<div\b[^>]*>|</div>", src[start:]):
        depth += 1 if m.group().startswith("<div") else -1
        if depth == 0:
            inner_start = start + src[start:].find(">") + 1
            return src[inner_start:start + m.start()]
    return src[start:]


def strip_block(body: str, open_pat: str) -> str:
    """open_pat 로 시작하는 <div> 블록을 짝 맞춰 통째로 제거한다."""
    while True:
        m = re.search(open_pat, body)
        if not m:
            return body
        inner = balanced_div(body, m.start())
        end = body.find(inner, m.start()) + len(inner) + len("</div>")
        body = body[:m.start()] + body[end:]


ATTR_DROP = re.compile(r"""\s(?:class|style|data-[\w-]+|aria-[\w-]+|role|itemprop|itemscope|itemtype|title)=(?:"[^"]*"|'[^']*')""")


def clean_body(body: str) -> str:
    # 플러그인 블록 제거: 연관 포스트, 광고 코드 블록, 목차(easy-table-of-contents)
    body = strip_block(body, r'<div[^>]*class="relpost-thumb-wrapper"[^>]*>')
    body = strip_block(body, r"""<div[^>]*class=(?:"|')code-block[^"']*(?:"|')[^>]*>""")
    body = strip_block(body, r"""<div[^>]*(?:id|class)=(?:"|')[^"']*ez-toc-container[^"']*(?:"|')[^>]*>""")
    # lazy-load: data-lazy-src 를 src 로 승격, svg 플레이스홀더·srcset 제거
    body = re.sub(r"<noscript>.*?</noscript>", "", body, flags=re.S)
    body = re.sub(r'src="data:image/svg\+xml[^"]*"', "", body)
    body = body.replace("data-lazy-src=", "src=")
    body = re.sub(r'\s(?:data-lazy-srcset|data-lazy-sizes|srcset|sizes|loading|decoding|fetchpriority)="[^"]*"', "", body)
    # <picture><source> 는 img 만 남긴다
    body = re.sub(r"<source\b[^>]*>", "", body)
    body = re.sub(r"</?picture[^>]*>", "", body)
    # 스크립트·스타일·광고·공유 버튼·iframe·svg·폼 요소 제거
    body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)
    body = re.sub(r"<svg\b.*?</svg>", "", body, flags=re.S)
    body = re.sub(r"<ins\b[^>]*adsbygoogle.*?</ins>", "", body, flags=re.S)
    body = re.sub(r'<div class="simplesocialbuttons.*?</div>\s*', "", body, flags=re.S)
    body = re.sub(r"<iframe\b.*?</iframe>", "", body, flags=re.S)
    body = re.sub(r"<(?:input|label)\b[^>]*>|</label>", "", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    # 속성 정리: id 와 표 관련 class 만 남긴다
    body = ATTR_DROP.sub(lambda m: m.group() if "wp-block-table" in m.group() else "", body)
    body = re.sub(r'\srel="[^"]*"', "", body)
    body = body.replace(' target="_blank"', ' target="_blank" rel="noopener"')
    # 빈 요소 정리 (반복)
    for _ in range(6):
        body = re.sub(r"<(div|p|span|figure|strong|em|a)>(?:\s|&nbsp;|<br\s*/?>)*</\1>", "", body)
        body = re.sub(r"<div>\s*</div>", "", body)
    body = re.sub(r"<p>\s*<br\s*/?>\s*</p>", "", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def extract(url: str, doc: str, ts: str):
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    slug = path.strip("/")
    title = html.unescape((re.findall(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h1>', doc, re.S) or [""])[0])
    title = re.sub(r"<[^>]+>", "", title).strip()
    if not title:
        t = (re.findall(r'<meta property="og:title" content="([^"]+)"', doc) or [""])[0]
        title = re.split(r" [-|] ", html.unescape(t))[0].strip()
    title = re.sub(r"\s+", " ", title)
    published = (re.findall(r'article:published_time" content="([^"]+)"', doc) or [""])[0]
    modified = (re.findall(r'article:modified_time" content="([^"]+)"', doc) or [""])[0]
    description = html.unescape((re.findall(r'<meta name="description" content="([^"]*)"', doc) or [""])[0])
    featured = (re.findall(r'<meta property="og:image" content="([^"]+)"', doc) or [""])[0]
    cat_slug = CATEGORY_OF.get(slug, "etc")

    m = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>', doc)
    body = clean_body(balanced_div(doc, m.start())) if m else ""
    images = sorted(set(re.findall(r'<img[^>]+src="(https?://[^"]+)"', body)))
    if featured:
        images.append(featured)
    image_map = {u: local_image_name(u) for u in images}
    for u, name in image_map.items():
        body = body.replace(f'src="{u}"', f'src="/{IMG_DIR}/{name}"')
    # 내부 링크는 같은 slug 를 유지하므로 상대 경로로 바꾼다
    body = re.sub(r'href="https?://(?:www\.)?jaetechlab\.com/([^"]*)"',
                  lambda m: 'href="/' + urllib.parse.unquote(m.group(1)) + '"', body)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()
    return {
        "slug": slug, "original_url": f"https://jaetechlab.com{path}", "archive_ts": ts,
        "title": title, "published": published[:10], "modified": modified[:10],
        "category": CAT_NAME[cat_slug], "category_slug": cat_slug,
        "description": description, "featured": f"/{IMG_DIR}/{image_map[featured]}" if featured else "",
        "images": image_map,
        "chars": len(text), "body": body,
    }


posts = []
for ts, url, *_ in ROWS:
    doc = RAW.get(url, "")
    if 'og:type" content="article"' not in doc or "single-post" not in doc:
        continue
    posts.append(extract(url, doc, ts))

posts.sort(key=lambda p: p["published"])
out = ROOT / "content"
out.mkdir(exist_ok=True)
json.dump(posts, open(out / "posts.json", "w"), ensure_ascii=False, indent=1)
all_images = {}
for p in posts:
    all_images.update(p["images"])
json.dump(all_images, open(out / "images.json", "w"), ensure_ascii=False, indent=1)
print(f"posts: {len(posts)}  chars: {sum(p['chars'] for p in posts)}  images: {len(all_images)}")
for p in posts:
    print(f"  {p['published']}  {p['category']:5s} {p['chars']:5d}자 img{len(p['images']):2d}  {p['title'][:45]}")
