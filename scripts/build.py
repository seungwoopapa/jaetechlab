#!/usr/bin/env python3
"""content/posts.json + templates 로 site/ 정적 사이트를 생성한다.

생성물: 홈, 카테고리 6개, 연도별 아카이브, 글 35편, 소개·문의·개인정보처리방침·면책 고지,
404, sitemap.xml, robots.txt, feed.xml, CNAME, ads.txt(설정 시).
"""
import html
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs"
CONF = json.load(open(ROOT / "config.json"))
POSTS = json.load(open(ROOT / "content" / "posts.json"))
PAGES_DIR = ROOT / "pages"

CATS = [("stock-invest", "주식투자"), ("loan", "대출"), ("real-estate", "부동산"),
        ("tax", "세금"), ("book-review", "도서리뷰"), ("etc", "기타")]
CAT_DESC = {
    "stock-invest": "ETF, 공모주, 해외주식, 자산배분 등 주식투자의 기초 개념과 실전 방법을 정리한 글입니다.",
    "loan": "정부지원대출, 전세대출, 주택담보대출, 상환 방식 등 대출 상품과 조건을 비교한 글입니다.",
    "real-estate": "부동산 대책, 청약통장, 무주택자 기준 등 내 집 마련과 관련된 제도를 정리한 글입니다.",
    "tax": "주식 양도세 등 투자와 관련된 세금 제도를 정리한 글입니다.",
    "book-review": "재테크와 자기계발 도서를 읽고 핵심을 요약한 리뷰입니다.",
    "etc": "금 투자, 군적금 등 한 갈래로 묶기 어려운 재테크 정보입니다.",
}
SLUGS = {p["slug"] for p in POSTS}
YEAR = str(date.today().year)


def esc(s):
    return html.escape(s, quote=True)


def kdate(iso):
    if not iso:
        return ""
    y, m, d = iso.split("-")
    return f"{y}년 {int(m)}월 {int(d)}일"


def url_for(path):
    return CONF["base_url"].rstrip("/") + path


# ---------- 레이아웃 ----------
def layout(title, body, *, description="", path="/", og_type="website", og_image="", jsonld=None, noindex=False):
    full_title = CONF["site_name"] if path == "/" else f"{title} | {CONF['site_name']}"
    nav = ""
    for slug, name in CATS:
        cur = ' aria-current="page"' if path.startswith(f"/category/{slug}/") else ""
        nav += f'<li><a href="/category/{slug}/"{cur}>{name}</a></li>'
    adsense = ""
    if CONF.get("adsense_client"):
        adsense = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={CONF["adsense_client"]}" '
                   f'crossorigin="anonymous"></script>')
    ld = f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ""
    og_image = og_image or "/images/og-default.png"
    home_cur = ' aria-current="page"' if path == "/" else ""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description or CONF['tagline'])}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<link rel="canonical" href="{esc(url_for(path))}">
<link rel="alternate" type="application/rss+xml" title="{esc(CONF['site_name'])}" href="/feed.xml">
<meta property="og:site_name" content="{esc(CONF['site_name'])}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description or CONF['tagline'])}">
<meta property="og:url" content="{esc(url_for(path))}">
<meta property="og:image" content="{esc(url_for(og_image))}">
<meta property="og:locale" content="ko_KR">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/style.css">
{adsense}
{ld}
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/"><span class="brand-mark">₩</span> {esc(CONF['site_name'])}</a>
    <p class="tagline">{esc(CONF['tagline'])}</p>
    <nav class="nav" aria-label="주요 메뉴">
      <ul>
        <li><a href="/"{home_cur}>홈</a></li>
        {nav}
        <li><a href="/archive/">연도별</a></li>
        <li><a href="/about/">소개</a></li>
        <li><a href="/contact/">문의</a></li>
      </ul>
    </nav>
  </div>
</header>
<main class="wrap">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <nav aria-label="사이트 정보">
      <a href="/about/">소개</a> · <a href="/contact/">문의</a> · <a href="/privacy/">개인정보처리방침</a> · <a href="/disclaimer/">면책 고지</a> · <a href="/archive/">전체 글</a> · <a href="/feed.xml">RSS</a>
    </nav>
    <p>© 2020–{YEAR} {esc(CONF['site_name'])}. 이 사이트의 글은 작성자의 개인적인 공부와 경험을 정리한 것으로, 특정 금융상품의 매수·매도를 권유하지 않습니다.</p>
  </div>
