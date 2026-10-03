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
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_facts import crew_hours, quotes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA, DIST, STATIC = ROOT / "data", ROOT / "dist", ROOT / "static"
MIN_PAGE = 2   # 지역·지역+분야 페이지를 만드는 최소 사례 수

C = json.loads((DATA / "content.json").read_text(encoding="utf-8"))
RAW = {p["logNo"]: p for p in json.loads((DATA / "posts.json").read_text(encoding="utf-8"))["posts"]}
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
                  "thumb": photos[0] if photos else None})
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
    return BASE + path


def head(title, desc, path, img=None, extra="", home=False):
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
   {a('/#services', '작업분야', 'service')}{a('/portfolio/', '시공사례', 'portfolio')}{a('/area/', '출장지역', 'area')}{a('/contact/', '상담안내', 'contact')}
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
    svc_links = "".join(f'<a href="/service/{k}/">{e(SVC[k]["short"])}</a>' for k in SVC_ORDER)
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
    return f"""<a class="card" href="/portfolio/{p['id']}/">
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
</div></section>

<section class="sec"><div class="wrap">
 <h2 class="h2">하루를 통째로 비우지 않으셔도 됩니다</h2>
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
        title = f"{s['name']} | {S['brand']}"
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
 <div class="gallery">{''.join(f'<a href="/portfolio/{p["id"]}/"><img src="/img/{ph}" alt="{e(p["title"])}" loading="lazy"></a>' for p, ph in photos)}</div>
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
 <h2 class="h3">지역별로 보기</h2>
 <div class="chips">{''.join(f'<a class="chip ghost" href="/area/{r}/">{e(REG[r])} {c}건</a>' if r in REGION_PAGES else f'<span class="chip ghost">{e(REG[r])} {c}건</span>' for r, c in regs.most_common())}</div>
 <h2 class="h3">다른 작업분야</h2>
 <div class="chips">{''.join(f'<a class="chip" href="/service/{o}/">{e(SVC[o]["short"])}</a>' for o in SVC_ORDER if o != k)}</div>
</div></section>
""" + cta(f"{s['short']}, 사진 한 장이면 상담됩니다") + footer()
        write(path, body)


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
        path = f"/portfolio/{p['id']}/"
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
        art = {"@context": "https://schema.org", "@type": "Article", "headline": p["title"], "datePublished": p["date"],
               "image": [url("/img/" + ph) for ph in p["photos"][:3]],
               "author": {"@type": "Organization", "name": S["brand"]}, "description": p["summary"]}
        title = f"{p['title']} | {S['brand']}"
        body = head(title, p["summary"], path, p["thumb"], breadcrumb_ld(bc) + jsonld(art)) + header("portfolio") + crumbs(bc) + f"""
<article class="sec case"><div class="wrap narrow">
 <div class="chips"><a class="chip" href="/service/{p['cat']}/">{e(s['short'])}</a><span class="chip ghost">{e(REG[p['region']])}</span></div>
 <h1>{e(p['title'])}</h1>
 <p class="prose">{e(p['summary'])}</p>
 <dl class="facts">{''.join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in facts)}</dl>
 {quote}
 <div class="gallery lb">{''.join(f'<a href="/img/{ph}"><img src="/img/{ph}" alt="{e(p["title"])} 사진 {i + 1}" loading="{"eager" if i < 2 else "lazy"}"></a>' for i, ph in enumerate(p['photos']))}</div>
 <p class="src"><a class="btn ghost" href="{p['blogUrl']}" target="_blank" rel="noopener">블로그에서 작업 과정 전체 보기 →</a> {reg_link}</p>
 <div class="box"><b>{e(s['name'])}은 이렇게 합니다</b><p>{e(s['tagline'])}</p><a href="/service/{p['cat']}/">작업 방법 · 자주 묻는 질문 보기 →</a></div>
</div></article>
<section class="sec alt"><div class="wrap"><h2 class="h2">비슷한 시공사례</h2>{grid(related)}</div></section>
""" + cta() + footer()
        write(path, body)


# ───────────────────────── 출장지역 ─────────────────────────
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
        desc = f"{lead} " + ", ".join(f"{SVC[k]['short']} {v}건" for k, v in svc_cnt.most_common(4)) + "."
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
        desc = f"{lead} {s['tagline']}. " + " · ".join(p["title"] for p in posts[:2])
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
def build_assets():
    shutil.copytree(STATIC, DIST, dirs_exist_ok=True)       # css, js, 파비콘, 네이버 인증 파일, .htaccess
    used = {ph for p in POSTS for ph in p["photos"]}
    for rel in used:
        dst = DIST / "img" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DATA / "img" / rel, dst)
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nUser-agent: Yeti\nAllow: /\n\nSitemap: {url('/sitemap.xml')}\n", encoding="utf-8")
    imgs = {f"/portfolio/{p['id']}/": p["photos"] for p in POSTS}
    titles = {f"/portfolio/{p['id']}/": p["title"] for p in POSTS}
    last = {f"/portfolio/{p['id']}/": p["date"] for p in POSTS}
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for path in PAGES:
        parts.append(f"<url><loc>{url(path)}</loc><lastmod>{last.get(path, DATES[-1])}</lastmod>")
        for ph in imgs.get(path, [])[:5]:
            parts.append(f"<image:image><image:loc>{url('/img/' + ph)}</image:loc><image:title>{e(titles[path])}</image:title></image:image>")
        parts.append("</url>")
    parts.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(parts), encoding="utf-8")
    return len(used)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    build_home(); build_services(); build_portfolio(); build_areas(); build_contact()
    n_img = build_assets()
    print(f"페이지 {len(PAGES)}개 (메인 1 · 분야 {len(SVC)} · 사례 {len(POSTS) + 1} · 지역 {len(REGION_PAGES) + 1} · 지역+분야 {len(COMBOS)} · 상담 1)")
    print(f"사진 {n_img}장 · sitemap.xml · robots.txt → dist/")
    print("지역 페이지:", ", ".join(f"{REG[r]}({len(BY_REG[r])})" for r in REGION_PAGES))
    print("지역+분야:", ", ".join(f"{REG[r]}-{SVC[k]['short']}({len(BY_COMBO[(r, k)])})" for r, k in COMBOS))


if __name__ == "__main__":
    main()
