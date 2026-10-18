"""
data/posts.json(블로그 원문) + data/content.json(편집 데이터)로 홈페이지 전체를 dist/ 에 만듭니다.

사용법:  python scripts/build.py
결과:    dist/  ← 이 폴더 안의 내용 전체를 FileZilla로 서버 최상위 폴더에 올립니다.

페이지 구성 (레퍼런스: luckyrepair.co.kr)
  /                      메인
  /service/<분야>/        작업분야 8개
  /portfolio/            시공사례 전체
  /portfolio/<글번호>/    시공사례 1건 (블로그 글 1편)
  /area/                 출장지역 전체
  /area/<지역>/           지역별 기록 (사례 2건 이상인 지역만)
  /area/<지역>/<분야>/     지역+분야 (사례 2건 이상인 조합만 — 얇은 페이지는 만들지 않음)
  /contact/              상담 안내
"""
import html
import json
import re
import shutil
import sys
from urllib.parse import quote

from PIL import Image
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_facts import crew_hours, quotes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA, DIST, STATIC = ROOT / "data", ROOT / "dist", ROOT / "static"
MIN_PAGE = 2   # 지역·지역+분야 페이지를 만드는 최소 사례 수
TODAY = "2026-10-16"          # 이번 빌드 날짜 (사이트맵 lastmod)
FREEZE_UNTIL = "2026-11-01"   # 이 날짜 전까지 기존 페이지의 title·description은 baseline 그대로 유지

C = json.loads((DATA / "content.json").read_text(encoding="utf-8"))
RAW = {p["logNo"]: p for p in json.loads((DATA / "posts.json").read_text(encoding="utf-8"))["posts"]}
# 같은 대표의 두 번째 블로그(사진·사실만 사용, 블로그 링크·이름은 쓰지 않음)
RAW.update({p["logNo"]: p for p in json.loads((DATA / "posts_donyotti.json").read_text(encoding="utf-8"))["posts"]})
NEW_CASES = [x for f in sorted(DATA.glob("new_cases_*.json")) for x in json.loads(f.read_text(encoding="utf-8"))]
STORIES = {}
for _f in sorted(DATA.glob("old_story_*.json")):
    STORIES.update(json.loads(_f.read_text(encoding="utf-8")))
EXTRA = {}   # 사례별 '작업 후 달라진 점'·'맡기기 전에 확인할 점' (블로그 후기·체크포인트를 새로 쓴 것)
for _f in sorted(DATA.glob("extra_*.json")):
    EXTRA.update(json.loads(_f.read_text(encoding="utf-8")))
POINTS = {}  # 사례별 '이 현장의 작업 포인트' (블로그의 자재·순서 설명을 새로 쓴 것)
for _f in sorted(DATA.glob("point_*.json")):
    POINTS.update(json.loads(_f.read_text(encoding="utf-8")))
BASELINE = json.loads((DATA / "baseline_2026-10-16.json").read_text(encoding="utf-8"))
ABOUT = json.loads((DATA / "about.json").read_text(encoding="utf-8"))
OUT = json.loads((DATA / "outreach.json").read_text(encoding="utf-8"))
BANNERS = set(json.loads((DATA / "banners.json").read_text(encoding="utf-8")))
S = C["site"]
BASE = S["baseUrl"].rstrip("/")
PHONE, TEL = S["phone"], S["phone"].replace("-", "")
SVC = {s["key"]: s for s in C["services"]}
REG = C["regions"]
e = html.escape


# ───────────────────────── 데이터 준비 ─────────────────────────
def fmt_time(h):
    if not h:
        return ""
    kind, v = h
    if kind == "day":
        return f"{v}일"
    whole, mins = int(v), round((v - int(v)) * 60)
    return f"{whole}시간" + (f" {mins}분" if mins else "")


POSTS = []
for c in C["posts"]:
    raw = RAW[c["id"]]
    crew, hours = crew_hours(raw["paragraphs"])
    # 첫 사진(제목 표지)과 반복 홍보 카드는 빼고 현장 사진만 사용
    photos = [rel for rel in raw["images"] if not rel.endswith("/1.jpg") and rel not in BANNERS]
    POSTS.append({**c, "date": raw["date"], "blogUrl": raw["url"], "place": raw.get("place"),
                  "crew": crew, "hours": hours, "time": fmt_time(hours),
                  "quotes": quotes(raw["paragraphs"]), "photos": photos,
                  "thumb": photos[0] if photos else None,
                  "path": f"/portfolio/{c['id']}/", "story": STORIES.get(c["id"])})


def slugify(t):
    t = re.sub(r"[—·,()/]", " ", t)
    return re.sub(r"\s+", "-", t.strip())


for c in NEW_CASES:
    raw = RAW[c["id"]]
    photos = [rel[:-4] + ".webp" for rel in raw["images"] if not rel.endswith("/1.jpg") and rel not in BANNERS]
    POSTS.append({**c, "date": raw["date"], "blogUrl": None,
                  "place": {"name": c["place"]} if c.get("place") else None,
                  "crew": c["crew"], "hours": tuple(c["hours"]), "time": fmt_time(c["hours"]),
                  "quotes": [c["quote"]], "photos": photos, "thumb": photos[0] if photos else None,
                  "path": f"/portfolio/{slugify(c['title'])}/"})
for p in POSTS:
    p["href"] = quote(p["path"])
assert len({p["path"] for p in POSTS}) == len(POSTS), "사례 주소 중복"
POSTS.sort(key=lambda p: p["date"], reverse=True)

BY_SVC, BY_REG, BY_COMBO = defaultdict(list), defaultdict(list), defaultdict(list)
for p in POSTS:
    BY_SVC[p["cat"]].append(p)
    BY_REG[p["region"]].append(p)
    BY_COMBO[(p["region"], p["cat"])].append(p)

REGION_PAGES = [r for r in REG if len(BY_REG[r]) >= MIN_PAGE]
REGION_PAGES.sort(key=lambda r: -len(BY_REG[r]))
COMBOS = sorted([k for k, v in BY_COMBO.items() if len(v) >= MIN_PAGE and k[0] in REGION_PAGES],
                key=lambda k: (-len(BY_COMBO[k]), k))
SVC_ORDER = sorted(SVC, key=lambda k: -len(BY_SVC[k]))


def apartments(posts):
    """블로그 '장소'에 붙은 단지명 (띄어쓰기 없는 이름만 = 주소형 표기 제외)"""
    names = []
    for p in posts:
        n = (p["place"] or {}).get("name", "").replace("배드민턴장", "")
        if n and " " not in n and n not in names:
            names.append(n)
    return names


def crew_summary(posts):
    crews = Counter(p["crew"] for p in posts if p["crew"])
    hrs = [p["hours"][1] for p in posts if p["hours"] and p["hours"][0] == "hour"]
    short = sum(1 for h in hrs if h <= 3)
    return crews, hrs, short


ALL_CREWS, ALL_HRS, ALL_SHORT = crew_summary(POSTS)
DATES = sorted(p["date"] for p in POSTS)


# ───────────────────────── 공통 조각 ─────────────────────────
def url(path):
    return BASE + quote(path, safe="/")