</footer>
</body>
</html>
"""


# ---------- 본문 후처리 ----------
def fix_body(body):
    existing = {p.name for p in (SITE / "images").glob("*")} if (SITE / "images").exists() else set()

    def img_ok(tag):
        m = re.search(r'src="/images/([^"]+)"', tag)
        return bool(m) and m.group(1) in existing

    # 파일이 없는 이미지는 figure 째로 제거, 있으면 lazy 로딩 붙임
    def fig(m):
        block = m.group(0)
        imgs = re.findall(r"<img\b[^>]*>", block)
        if imgs and not any(img_ok(i) for i in imgs):
            return ""
        return block
    body = re.sub(r"<figure\b[^>]*>.*?</figure>", fig, body, flags=re.S)
    body = re.sub(r"<img\b[^>]*>", lambda m: (m.group(0)[:-1].rstrip("/") + ' loading="lazy">') if img_ok(m.group(0)) else "", body)
    # 없는 내부 글 링크는 텍스트만 남긴다
    def link(m):
        href = m.group(1)
        if href.startswith("/") and not href.startswith("/images/"):
            slug = href.strip("/").split("#")[0]
            if slug and slug not in SLUGS and not slug.startswith("category/"):
                return m.group(2)
        return m.group(0)
    body = re.sub(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', link, body, flags=re.S)
    # <p><div> 같은 잘못된 중첩 정리
    body = body.replace("<p><div>", "<div>").replace("</div></p>", "</div>")
    for _ in range(3):
        body = re.sub(r"<(div|p|figure)>\s*</\1>", "", body)
    return body


def post_card(p):
    thumb = f'<img src="{p["featured"]}" alt="" loading="lazy">' if p.get("featured_ok") else '<span class="thumb-placeholder">₩</span>'
    return f"""<li class="card">
  <a class="card-thumb" href="/{esc(p['slug'])}/">{thumb}</a>
  <div class="card-body">
    <div class="meta"><a class="cat" href="/category/{p['category_slug']}/">{p['category']}</a><time datetime="{p['published']}">{kdate(p['published'])}</time></div>
    <h3><a href="/{esc(p['slug'])}/">{esc(p['title'])}</a></h3>
    <p>{esc(p['description'][:110])}{'…' if len(p['description']) > 110 else ''}</p>
  </div>
</li>"""


def post_list(posts):
    return '<ul class="cards">' + "".join(post_card(p) for p in posts) + "</ul>"


# ---------- 페이지 생성 ----------
def write(path, content):
    out = SITE / path.strip("/") / "index.html" if path.endswith("/") else SITE / path.strip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def build_post(i, p):
    prev_p = POSTS[i - 1] if i > 0 else None
    next_p = POSTS[i + 1] if i + 1 < len(POSTS) else None
    related = [q for q in POSTS if q["category_slug"] == p["category_slug"] and q["slug"] != p["slug"]]
    related = sorted(related, key=lambda q: abs((datetime.fromisoformat(q["published"]) - datetime.fromisoformat(p["published"])).days))[:3]
    notice = (f'<aside class="notice"><strong>작성일 {kdate(p["published"])}</strong>'
              + (f' · 최종 수정 {kdate(p["modified"])}' if p["modified"] and p["modified"] != p["published"] else "")
              + f'<br>이 글의 금융 제도·금리·한도·수치는 <b>{p["published"][:4]}년 작성 시점 기준</b>입니다. 현재 기준과 다를 수 있으니 실제 결정 전에는 해당 기관의 최신 안내를 확인해 주세요.</aside>')
    nav = '<nav class="post-nav" aria-label="이전·다음 글">'
    nav += f'<a class="prev" href="/{esc(prev_p["slug"])}/"><small>이전 글</small>{esc(prev_p["title"])}</a>' if prev_p else "<span></span>"
    nav += f'<a class="next" href="/{esc(next_p["slug"])}/"><small>다음 글</small>{esc(next_p["title"])}</a>' if next_p else "<span></span>"
    nav += "</nav>"
    rel = ""
    if related:
        rel = '<section class="related"><h2>같은 카테고리의 다른 글</h2>' + post_list(related) + "</section>"
    body = f"""<article class="post">
  <header class="post-header">
    <div class="meta"><a class="cat" href="/category/{p['category_slug']}/">{p['category']}</a><time datetime="{p['published']}">{kdate(p['published'])}</time></div>
    <h1>{esc(p['title'])}</h1>
  </header>
  {notice}
  <div class="post-body">
{fix_body(p['body'])}
  </div>
  <footer class="post-footer">
    <p>이 글은 {CONF['site_name']} 운영자가 직접 공부하며 정리한 내용입니다. 투자·대출 결정의 책임은 본인에게 있으며, 자세한 내용은 <a href="/disclaimer/">면책 고지</a>를 참고해 주세요.</p>
  </footer>
