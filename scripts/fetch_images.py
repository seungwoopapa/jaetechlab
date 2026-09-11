#!/usr/bin/env python3
"""content/images.json 의 원본 이미지 URL을 웨이백에서 순차로 받아 site/images/ 에 저장한다.

- 아카이브는 병렬 요청을 막으므로 한 번에 하나씩, 요청 사이 1초 쉰다.
- 정확한 URL 스냅샷이 없으면 크기 접미사(-1024x576)를 뗀 원본으로 재시도한다.
- 결과는 content/images_status.json 에 남긴다. 이미 받은 파일은 건너뛴다.
"""
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
images = json.load(open(ROOT / "content" / "images.json"))
status_path = ROOT / "content" / "images_status.json"
status = json.load(open(status_path)) if status_path.exists() else {}

cdx = {}
for ts, url, *_ in json.load(open(ROOT / "raw" / "cdx_img.json"))[1:]:
    key = urllib.parse.unquote(url).lower().replace("http://", "").replace("https://", "").replace("www.", "")
    cdx.setdefault(key, ts)


def key_of(url):
    return urllib.parse.unquote(url).lower().replace("http://", "").replace("https://", "").replace("www.", "")


def encoded(url):
    """한글 파일명은 퍼센트 인코딩해야 웨이백이 받아 준다."""
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(urllib.parse.unquote(parts.path))))


def fetch(url):
    ts = cdx.get(key_of(url), "2")
    req = urllib.request.Request(f"https://web.archive.org/web/{ts}im_/{encoded(url)}",
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
        ctype = r.headers.get("Content-Type", "")
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    if not ctype.startswith("image/") or len(data) < 100:
        raise ValueError(f"not an image: {ctype} {len(data)}B")
    return data


for i, (url, name) in enumerate(images.items(), 1):
    dest = OUT / name
    if dest.exists() and status.get(url) == "ok":
        continue
    candidates = [url]
    stripped = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", url)
    if stripped != url:
        candidates.append(stripped)
    # 같은 파일의 다른 크기가 아카이브에 있으면 그것도 후보 (큰 것부터)
    stem = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", key_of(url))
    alts = [k for k in cdx if re.sub(r"-\d+x\d+(\.\w+)$", r"\1", k) == stem and k != key_of(url) and k != key_of(stripped)]
    alts.sort(key=lambda k: -int((re.findall(r"-(\d+)x\d+\.", k) or ["99999"])[0]))
    candidates += ["https://" + k for k in alts]
    result = "missing"
    for cand in candidates:
        for attempt in range(3):
            try:
                dest.write_bytes(fetch(cand))
                result = "ok"
                break
            except Exception as e:  # noqa: BLE001
                err = str(e)
                if "429" in err or "refused" in err:
                    time.sleep(15 * (attempt + 1))
                elif "404" in err:
                    break
                else:
                    time.sleep(2)
        if result == "ok":
            break
    status[url] = result if result == "ok" else f"missing: {err[:80]}"
    json.dump(status, open(status_path, "w"), ensure_ascii=False, indent=1)
    print(f"[{i}/{len(images)}] {result:7s} {name}  {urllib.parse.unquote(url)[-60:]}", flush=True)
    time.sleep(1)

ok = sum(1 for v in status.values() if v == "ok")
print(f"done: ok={ok} missing={len(status) - ok} total={len(images)}")