def head(title, desc, path, img=None, extra="", home=False):
    if TODAY < FREEZE_UNTIL and path in BASELINE:   # 재평가 중인 기존 페이지는 제목·설명을 바꾸지 않음
        title, desc = BASELINE[path]["title"], BASELINE[path]["desc"]
    og_img = url("/img/" + img) if img else url("/favicon-512.png")
    verify = f'<meta name="naver-site-verification" content="{S["naverVerification"]}" />' if home else ""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
{verify}
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url(path)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="ko_KR">
<meta property="og:site_name" content="{e(S['brand'])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{og_img}">
<meta property="og:url" content="{url(path)}">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" type="image/png" sizes="48x48" href="/favicon-48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<meta name="theme-color" content="#13294B">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css?v={VERSION}">
<link rel="alternate" type="application/rss+xml" title="{e(S['brand'])} 시공사례" href="{url('/rss.xml')}">
{extra}
</head>
<body>
"""


def jsonld(obj):
    return f'<script type="application/ld+json">{json.dumps(obj, ensure_ascii=False)}</script>'


def breadcrumb_ld(items):
    return jsonld({"@context": "https://schema.org", "@type": "BreadcrumbList",
                   "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": url(u)}
                                       for i, (n, u) in enumerate(items)]})


def header(active=""):
    def a(path, label, key):
        cls = ' class="on"' if key == active else ""
        return f'<a href="{path}"{cls}>{label}</a>'
    return f"""<header class="hd">
 <div class="wrap hd-in">
  <a class="logo" href="/"><img src="/favicon.svg" alt="" width="30" height="30"><span>{e(S['brand'])}</span></a>
  <nav class="gnb" id="gnb">
   {a('/#services', '작업분야', 'service')}{a('/portfolio/', '시공사례', 'portfolio')}{a('/area/', '출장지역', 'area')}{a('/about/', '업체소개', 'about')}{a('/contact/', '상담안내', 'contact')}
   <a class="gnb-cta" href="tel:{TEL}">☎ {PHONE}</a>
  </nav>
  <button class="burger" aria-label="메뉴" onclick="document.body.classList.toggle('menu-open')"><span></span><span></span><span></span></button>
 </div>
</header>
<main>
"""


def crumbs(items):
    parts = [f'<a href="{u}">{e(n)}</a>' for n, u in items[:-1]] + [f"<span>{e(items[-1][0])}</span>"]
    return f'<nav class="crumbs wrap">{" / ".join(parts)}</nav>'


def cta(title="사진 한 장이면 상담이 시작됩니다", region=""):
    who = f"{region}이시면 " if region else ""
    return f"""<section class="cta-band"><div class="wrap">
 <h2>{e(title)}</h2>
 <p>{who}고칠 곳을 <b>멀리서 한 장, 가까이서 한 장</b> 찍어 문자로 보내주세요. 확인 후 가능한 방법과 방문 일정을 알려드립니다.</p>
 <div class="btns"><a class="btn pri" href="sms:{TEL}">✉ 문자로 사진 보내기</a><a class="btn ghost" href="tel:{TEL}">☎ {PHONE}</a></div>
</div></section>
"""


def footer():
    svc_links = "".join(f'<a href="/service/{k}/">{e(SVC[k]["short"])}</a>' for k in SVC_ORDER) + "".join(
        f'<a href="/service/{t["key"]}/">{e(t["short"])}</a>' for t in C.get("themes", []))
    reg_links = "".join(f'<a href="/area/{r}/">{e(REG[r])}</a>' for r in REGION_PAGES)
    return f"""</main>
<footer class="ft"><div class="wrap ft-in">
 <div><b class="ft-brand">{e(S['brand'])}</b>
  <p>{e(S['tagline'])}. 통째로 바꾸기 전에 고장 난 부분부터 찾습니다.</p>
  <p>{e(S['areaLine'])}</p>
  <p><a href="tel:{TEL}">☎ {PHONE}</a> · <a href="{S['blog']}" target="_blank" rel="noopener">네이버 블로그</a></p></div>
 <div><b>작업분야</b><div class="ft-links">{svc_links}</div></div>
 <div><b>출장지역</b><div class="ft-links">{reg_links}</div></div>
</div><p class="wrap copy">© {DATES[-1][:4]} {e(S['brand'])}. All rights reserved.</p></footer>
<div class="callbar">
 <a class="cb-call" href="tel:{TEL}"><span class="cb-kw">{e(S['mainArea'])} 집수리 상담</span><span class="cb-act">📞 지금 전화하기</span></a>
 <a class="cb-sms" href="sms:{TEL}"><span class="cb-act">✉️ 사진 문자</span></a>
</div>
<script src="/assets/site.js?v={VERSION}"></script>
</body></html>
"""


def card(p, show_region=True):
    img = f'<img src="/img/{p["thumb"]}" alt="{e(p["title"])}" loading="lazy">' if p["thumb"] else '<div class="noimg"></div>'
    reg = f'<span class="chip ghost">{e(REG[p["region"]])}</span>' if show_region else ""
    return f"""<a class="card" href="{p['href']}">
 <div class="card-img">{img}</div>
 <div class="card-bd"><div class="chips"><span class="chip">{e(SVC[p['cat']]['short'])}</span>{reg}</div>
 <h3>{e(p['title'])}</h3><p>{e(p['summary'])}</p></div></a>"""


def grid(posts, **kw):
    return '<div class="grid">' + "".join(card(p, **kw) for p in posts) + "</div>"


def write(path, text):
    out = DIST / path.lstrip("/") / "index.html" if path.endswith("/") else DIST / path.lstrip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    PAGES.append(path)


PAGES = []
VERSION = DATES[-1].replace("-", "")


# ───────────────────────── 메인 ─────────────────────────
def build_home():
    n = len(POSTS)
    zones = "".join(f"""<a class="zone" href="/service/{k}/"><b>{e(SVC[k]['short'])}</b>
      <ul>{''.join(f'<li>{e(s)}</li>' for s in SVC[k]['symptoms'])}</ul><span>이 작업 보기 →</span></a>""" for k in SVC_ORDER)
    fields = "".join(f"""<a class="field" href="/service/{k}/"><small>{e(SVC[k]['eng'])}</small>
      <h3>{e(SVC[k]['name'])} <em>{len(BY_SVC[k])}건</em></h3><p>{e(SVC[k]['tagline'])}</p>
      <ul>{''.join(f'<li>{e(w)}</li>' for w in SVC[k]['works'][:3])}</ul></a>""" for k in SVC_ORDER)
    one = ALL_CREWS.get(1, 0)
    regions = "".join(f'<a class="rg" href="/area/{r}/"><b>{e(REG[r])}</b><span>{len(BY_REG[r])}건</span></a>'
                      for r in sorted(REG, key=lambda r: -len(BY_REG[r])) if BY_REG[r] and r in REGION_PAGES)
    others = [REG[r] for r in REG if BY_REG[r] and r not in REGION_PAGES]
    biz = {"@context": "https://schema.org", "@type": "HomeAndConstructionBusiness", "name": S["brand"],
           "url": url("/"), "telephone": "+82-" + PHONE[1:], "image": url("/favicon-512.png"),
           "logo": url("/favicon-512.png"), "sameAs": [S["blog"]],
           "areaServed": [{"@type": "Place", "name": REG[r]} for r in REGION_PAGES],
           "description": f"{S['mainArea']} 집수리 전문. " + ", ".join(SVC[k]["short"] for k in SVC_ORDER)}
    site = {"@context": "https://schema.org", "@type": "WebSite", "name": S["brand"], "url": url("/")}
    title = f"{S['mainArea']} 집수리 {S['brand']} | 원상복구·싱크대·욕실·로봇청소기 직배수"
    desc = (f"{S['mainArea']} 집수리 전문 {S['brand']}. 싱크대·상판·욕실 줄눈·변기 백시멘트·문·거울·로봇청소기 직배수까지 "
            f"고장 난 부분만 고칩니다. 블로그에 기록한 시공 {n}건.")
    body = head(title, desc, "/", POSTS[0]["thumb"], jsonld(biz) + jsonld(site), home=True) + header() + f"""