</article>
{nav}
{rel}"""
    jsonld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": p["title"], "description": p["description"],
        "datePublished": p["published"], "dateModified": p["modified"] or p["published"],
        "author": {"@type": "Person", "name": CONF["author"]},
        "publisher": {"@type": "Organization", "name": CONF["site_name"]},
        "mainEntityOfPage": url_for(f"/{p['slug']}/"),
        "articleSection": p["category"],
    }
    if p.get("featured_ok"):
        jsonld["image"] = url_for(p["featured"])
    write(f"/{p['slug']}/", layout(p["title"], body, description=p["description"], path=f"/{p['slug']}/",
                                    og_type="article", og_image=p["featured"] if p.get("featured_ok") else "", jsonld=jsonld))


def build_home():
    latest = sorted(POSTS, key=lambda p: p["published"], reverse=True)
    cat_chips = "".join(
        f'<a class="chip" href="/category/{slug}/">{name} <span>{sum(1 for p in POSTS if p["category_slug"] == slug)}</span></a>'
        for slug, name in CATS)
    intro = (PAGES_DIR / "home-intro.html").read_text(encoding="utf-8")
    body = f"""<section class="hero">
{intro}
<div class="chips">{cat_chips}</div>
</section>
<section>
<h2 class="section-title">전체 글 <small>{len(POSTS)}편 · 최신순</small></h2>
{post_list(latest)}
</section>"""
    jsonld = {"@context": "https://schema.org", "@type": "WebSite", "name": CONF["site_name"], "url": CONF["base_url"],
              "description": CONF["tagline"]}
    write("/", layout(CONF["site_name"], body, description=CONF["tagline"], path="/", jsonld=jsonld))


def build_categories():
    for slug, name in CATS:
        posts = sorted([p for p in POSTS if p["category_slug"] == slug], key=lambda p: p["published"], reverse=True)
        body = f"""<section class="archive-head"><h1>{name}</h1><p>{CAT_DESC[slug]} 총 {len(posts)}편.</p></section>
{post_list(posts)}"""
        write(f"/category/{slug}/", layout(name, body, description=CAT_DESC[slug], path=f"/category/{slug}/"))


def build_archive():
    years = sorted({p["published"][:4] for p in POSTS}, reverse=True)
    sections = ""
    for y in years:
        posts = sorted([p for p in POSTS if p["published"].startswith(y)], key=lambda p: p["published"], reverse=True)
        items = "".join(f'<li><time datetime="{p["published"]}">{p["published"]}</time> <a href="/{esc(p["slug"])}/">{esc(p["title"])}</a> <span class="cat-inline">{p["category"]}</span></li>' for p in posts)
        sections += f'<section class="year"><h2 id="y{y}">{y}년 <small>{len(posts)}편</small></h2><ul class="plain-list">{items}</ul></section>'
        ybody = f'<section class="archive-head"><h1>{y}년에 쓴 글</h1><p>총 {len(posts)}편. 모든 글은 작성 당시의 제도와 수치를 기준으로 합니다.</p></section>{post_list(posts)}'
        write(f"/archive/{y}/", layout(f"{y}년 글", ybody, description=f"{CONF['site_name']}의 {y}년 글 {len(posts)}편", path=f"/archive/{y}/"))
    yearnav = " · ".join(f'<a href="/archive/{y}/">{y}년</a>' for y in years)
    body = f'<section class="archive-head"><h1>전체 글 목록</h1><p>연도별로 정리한 글 {len(POSTS)}편입니다. {yearnav}</p></section>{sections}'
    write("/archive/", layout("전체 글 목록", body, description=f"{CONF['site_name']}의 전체 글을 연도별로 정리했습니다.", path="/archive/"))


def build_pages():
    for page in ["about", "contact", "privacy", "disclaimer"]:
        raw = (PAGES_DIR / f"{page}.html").read_text(encoding="utf-8")
        raw = raw.replace("{{email}}", CONF["contact_email"]).replace("{{site_name}}", CONF["site_name"]) \
                 .replace("{{base_url}}", CONF["base_url"]).replace("{{today}}", date.today().isoformat()) \
                 .replace("{{post_count}}", str(len(POSTS)))
        title = re.search(r"<h1>(.*?)</h1>", raw).group(1)
        desc = re.sub(r"<[^>]+>", "", re.search(r"<p>(.*?)</p>", raw, re.S).group(1)).strip()[:150]
        write(f"/{page}/", layout(title, f'<article class="page">{raw}</article>', description=desc, path=f"/{page}/"))
    body = '<article class="page"><h1>페이지를 찾을 수 없습니다</h1><p>주소가 바뀌었거나 삭제된 글입니다. <a href="/">홈</a>이나 <a href="/archive/">전체 글 목록</a>에서 찾아보세요.</p></article>'
    (SITE / "404.html").write_text(layout("페이지를 찾을 수 없습니다", body, path="/404.html", noindex=True), encoding="utf-8")


def build_meta():
    urls = ["/", "/about/", "/contact/", "/privacy/", "/disclaimer/", "/archive/"]
    urls += [f"/category/{s}/" for s, _ in CATS]
    urls += [f"/archive/{y}/" for y in sorted({p["published"][:4] for p in POSTS})]
    today = date.today().isoformat()
    entries = "".join(f"<url><loc>{esc(url_for(u))}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    entries += "".join(f"<url><loc>{esc(url_for('/' + p['slug'] + '/'))}</loc><lastmod>{p['modified'] or p['published']}</lastmod></url>" for p in POSTS)
    (SITE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>', encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {url_for('/sitemap.xml')}\n", encoding="utf-8")
    (SITE / "CNAME").write_text(CONF["domain"], encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    if CONF.get("adsense_client"):
        pub = CONF["adsense_client"].replace("ca-", "")
        (SITE / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    items = ""
    for p in sorted(POSTS, key=lambda p: p["published"], reverse=True):
        pub = datetime.fromisoformat(p["published"]).replace(tzinfo=timezone.utc).strftime("%a, %d %b %Y 00:00:00 +0000")
        items += f"<item><title>{esc(p['title'])}</title><link>{esc(url_for('/' + p['slug'] + '/'))}</link><guid>{esc(url_for('/' + p['slug'] + '/'))}</guid><pubDate>{pub}</pubDate><category>{p['category']}</category><description>{esc(p['description'])}</description></item>"
    (SITE / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(CONF["site_name"])}</title><link>{CONF["base_url"]}</link><description>{esc(CONF["tagline"])}</description><language>ko</language>{items}</channel></rss>', encoding="utf-8")


def main():
    # 이미지 폴더는 유지하고 나머지 생성물만 새로 만든다
    for child in SITE.iterdir() if SITE.exists() else []:
        if child.name != "images":
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    SITE.mkdir(exist_ok=True)
    shutil.copy(ROOT / "static" / "style.css", SITE / "style.css")
    shutil.copy(ROOT / "static" / "favicon.svg", SITE / "favicon.svg")
    (SITE / "images").mkdir(exist_ok=True)
    shutil.copy(ROOT / "static" / "og-default.png", SITE / "images" / "og-default.png")
    existing = {p.name for p in (SITE / "images").glob("*")}
    for p in POSTS:
        p["featured_ok"] = bool(p["featured"]) and p["featured"].split("/")[-1] in existing
    for i, p in enumerate(POSTS):
        build_post(i, p)
    build_home()
    build_categories()
    build_archive()
    build_pages()
    build_meta()
    n_html = sum(1 for _ in SITE.rglob("*.html"))
    n_img = sum(1 for _ in (SITE / "images").glob("*"))
    print(f"built: {n_html} html pages, {n_img} images, featured ok: {sum(p['featured_ok'] for p in POSTS)}/{len(POSTS)}")


if __name__ == "__main__":
    main()
