# jaetechlab.com 복원 사이트 (머니 가이드)

web.archive.org 에 남아 있던 옛 워드프레스 블로그 "재테크 공부하는 남자 / 머니 가이드"의 글 35편을 뽑아
정적 사이트로 다시 조립한 저장소입니다. GitHub Pages 가 `main` 브랜치의 `docs/` 폴더를 서빙합니다.

## 구조

```
config.json            사이트명·도메인·연락 이메일·애드센스 클라이언트 ID
raw/                   아카이브에서 받은 원본 HTML(all_html.json)과 CDX 목록 — 재추출용
content/posts.json     추출된 글 35편 (제목·작성일·카테고리·본문 HTML·이미지 매핑)
content/images.json    원본 이미지 URL -> 로컬 파일명
pages/                 소개·문의·개인정보처리방침·면책 고지·홈 소개글 (직접 수정 가능)
static/                CSS, 파비콘, 기본 OG 이미지
scripts/extract.py     raw -> content/posts.json
scripts/fetch_images.py content/images.json -> docs/images/ (웨이백에서 순차 다운로드)
scripts/build.py       content + pages + static -> docs/ (전체 HTML, sitemap, robots, feed, CNAME, ads.txt)
docs/                  배포 산출물 (GitHub Pages 가 서빙)
```

## 다시 만들기

파이썬 3 표준 라이브러리만 씁니다. 외부 패키지 없음.

```bash
python3 scripts/extract.py        # 글 재추출 (raw/ 가 있을 때만 필요)
python3 scripts/fetch_images.py   # 아직 못 받은 이미지 재시도 (받은 건 건너뜀)
python3 scripts/build.py          # docs/ 재생성
```

글 하나를 고치려면 `content/posts.json` 의 해당 항목 `body` 를 고친 뒤 `build.py` 만 다시 돌리면 됩니다.
소개·문의 등 고정 페이지는 `pages/*.html` 을 고칩니다. `{{email}}`, `{{site_name}}`, `{{today}}` 자리표시자가 치환됩니다.

## 배포

`docs/` 를 커밋해서 `main` 에 푸시하면 GitHub Pages 가 1~2분 안에 반영합니다.

```bash
python3 scripts/build.py && git add -A && git commit -m "update" && git push
```

도메인 연결·애드센스·서치콘솔 절차는 [안내서.md](안내서.md) 를 보세요.

## 내용에 대한 원칙

- 글 본문은 아카이브 원문 그대로입니다. 공유 버튼·광고 코드·목차 플러그인·lazy-load 껍데기만 걷어냈습니다.
- 모든 글 상단에 원래 작성일과 "작성 시점 기준" 안내를 넣었습니다. 낡은 수치를 본문에서 고치지는 않았습니다.
- 아카이브에 없는 이미지는 `<figure>` 째로 뺐습니다. 깨진 이미지는 없습니다.
- 카테고리는 옛 사이트의 목록 페이지에서 역으로 복원했습니다. 2023년 "머니 가이드" 시절의 신용대출·주택담보·전세자금·유용한 정보는 모두 "대출"로 합쳤습니다.