<section class="hero"><div class="wrap">
 <p class="eyebrow">{e(S['mainArea'])} 집수리 · 원상복구 · 생활수리</p>
 <h1>{e(S['mainArea'])} 집수리<br><em>고장 난 부분만,</em> 다 고칩니다</h1>
 <p class="lead">블로그에 기록한 최근 시공 <b>{n}건</b>. 통째로 바꾸라는 말을 듣기 전에, 살릴 수 있는 것부터 찾습니다.</p>
 <div class="btns"><a class="btn pri" href="sms:{TEL}">✉ 문자로 사진 보내기</a><a class="btn ghost" href="tel:{TEL}">☎ {PHONE}</a></div>
 <p class="note">현장 작업 중에는 전화를 못 받을 수 있습니다. 문자로 사진을 보내주시면 확인 후 답을 드립니다.</p>
</div></section>

<section class="sec"><div class="wrap">
 <h2 class="h2">집 안 어디가 문제인가요?</h2>
 <p class="sub">무슨 공사인지 몰라도 됩니다. 증상을 고르시면 그 자리에서 하는 작업을 보여드립니다.</p>
 <div class="zones">{zones}</div>
</div></section>

<section class="sec alt" id="services"><div class="wrap">
 <h2 class="h2">작업 분야 {len(SVC)}가지</h2>
 <p class="sub">블로그 기록 {n}건을 분야별로 나눈 것입니다. 숫자는 실제로 한 건수입니다.</p>
 <div class="fields">{fields}</div>
 <h2 class="h3">많이 찾는 작업</h2>{kw_chips()}
 {''.join(f'<div class="box"><b>{e(t["name"])}</b><p>{e(t["tagline"])}. 전세·월세 퇴거 전 원상복구, 입주 전 하자보수까지 기록 {len(t["posts"])}건.</p><a href="/service/{t["key"]}/">원상복구 작업 보기 →</a></div>' for t in C.get("themes", []))}
</div></section>

<section class="sec"><div class="wrap">
 <h2 class="h2">대부분 몇 시간이면 끝납니다</h2>
 <p class="sub">블로그 글마다 몇 명이 몇 시간 일했는지 적어 두었습니다. 지어낸 값이 아니라 기록입니다.</p>
 <div class="stats">
  <div><b>{one}건</b><span>1명이 작업</span><p>인원을 적어 둔 {sum(ALL_CREWS.values())}건 중</p></div>
  <div><b>{ALL_SHORT}건</b><span>3시간 안에 마무리</span><p>시간을 적어 둔 {len(ALL_HRS)}건 중</p></div>
  <div><b>{n}건</b><span>블로그 기록</span><p>{DATES[0][:4]}년 {int(DATES[0][5:7])}월부터 사진과 함께</p></div>
 </div>
</div></section>

<section class="sec alt"><div class="wrap">
 <h2 class="h2">최근 시공사례</h2>
 {grid(POSTS[:8])}
 <p class="more"><a class="btn ghost" href="/portfolio/">시공사례 {n}건 전체 보기 →</a></p>
</div></section>

<section class="sec"><div class="wrap">
 <h2 class="h2">이렇게 진행됩니다</h2>
 {steps()}
</div></section>

<section class="sec alt"><div class="wrap">
 <h2 class="h2">출장 가능 지역</h2>
 <p class="sub">숫자는 블로그에 기록한 실제 시공 건수입니다. {e(S['areaLine'])}.</p>
 <div class="regions">{regions}</div>
 {f'<p class="sub small">그 밖에 {", ".join(others)}에서도 작업했습니다.</p>' if others else ''}
</div></section>
""" + cta() + footer()
    write("/", body)


def steps():
    items = [("사진으로 문의", "고칠 곳을 멀리서 한 장, 가까이서 한 장 찍어 문자로 보내주세요. 지역과 집 안 위치도 함께 적어 주시면 좋습니다."),
             ("되는지 먼저 말씀드리기", "사진으로 구조를 보고 가능한 방법과 현장에서 더 봐야 할 부분을 미리 알려드립니다."),
             ("방문해서 그 부분만", "통째로 바꾸지 않고 고장 난 부분부터 고칩니다. 대부분 1명이 몇 시간 안에 끝냅니다."),
             ("확인하고 정리", "여닫고 물을 틀어 보며 작동을 확인하고, 작업 자리를 정리한 뒤 마칩니다.")]
    return '<ol class="steps">' + "".join(f"<li><b>{e(t)}</b><p>{e(d)}</p></li>" for t, d in items) + "</ol>"


# ───────────────────────── 작업분야 ─────────────────────────
def build_services():
    for k in SVC_ORDER:
        s, posts = SVC[k], BY_SVC[k]
        crews, hrs, short = crew_summary(posts)
        qs = []
        for p in posts:
            if p["quotes"] and len(qs) < 4:
                qs.append(p["quotes"][0])
        regs = Counter(p["region"] for p in posts)
        combos = [r for (r, c) in COMBOS if c == k]
        photos = [(p, ph) for p in posts for ph in p["photos"][:2]][:8]
        faq = s["faq"] + ([{"q": "작업은 얼마나 걸리나요?",
                            "a": f"이 분야에서 시간을 적어 둔 {len(hrs)}건 중 {short}건이 3시간 안에 끝났습니다. 대부분 {crews.most_common(1)[0][0]}명이 작업합니다."}]
                          if hrs and crews else [])
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": [{"@type": "Question", "name": f["q"],
                                  "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]}
        path = f"/service/{k}/"
        bc = [("홈", "/"), ("작업분야", "/#services"), (s["name"], path)]
        title = f"{s['name']} | {S['mainArea']} {S['brand']}"
        desc = f"{s['tagline']}. {S['brand']} {s['name']} 기록 {len(posts)}건. " + ", ".join(s["works"][:3]) + "."
        body = head(title, desc, path, posts[0]["thumb"], breadcrumb_ld(bc) + jsonld(faq_ld)) + header("service") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap">
 <small class="eng">{e(s['eng'])}</small>
 <h1>{e(s['name'])}</h1>
 <p class="lead">{e(s['tagline'])}</p>
 <div class="chips big"><span class="chip">기록 {len(posts)}건</span>{''.join(f'<a class="chip ghost" href="/area/{r}/{k}/">{e(REG[r])}</a>' for r in combos)}</div>
</div></section>
<section class="sec"><div class="wrap narrow">
 <p class="prose">{e(s['intro'])} {S['brand']} 블로그 기록 {len(POSTS)}건 중 <b>{len(posts)}건</b>이 이 작업입니다.</p>
 <h2 class="h3">이 분야에서 하는 작업</h2>
 <ul class="checks">{''.join(f'<li>{e(w)}</li>' for w in s['works'])}</ul>
 {f'<h2 class="h3">이런 문의를 받았습니다</h2><p class="sub small">블로그에 남아 있는 실제 고객님 말씀입니다.</p><div class="quotes">' + ''.join(f'<blockquote>“{e(q)}”</blockquote>' for q in qs) + '</div>' if qs else ''}
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">{e(s['short'])} 시공 사진</h2>
 <div class="gallery">{''.join(f'<a href="{p["href"]}"><img src="/img/{ph}" alt="{e(p["title"])}" loading="lazy"></a>' for p, ph in photos)}</div>
</div></section>
<section class="sec"><div class="wrap">
 <h2 class="h2">진행 절차</h2>{steps()}
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">{e(s['short'])} 시공사례 {len(posts)}건</h2>{grid(posts)}
</div></section>
<section class="sec"><div class="wrap narrow">
 <h2 class="h2">자주 묻는 질문</h2>
 <div class="faq">{''.join(f'<details><summary>Q. {e(f["q"])}</summary><p>{e(f["a"])}</p></details>' for f in faq)}</div>
 {f'<h2 class="h3">자주 찾는 {e(s["short"])} 작업</h2>' + kw_chips([k]) if any(x["svc"] == k for x in KWP) else ''}
 <h2 class="h3">지역별로 보기</h2>
 <div class="chips">{''.join(f'<a class="chip ghost" href="/area/{r}/">{e(REG[r])} {c}건</a>' if r in REGION_PAGES else f'<span class="chip ghost">{e(REG[r])} {c}건</span>' for r, c in regs.most_common())}</div>
 <h2 class="h3">다른 작업분야</h2>
 <div class="chips">{''.join(f'<a class="chip" href="/service/{o}/">{e(SVC[o]["short"])}</a>' for o in SVC_ORDER if o != k)}{''.join(f'<a class="chip" href="/service/{t["key"]}/">{e(t["short"])}</a>' for t in C.get("themes", []))}</div>
</div></section>
""" + cta(f"{s['short']}, 사진 한 장이면 상담됩니다") + footer()
        write(path, body)


# ───────────────────────── 주제 페이지 (여러 분야에 걸친 상황: 이사 전후 원상복구 등) ─────────────────────────
THEMES = C.get("themes", [])
POST_BY_ID = {p["id"]: p for p in POSTS}


def build_themes():
    for t in THEMES:
        posts = [POST_BY_ID[i] for i in t["posts"] if i in POST_BY_ID]
        qs = [p["quotes"][0] for p in posts if p["quotes"]][:4]
        photos = [(p, ph) for p in posts for ph in p["photos"][:1]][:8]
        cats = Counter(p["cat"] for p in posts)
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": [{"@type": "Question", "name": f["q"],
                                  "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in t["faq"]]}
        path = f"/service/{t['key']}/"
        bc = [("홈", "/"), ("작업분야", "/#services"), (t["name"], path)]
        title = f"{t['name']} | {S['mainArea']} {S['brand']}"
        desc = (f"{t['tagline']}. 전세·월세 퇴거 전 원상복구, 입주 전 하자보수 같은 생활수리를 고장 난 부분만. "
                f"{S['brand']} 기록 {len(posts)}건.")
        body = head(title, desc, path, posts[0]["thumb"], breadcrumb_ld(bc) + jsonld(faq_ld)) + header("service") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap">
 <small class="eng">{e(t['eng'])}</small>
 <h1>{e(t['name'])}</h1>
 <p class="lead">{e(t['tagline'])}</p>
 <div class="chips big"><span class="chip">기록 {len(posts)}건</span>{''.join(f'<a class="chip ghost" href="/service/{k}/">{e(SVC[k]["short"])} {v}건</a>' for k, v in cats.most_common())}</div>
</div></section>
<section class="sec"><div class="wrap narrow">
 <p class="prose">{e(t['intro'])}</p>
 <h2 class="h3">이사 전후로 맡기신 작업</h2>
 <ul class="checks">{''.join(f'<li>{e(w)}</li>' for w in t['works'])}</ul>
 {f'<h2 class="h3">이런 문의를 받았습니다</h2><p class="sub small">블로그에 남아 있는 실제 고객님 말씀입니다.</p><div class="quotes">' + ''.join(f'<blockquote>“{e(q)}”</blockquote>' for q in qs) + '</div>' if qs else ''}
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">원상복구 시공 사진</h2>
 <div class="gallery">{''.join(f'<a href="{p["href"]}"><img src="/img/{ph}" alt="{e(p["title"])}" loading="lazy"></a>' for p, ph in photos)}</div>
</div></section>
<section class="sec"><div class="wrap">
 <h2 class="h2">진행 절차</h2>{steps()}
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">이사 전후 시공사례 {len(posts)}건</h2>{grid(posts)}
</div></section>
<section class="sec"><div class="wrap narrow">
 <h2 class="h2">자주 묻는 질문</h2>
 <div class="faq">{''.join(f'<details><summary>Q. {e(f["q"])}</summary><p>{e(f["a"])}</p></details>' for f in t['faq'])}</div>
 <h2 class="h3">다른 작업분야</h2>
 <div class="chips">{''.join(f'<a class="chip" href="/service/{o}/">{e(SVC[o]["short"])}</a>' for o in SVC_ORDER)}</div>
</div></section>
""" + cta("이사 날짜와 사진을 함께 보내주세요") + footer()
        write(path, body)



# ───────────────────────── 검색어 페이지 (/로보락-직배수-키트-설치/ 처럼 검색어 그대로인 주소) ─────────────────────────
KWP = C.get("keywordPages", [])
KW_OF_POST = {}
for _k in KWP:
    for _i in _k["posts"]:
        KW_OF_POST.setdefault(_i, _k)


def kw_href(k):
    return "/" + quote(k["slug"]) + "/"


def build_keywords():
    for k in KWP:
        posts = [POST_BY_ID[i] for i in k["posts"] if i in POST_BY_ID]
        s = SVC[k["svc"]]
        regions = []
        for p in posts:
            if REG[p["region"]] not in regions:
                regions.append(REG[p["region"]])
        crews, hrs, short = crew_summary(posts)
        qs = [p["quotes"][0] for p in posts if p["quotes"]][:3]
        photos = [(p, ph) for p in posts for ph in p["photos"][:3]][:9]
        faq = k["faq"] + [{"q": "어느 지역까지 오시나요?", "a": f"{S['areaLine']}. 이 작업은 {', '.join(regions)}에서 했습니다."}]
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": [{"@type": "Question", "name": f["q"],
                                  "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]}
        path = f"/{k['slug']}/"
        bc = [("홈", "/"), (s["name"], f"/service/{k['svc']}/"), (k["kw"], path)]
        title = f"{k['kw']} | {S['mainArea']} {S['brand']}"
        desc = f"{k['kw']}. {k['lead']}. {S['brand']} 실제 시공 {len(posts)}건 ({', '.join(regions)}). 사진을 문자로 보내주시면 가능한 방법부터 알려드립니다."
        others = [o for o in KWP if o is not k]
        body = head(title, desc, path, posts[0]["thumb"], breadcrumb_ld(bc) + jsonld(faq_ld)) + header("service") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap">
 <small class="eng">{e(s['eng'])}</small>
 <h1>{e(k['kw'])}</h1>
 <p class="lead">{e(k['lead'])}</p>
 <div class="chips big"><span class="chip">시공 {len(posts)}건</span>{''.join(f'<span class="chip ghost">{e(r)}</span>' for r in regions)}</div>
</div></section>
<section class="sec"><div class="wrap narrow">
 <p class="prose">{e(k['intro'])}</p>
 <h2 class="h3">{e(k['kw'])}, 이런 집에서 했습니다</h2>
 <ul class="checks">{''.join(f'<li>{e(c)}</li>' for c in k['checks'])}</ul>
 {f'<p class="sub small">시간을 적어 둔 {len(hrs)}건 중 {short}건이 3시간 안에 끝났고, 대부분 {crews.most_common(1)[0][0]}명이 작업했습니다.</p>' if hrs and crews else ''}
 {f'<h2 class="h3">고객님 말씀</h2><div class="quotes">' + ''.join(f'<blockquote>“{e(q)}”</blockquote>' for q in qs) + '</div>' if qs else ''}
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">{e(k['kw'])} 사진</h2>
 <div class="gallery">{''.join(f'<a href="{p["href"]}"><img src="/img/{ph}" alt="{e(k["kw"])} — {e(p["title"])}" loading="lazy"></a>' for p, ph in photos)}</div>
</div></section>
<section class="sec"><div class="wrap">
 <h2 class="h2">{e(k['kw'])} 시공사례 {len(posts)}건</h2>{grid(posts)}
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">진행 절차</h2>{steps()}
</div></section>
<section class="sec"><div class="wrap narrow">
 <h2 class="h2">자주 묻는 질문</h2>
 <div class="faq">{''.join(f'<details><summary>Q. {e(f["q"])}</summary><p>{e(f["a"])}</p></details>' for f in faq)}</div>
 <div class="box"><b>{e(s['name'])}</b><p>{e(s['tagline'])}</p><a href="/service/{k['svc']}/">{e(s['short'])} 작업 전체 보기 →</a></div>
 <h2 class="h3">다른 작업</h2>
 <div class="chips">{''.join(f'<a class="chip ghost" href="{kw_href(o)}">{e(o["kw"])}</a>' for o in others)}</div>
</div></section>
""" + cta(f"{k['kw']}, 사진 한 장이면 상담됩니다") + footer()
        write(path, body)


def kw_chips(keys=None):
    items = [k for k in KWP if keys is None or k["svc"] in keys]
    return '<div class="chips">' + "".join(f'<a class="chip ghost" href="{kw_href(k)}">{e(k["kw"])}</a>' for k in items) + "</div>"


# ───────────────────────── 시공사례 ─────────────────────────
def build_portfolio():
    chips = '<div class="chips filter"><button class="chip on" data-f="all">전체 ' + str(len(POSTS)) + "</button>" + "".join(
        f'<button class="chip ghost" data-f="{k}">{e(SVC[k]["short"])} {len(BY_SVC[k])}</button>' for k in SVC_ORDER) + "</div>"
    cards = "".join(f'<div class="fi" data-c="{p["cat"]}">{card(p)}</div>' for p in POSTS)
    bc = [("홈", "/"), ("시공사례", "/portfolio/")]
    title = f"시공사례 {len(POSTS)}건 | {S['brand']}"
    desc = f"{S['brand']}가 직접 다녀온 집수리 현장 {len(POSTS)}건. 지역, 작업 내용, 인원과 시간, 현장 사진을 정리했습니다."
    body = head(title, desc, "/portfolio/", POSTS[0]["thumb"], breadcrumb_ld(bc)) + header("portfolio") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap"><small class="eng">PORTFOLIO</small><h1>시공사례 {len(POSTS)}건</h1>
 <p class="lead">블로그에 기록한 현장을 한 곳에 모았습니다. 분야를 누르면 그 작업만 볼 수 있습니다.</p></div></section>
<section class="sec"><div class="wrap">{chips}<div class="grid">{cards}</div></div></section>
""" + cta() + footer()
    write("/portfolio/", body)

    for p in POSTS:
        s = SVC[p["cat"]]
        path = p["path"]
        bc = [("홈", "/"), ("시공사례", "/portfolio/"), (p["title"], path)]
        facts = [("지역", p["area"]), ("작업분야", s["name"]), ("작업일", p["date"].replace("-", ". "))]
        if p["crew"]:
            facts.append(("인원", f"{p['crew']}명"))
        if p["time"]:
            facts.append(("소요", p["time"]))
        place = (p["place"] or {}).get("name", "")
        if place and " " not in place:
            facts.append(("현장", place.replace("배드민턴장", "")))
        related = [q for q in BY_SVC[p["cat"]] if q["id"] != p["id"]][:6]
        reg_link = f'<a href="/area/{p["region"]}/">{e(REG[p["region"]])} 다른 작업 보기</a>' if p["region"] in REGION_PAGES else ""
        quote = f'<blockquote class="q1">“{e(p["quotes"][0])}”<cite>고객님 말씀</cite></blockquote>' if p["quotes"] else ""
        st = p.get("story")
        ex = EXTRA.get(p["id"])
        story = f"""<section class="story">
 <h2 class="h3">현장 상황</h2><p class="prose">{e(st['situation'])}</p>
 <h2 class="h3">확인한 내용</h2><p class="prose">{e(st['check'])}</p>
 <h2 class="h3">작업 순서</h2><ol class="nums">{''.join(f'<li>{e(x)}</li>' for x in st['steps'])}</ol>
 {f"<h2 class='h3'>이 현장의 작업 포인트</h2><p class='prose'>{e(POINTS[p['id']])}</p>" if p["id"] in POINTS else ""}
 <h2 class="h3">비슷한 증상이라면</h2><p class="prose">{e(st['tip'])}</p>
 {f"<h2 class='h3'>작업 후 달라진 점</h2><p class='prose'>{e(ex['result'])}</p>" if ex else ""}
 {f"<h2 class='h3'>맡기기 전에 확인할 점</h2><ul class='checks'>" + "".join(f"<li>{e(x)}</li>" for x in ex['cautions']) + "</ul>" if ex else ""}
</section>""" if st else ""
        blog_btn = (f'<a class="btn ghost" href="{p["blogUrl"]}" target="_blank" rel="noopener">블로그에서 작업 과정 전체 보기 →</a> '
                    if p["blogUrl"] else "")
        art = {"@context": "https://schema.org", "@type": "Article", "headline": p["title"], "datePublished": p["date"],
               "image": [url("/img/" + ph) for ph in p["photos"][:3]],
               "author": {"@type": "Organization", "name": S["brand"]},
               "publisher": {"@type": "Organization", "name": S["brand"],
                             "logo": {"@type": "ImageObject", "url": url("/favicon-512.png")}},
               "mainEntityOfPage": url(p["path"]), "description": p["summary"]}
        title = f"{p['title']} | {S['brand']}"
        body = head(title, p["summary"], path, p["thumb"], breadcrumb_ld(bc) + jsonld(art)) + header("portfolio") + crumbs(bc) + f"""
<article class="sec case"><div class="wrap narrow">
 <div class="chips"><a class="chip" href="/service/{p['cat']}/">{e(s['short'])}</a><span class="chip ghost">{e(REG[p['region']])}</span></div>
 <h1>{e(p['title'])}</h1>
 <p class="prose">{e(p['summary'])}</p>
 <dl class="facts">{''.join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in facts)}</dl>
 {quote}
 {story}
 <h2 class="h3">현장 사진 {len(p['photos'])}장</h2>
 <div class="gallery lb">{''.join(f'<a href="/img/{ph}"><img src="/img/{ph}" alt="{e(p["title"])} 사진 {i + 1}" loading="{"eager" if i < 2 else "lazy"}"></a>' for i, ph in enumerate(p['photos']))}</div>
 <p class="src">{blog_btn}{reg_link}</p>
 {f'<p class="src"><a class="btn ghost" href="{kw_href(KW_OF_POST[p["id"]])}">{e(KW_OF_POST[p["id"]]["kw"])} 사례 모아 보기 →</a></p>' if p["id"] in KW_OF_POST else ''}
 <div class="box"><b>{e(s['name'])}은 이렇게 합니다</b><p>{e(s['tagline'])}</p><a href="/service/{p['cat']}/">작업 방법 · 자주 묻는 질문 보기 →</a></div>
</div></article>
<section class="sec alt"><div class="wrap"><h2 class="h2">비슷한 시공사례</h2>{grid(related)}</div></section>
""" + cta() + footer()
        write(path, body)


# ───────────────────────── 출장지역 ─────────────────────────

SERVICE_ZONES = [
    ("서울", ["강남", "서초", "송파", "강동", "강서", "양천", "구로", "영등포", "금천", "관악", "동작", "마포", "은평", "서대문",
             "종로", "중구", "용산", "성동", "광진", "노원", "도봉", "중랑", "동대문", "성북", "강북"]),
    ("경기 남부", ["수원", "용인", "화성", "동탄", "병점", "오산", "평택", "안성", "안양", "군포", "의왕", "과천", "성남", "분당"]),
    ("경기 서부·인천", ["인천", "부천", "시흥", "광명", "안산", "김포"]),
    ("경기 동부", ["하남", "경기 광주", "이천", "여주", "구리", "남양주"]),
    ("경기 북부", ["고양", "일산", "파주", "의정부", "양주"]),
    ("충남", ["아산", "천안"]),
]


def zone_html():
    by_name = {REG[r]: f"/area/{r}/" for r in REGION_PAGES}
    outs = {t: quote(hub_path(hb)) for hb in OUT["hubs"] for t in hb["towns"]}
    out = []
    for zname, names in SERVICE_ZONES:
        items = []
        for nm in names:
            link = by_name.get(nm) or outs.get(nm)
            items.append(f'<a href="{link}">{e(nm)}</a>' if link else e(nm))
        out.append(f"<div><b>{e(zname)}</b><p>{' · '.join(items)}</p></div>")
    return "".join(out)


def build_areas():
    rows = "".join(f'<a class="rg" href="/area/{r}/"><b>{e(REG[r])}</b><span>{len(BY_REG[r])}건</span></a>' for r in REGION_PAGES)
    others = [f"{REG[r]} {len(BY_REG[r])}건" for r in REG if BY_REG[r] and r not in REGION_PAGES]
    bc = [("홈", "/"), ("출장지역", "/area/")]
    body = head(f"출장지역 | {S['brand']}", f"{S['brand']} 출장 지역과 지역별 실제 시공 기록. {S['areaLine']}.", "/area/", None,
                breadcrumb_ld(bc)) + header("area") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap"><small class="eng">AREA</small><h1>출장 가능 지역</h1>
 <p class="lead">{e(S['areaLine'])}. 숫자는 블로그에 기록한 실제 시공 건수입니다.</p></div></section>
<section class="sec"><div class="wrap"><div class="regions">{rows}</div>
 {f'<p class="sub small">그 밖에 {", ".join(others)}의 기록이 있습니다. 목록에 없는 지역도 일정이 맞으면 방문합니다.</p>' if others else ''}
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">출장 가능 지역 전체</h2>
 <p class="sub">시공 기록이 아직 없는 곳도 출장 갑니다. 밑줄 친 지역을 누르면 실제 시공 기록이나 권역 출장 안내를 볼 수 있습니다.</p>
 <div class="zone-list">{zone_html()}</div>
</div></section>""" + cta() + footer()
    write("/area/", body)

    for r in REGION_PAGES:
        posts, name = BY_REG[r], REG[r]
        svc_cnt = Counter(p["cat"] for p in posts)
        top, top_n = svc_cnt.most_common(1)[0]
        apts = apartments(posts)
        path = f"/area/{r}/"
        bc = [("홈", "/"), ("출장지역", "/area/"), (f"{name} 집수리", path)]
        combos = [c for (rr, c) in COMBOS if rr == r]
        lead = f"{name}에서 기록한 시공은 {len(posts)}건이고, 그중 {top_n}건이 {SVC[top]['short']} 작업입니다."
        title = f"{name} 집수리 | {S['brand']}"
        desc = (f"{name} " + ", ".join(f"{SVC[k]['short']}" for k, _ in svc_cnt.most_common(4))
                + f". 고장 난 부분만 고칩니다. 사진을 문자로 보내주시면 가능한 방법부터 알려드립니다. {name} 시공 기록 {len(posts)}건.")
        body = head(title, desc, path, posts[0]["thumb"], breadcrumb_ld(bc)) + header("area") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap"><small class="eng">AREA · {e(name)}</small><h1>{e(name)} 집수리</h1>
 <p class="lead">{e(lead)}</p>
 <div class="chips big">{''.join(f'<a class="chip" href="/area/{r}/{k}/">{e(SVC[k]["short"])} {v}건</a>' if k in combos else f'<a class="chip ghost" href="/service/{k}/">{e(SVC[k]["short"])} {v}건</a>' for k, v in svc_cnt.most_common())}</div>
</div></section>
<section class="sec"><div class="wrap">
 {f'<p class="sub">{e(", ".join(apts))}에서 작업했습니다.</p>' if apts else ''}
 <h2 class="h2">{e(name)}에서 진행한 작업</h2>{grid(posts, show_region=False)}
</div></section>""" + cta(f"{name}이시면 사진만 보내주세요") + footer()
        write(path, body)

    for (r, k) in COMBOS:
        posts, name, s = BY_COMBO[(r, k)], REG[r], SVC[k]
        total = len(BY_REG[r])
        apts = apartments(posts)
        path = f"/area/{r}/{k}/"
        bc = [("홈", "/"), ("출장지역", "/area/"), (name, f"/area/{r}/"), (s["short"], path)]
        lead = f"{name} 기록 {total}건 중 {len(posts)}건이 {s['short']} 작업입니다."
        same_svc = [rr for (rr, kk) in COMBOS if kk == k and rr != r]
        title = f"{name} {s['name']} | {S['brand']}"
        desc = (f"{name} {s['name']}. {s['tagline']}. 사진을 문자로 보내주시면 가능한 방법부터 알려드립니다. "
                f"{name} 시공 기록: " + " · ".join(p["title"] for p in posts[:2]))
        body = head(title, desc, path, posts[0]["thumb"], breadcrumb_ld(bc)) + header("area") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap"><small class="eng">{e(s['eng'])} · {e(name)}</small><h1>{e(name)} {e(s['name'])}</h1>
 <p class="lead">{e(lead)} {e(s['tagline'])}.</p></div></section>
<section class="sec"><div class="wrap">
 {f'<p class="sub">{e(", ".join(apts))}에서 작업했습니다.</p>' if apts else ''}
 <h2 class="h2">{e(name)}에서 진행한 {e(s['short'])}</h2>{grid(posts, show_region=False)}
 <div class="box"><b>{e(s['name'])}은 이렇게 합니다</b><p>{e(s['intro'])}</p><a href="/service/{k}/">작업 방법 · 자주 묻는 질문 보기 →</a></div>
 <h2 class="h3">{e(name)}의 다른 작업</h2><p><a class="btn ghost" href="/area/{r}/">{e(name)} 집수리 전체 →</a></p>
 {f'<h2 class="h3">다른 지역 {e(s["short"])}</h2><div class="chips">' + ''.join(f'<a class="chip ghost" href="/area/{o}/{k}/">{e(REG[o])}</a>' for o in same_svc) + '</div>' if same_svc else ''}
</div></section>""" + cta(f"{name}이시면 사진만 보내주세요") + footer()
        write(path, body)



# ───────────────────────── 출장 안내 (사례가 아직 없는 지역 × 작업) ─────────────────────────
# "여기서 시공했다"가 아니라 "여기도 간다"를 알리는 페이지. 사례는 실제 지역 그대로 보여준다.
def josa(word, a, b):
    ch = word[-1]
    return a if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 else b


def zone_of(p):
    if p["region"] == "seoul":
        for gu, z in OUT["seoulGu"].items():
            if gu in p["area"] or gu in p["title"]:
                return z
        return "seoul-sw"
    return OUT["regionZone"].get(p["region"], "gg-s")


def place_label(p):
    if p["region"] == "seoul":
        m = re.search(r"서울\S*\s+(\S+?)구", p["area"])
        return f"서울 {m.group(1)}" if m else "서울"
    return REG[p["region"]]


def out_path(rname, t):
    return f"/{rname}-{t['slug']}/"


def hub_path(h):
    return f"/{h['slug']}/"


def build_outreach():
    """권역 출장 페이지: 기록이 아직 없는 지역을 권역 단위로 안내하고, 그 권역의 실제 사례를 보여준다."""
    for h in OUT["hubs"]:
        zone = OUT["zones"][h["zone"]]
        towns = "·".join(h["towns"])
        cases = [p for p in POSTS if zone_of(p) == h["zone"]]
        svc_cnt = Counter(p["cat"] for p in cases)
        places = []
        for p in cases:
            if place_label(p) not in places:
                places.append(place_label(p))
        reg_links = [r for r in REGION_PAGES if OUT["regionZone"].get(r) == h["zone"]]
        path = hub_path(h)
        kw = f"{towns} 집수리 출장"
        title = f"{kw} | {zone} 다고침집수리"
        desc = (f"{towns} 집수리 출장. {zone}에서 기록한 실제 시공 {len(cases)}건 — "
                + ", ".join(f"{SVC[k]['short']} {v}건" for k, v in svc_cnt.most_common(3)) + ". 사진을 문자로 보내주시면 가능한 방법부터 알려드립니다.")
        faq = [{"q": f"{towns}까지 출장 오시나요?",
                "a": f"네. {towns}{josa(h['towns'][-1], '은', '는')} {zone} 출장 지역입니다. 고칠 곳 사진과 위치를 문자로 보내주시면 가능한 방법과 방문 일정을 알려드립니다."},
               {"q": "어떤 작업을 맡길 수 있나요?",
                "a": f"이 권역에서는 {', '.join(SVC[k]['short'] for k, _ in svc_cnt.most_common(4))} 작업 기록이 있습니다. 그 밖에도 작업분야에 있는 일은 모두 상담할 수 있습니다."}]
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": [{"@type": "Question", "name": f["q"],
                                  "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]}
        bc = [("홈", "/"), ("출장지역", "/area/"), (kw, path)]
        others = [o for o in OUT["hubs"] if o is not h]
        body = head(title, desc, path, cases[0]["thumb"] if cases else None, breadcrumb_ld(bc) + jsonld(faq_ld)) + header("area") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap"><small class="eng">AREA · {e(zone)}</small><h1>{e(kw)}</h1>
 <p class="lead">{e(zone)} 출장 안내입니다. 이 권역에서 실제로 한 작업을 함께 보여드립니다.</p>
 <div class="chips big">{''.join(f'<a class="chip ghost" href="/service/{k}/">{e(SVC[k]["short"])} {v}건</a>' for k, v in svc_cnt.most_common())}</div>
</div></section>
<section class="sec"><div class="wrap narrow">
 <p class="prose">{e(h['intro'])}</p>
 <div class="box"><b>{e(zone)} 기록</b><p>{e(', '.join(places))}에서 모두 {len(cases)}건을 작업했습니다.</p>
 {('<div class="chips">' + ''.join(f'<a class="chip" href="/area/{r}/">{e(REG[r])} 집수리</a>' for r in reg_links) + '</div>') if reg_links else ''}</div>
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">{e(zone)} 시공사례 {len(cases)}건</h2>{grid(cases[:9])}
</div></section>
<section class="sec"><div class="wrap narrow">
 <h2 class="h2">진행 절차</h2>{steps()}
 <h2 class="h2">자주 묻는 질문</h2>
 <div class="faq">{''.join(f'<details><summary>Q. {e(f["q"])}</summary><p>{e(f["a"])}</p></details>' for f in faq)}</div>
 <h2 class="h3">다른 권역 출장 안내</h2>
 <div class="chips">{''.join(f'<a class="chip ghost" href="{quote(hub_path(o))}">{e("·".join(o["towns"]))}</a>' for o in others)}</div>
</div></section>
""" + cta(f"{towns}이시면 사진만 보내주세요") + footer()
        write(path, body)


# ───────────────────────── 업체소개 ─────────────────────────
def build_about():
    path = "/about/"
    bc = [("홈", "/"), ("업체소개", path)]
    n = len(POSTS)
    biz = {"@context": "https://schema.org", "@type": "HomeAndConstructionBusiness", "name": S["brand"],
           "url": url("/"), "telephone": "+82-" + PHONE[1:], "image": url("/favicon-512.png"),
           "logo": url("/favicon-512.png"), "sameAs": [S["blog"]],
           "areaServed": [{"@type": "Place", "name": REG[r]} for r in REGION_PAGES],
           "description": f"{S['mainArea']} 집수리 전문. " + ", ".join(SVC[k]["short"] for k in SVC_ORDER)}
    about_ld = {"@context": "https://schema.org", "@type": "AboutPage", "name": ABOUT["title"], "url": url(path),
                "about": {"@type": "HomeAndConstructionBusiness", "name": S["brand"], "telephone": "+82-" + PHONE[1:]}}
    stat_rows = "".join(f'<a class="rg" href="/service/{k}/"><b>{e(SVC[k]["short"])}</b><span>{len(BY_SVC[k])}건</span></a>' for k in SVC_ORDER)
    kp = {k["slug"]: k for k in KWP}
    best = ""
    for item in ABOUT["best"]:
        s = SVC[item["svc"]]
        links = "".join(f'<a class="chip ghost" href="{kw_href(kp[x])}">{e(kp[x]["kw"])}</a>' for x in item["kw"] if x in kp)
        best += f"""<div class="best">
 <h3>{e(s['name'])}<em>기록 {len(BY_SVC[item['svc']])}건</em></h3>
 <p class="prose">{e(s['tagline'])}.</p>
 <h4 class="h3">이럴 때 부르세요</h4><ul class="checks">{''.join(f'<li>{e(w)}</li>' for w in item['when'])}</ul>
 <h4 class="h3">수리로 될지, 바꿔야 할지</h4><p class="prose">{e(item['judge'])}</p>
 <h4 class="h3">상담할 때 찍어 보낼 사진</h4><p class="prose">{e(item['photo'])}</p>
 <div class="chips">{links}<a class="chip" href="/service/{item['svc']}/">{e(s['short'])} 작업 전체 →</a></div>
</div>"""
    body = head(ABOUT["title"], ABOUT["desc"], path, POSTS[0]["thumb"], breadcrumb_ld(bc) + jsonld(biz) + jsonld(about_ld)) + header("about") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap"><small class="eng">ABOUT</small><h1>다고침집수리 업체소개</h1>
 <p class="lead">{e(ABOUT['lead'])}</p></div></section>
<section class="sec"><div class="wrap">
 <h2 class="h2">숫자로 보는 작업</h2>
 <p class="sub">블로그에 사진과 함께 기록한 시공 {n}건을 분야별로 나눈 것입니다.</p>
 <div class="regions">{stat_rows}</div>
</div></section>
<section class="sec alt"><div class="wrap">
 <h2 class="h2">이렇게 일합니다</h2>
 <ol class="steps">{''.join(f"<li><b>{e(x['t'])}</b><p>{e(x['d'])}</p></li>" for x in ABOUT['principles'])}</ol>
</div></section>
<section class="sec"><div class="wrap narrow">
 <h2 class="h2">자주 맡기시는 작업</h2>
 <p class="sub">기록이 많은 순서입니다. 증상, 수리로 될지 판단하는 기준, 상담할 때 보내실 사진을 정리했습니다.</p>
 {best}
</div></section>
<section class="sec alt"><div class="wrap narrow">
 <h2 class="h2">출장 지역</h2>
 <p class="prose">{e(S['areaLine'])}. 실제 시공 기록이 있는 지역과 출장 가능한 지역 전체는 <a href="/area/">출장지역</a>에서 볼 수 있습니다.</p>
 <h2 class="h2">상담 방법</h2>
 <p class="prose">고칠 곳을 멀리서 한 장, 가까이서 한 장 찍어 문자로 보내주세요. 현장 작업 중에는 전화를 못 받을 수 있어 문자가 가장 빠릅니다. ☎ {e(PHONE)}</p>
 <div class="btns"><a class="btn pri" href="sms:{TEL}">✉ 문자로 사진 보내기</a><a class="btn ghost" href="tel:{TEL}">☎ {PHONE}</a></div>
</div></section>
""" + footer()
    write(path, body)


# ───────────────────────── 상담안내 ─────────────────────────
def build_contact():
    bc = [("홈", "/"), ("상담안내", "/contact/")]
    body = head(f"상담안내 | {S['brand']}", f"{S['brand']} 상담 방법. 고칠 곳 사진과 위치를 문자로 보내주시면 가능한 방법과 일정을 알려드립니다. {PHONE}",
                "/contact/", None, breadcrumb_ld(bc)) + header("contact") + crumbs(bc) + f"""
<section class="page-hd"><div class="wrap"><small class="eng">CONTACT</small><h1>사진 한 장이면 상담이 시작됩니다</h1>
 <p class="lead">현장 작업 중에는 전화를 못 받을 수 있습니다. 아래 세 가지를 문자로 보내주시면 확인 후 답을 드립니다.</p></div></section>
<section class="sec"><div class="wrap narrow">
 <ol class="send"><li><b>무엇이 불편하신지</b><p>예: 변기 밑이 누렇게 변했어요, 로봇청소기 직배수를 연결하고 싶어요</p></li>
  <li><b>지역과 집 안 위치</b><p>예: 동탄 청계동, 주방 싱크대 아래</p></li>
  <li><b>현장 사진</b><p>멀리서 한 장, 가까이서 한 장. 주변 구조가 보여야 정확하게 답할 수 있습니다.</p></li></ol>
 <div class="btns"><a class="btn pri" href="sms:{TEL}">✉ 문자로 사진 보내기</a><a class="btn ghost" href="tel:{TEL}">☎ {PHONE}</a></div>
 <h2 class="h2">진행 순서</h2>{steps()}
 <h2 class="h3">출장 지역</h2><p class="prose">{e(S['areaLine'])}. <a href="/area/">지역별 기록 보기 →</a></p>
</div></section>""" + footer()
    write("/contact/", body)


# ───────────────────────── 부속 파일 ─────────────────────────
def main_hash(path):
    import hashlib
    h = (DIST / path.lstrip("/") / "index.html").read_text(encoding="utf-8")
    return hashlib.md5(h.split("<main>", 1)[1].split("</main>", 1)[0].encode()).hexdigest()


def lastmod(path):
    """본문(<main>)이 baseline과 같으면 예전 날짜 유지, 바뀌었거나 새 페이지면 오늘 날짜"""
    b = BASELINE.get(path)
    return b["lastmod"] if b and b["hash"] == main_hash(path) else TODAY


def build_assets():
    shutil.copytree(STATIC, DIST, dirs_exist_ok=True)       # css, js, 파비콘, 네이버 인증 파일, .htaccess
    used = {ph for p in POSTS for ph in p["photos"]}
    for rel in used:
        dst = DIST / "img" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".webp"):   # 새로 추가한 사진은 webp로 변환
            Image.open(DATA / "img" / (rel[:-5] + ".jpg")).save(dst, "WEBP", quality=80, method=4)
        else:
            shutil.copy2(DATA / "img" / rel, dst)
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nUser-agent: Yeti\nAllow: /\n\nSitemap: {url('/sitemap.xml')}\n", encoding="utf-8")
    imgs = {p["path"]: p["photos"] for p in POSTS}
    titles = {p["path"]: p["title"] for p in POSTS}
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for path in PAGES:
        parts.append(f"<url><loc>{url(path)}</loc><lastmod>{lastmod(path)}</lastmod>")
        for ph in imgs.get(path, [])[:5]:
            parts.append(f"<image:image><image:loc>{url('/img/' + ph)}</image:loc><image:title>{e(titles[path])}</image:title></image:image>")
        parts.append("</url>")
    parts.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(parts), encoding="utf-8")
    build_rss()
    return len(used)


def build_rss():
    """시공사례 RSS — 네이버 서치어드바이저 'RSS 제출'용 (홈페이지와 같은 도메인이어야 함)"""
    from datetime import datetime
    from email.utils import format_datetime
    from zoneinfo import ZoneInfo
    kst = ZoneInfo("Asia/Seoul")

    def rfc822(d):
        return format_datetime(datetime.strptime(d, "%Y-%m-%d").replace(hour=9, tzinfo=kst))

    items = []
    for p in POSTS:
        link = url(p["path"])
        img = f'<img src="{url("/img/" + p["thumb"])}" alt="{e(p["title"])}"><br>' if p["thumb"] else ""
        items.append(f"""<item>
 <title>{e(p['title'])}</title>
 <link>{link}</link>
 <guid isPermaLink="true">{link}</guid>
 <category>{e(SVC[p['cat']]['name'])}</category>
 <description><![CDATA[{img}{p['summary']} ({p['area']})]]></description>
 <pubDate>{rfc822(p['date'])}</pubDate>
</item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
 <title>{e(S['brand'])} 시공사례</title>
 <link>{url('/')}</link>
 <atom:link href="{url('/rss.xml')}" rel="self" type="application/rss+xml"/>
 <description>{e(S['mainArea'])} 집수리 {e(S['brand'])}가 직접 다녀온 현장 기록</description>
 <language>ko</language>
 <lastBuildDate>{rfc822(DATES[-1])}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
"""
    (DIST / "rss.xml").write_text(rss, encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    build_home(); build_services(); build_themes(); build_keywords(); build_portfolio(); build_areas(); build_outreach(); build_about(); build_contact()
    n_img = build_assets()
    print(f"페이지 {len(PAGES)}개 (메인 1 · 분야 {len(SVC)} · 사례 {len(POSTS) + 1} · 지역 {len(REGION_PAGES) + 1} · 지역+분야 {len(COMBOS)} · 상담 1)")
    print(f"사진 {n_img}장 · sitemap.xml · robots.txt → dist/")
    print("지역 페이지:", ", ".join(f"{REG[r]}({len(BY_REG[r])})" for r in REGION_PAGES))
    print("지역+분야:", ", ".join(f"{REG[r]}-{SVC[k]['short']}({len(BY_COMBO[(r, k)])})" for r, k in COMBOS))


if __name__ == "__main__":
    main()
