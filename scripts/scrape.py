"""
네이버 블로그 글을 가져와 홈페이지 제작용 데이터로 저장합니다.

사용법:  python scripts/scrape.py <블로그아이디> [사진_최대장수]
결과:    data/posts.json        글 제목·날짜·태그·본문·장소·사진 목록
         data/img/<글번호>/N.jpg  사진 (긴 변 1000px, JPG 품질 78)

- 글 목록은 블로그 RSS(최근 50개)에서 가져옵니다.
- 본문은 글마다 PostView 페이지에서 읽습니다.
- 이미 받은 사진은 다시 받지 않으므로 여러 번 실행해도 됩니다.
"""
import io
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Referer": "https://blog.naver.com/"}


def fetch_rss(blog_id):
    xml = requests.get(f"https://rss.blog.naver.com/{blog_id}.xml", headers=UA, timeout=20)
    xml.raise_for_status()
    channel = ET.fromstring(xml.content).find("channel")
    items = []
    for it in channel.findall("item"):
        link = it.findtext("link", "")
        m = re.search(r"/(\d{9,})", link)
        if not m:
            continue
        items.append({
            "logNo": m.group(1),
            "title": (it.findtext("title") or "").strip(),
            "date": parsedate_to_datetime(it.findtext("pubDate")).strftime("%Y-%m-%d"),
            "tags": [t.strip() for t in (it.findtext("tag") or "").split(",") if t.strip()],
            "category": (it.findtext("category") or "").strip(),
            "url": f"https://blog.naver.com/{blog_id}/{m.group(1)}",
        })
    return {"blogTitle": channel.findtext("title", ""), "items": items}


def parse_post(blog_id, log_no):
    url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
    html = requests.get(url, headers=UA, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("div.se-main-container")
    if main is None:
        return None

    # 본문 문단 (빈 줄·특수 공백 제거)
    paras = []
    for p in main.select(".se-module-text p, .se-text-paragraph"):
        t = re.sub(r"[​\xa0]+", " ", p.get_text(" ", strip=True)).strip()
        if t and t not in paras:
            paras.append(t)

    # 사진: 썸네일 주소의 ?type= 을 큰 사이즈로 바꿔 원본에 가깝게 받음
    imgs = []
    for img in main.select("img.se-image-resource"):
        src = img.get("data-lazy-src") or img.get("src") or ""
        if "pstatic.net" not in src:
            continue
        src = re.sub(r"\?type=.*$", "", src) + "?type=w966"
        if src not in imgs:
            imgs.append(src)

    # 블로그 '장소' 첨부 (아파트명·주소)
    place = None
    pm = main.select_one(".se-placesMap, .se-module-map-text")
    if pm:
        name = pm.select_one(".se-map-title")
        addr = pm.select_one(".se-map-address")
        place = {"name": name.get_text(strip=True) if name else "",
                 "address": addr.get_text(strip=True) if addr else ""}
    return {"paragraphs": paras, "imageUrls": imgs, "place": place}


def save_image(url, dest):
    if dest.exists():
        return True
    r = requests.get(url, headers=UA, timeout=30)
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
        return False
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=78, optimize=True, progressive=True)
    return True


def main():
    blog_id = sys.argv[1] if len(sys.argv) > 1 else "hjadg5582"
    max_imgs = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    rss = fetch_rss(blog_id)
    print(f"블로그: {rss['blogTitle']}  글 {len(rss['items'])}개")

    posts = []
    for i, it in enumerate(rss["items"], 1):
        body = parse_post(blog_id, it["logNo"])
        if body is None:
            print(f"  [{i:2}] 본문 없음: {it['title']}")
            continue
        local = []
        for n, u in enumerate(body["imageUrls"][:max_imgs], 1):
            dest = DATA / "img" / it["logNo"] / f"{n}.jpg"
            if save_image(u, dest):
                local.append(f"{it['logNo']}/{n}.jpg")
        posts.append({**it, "paragraphs": body["paragraphs"], "place": body["place"],
                      "imageCount": len(body["imageUrls"]), "images": local})
        print(f"  [{i:2}] 문단 {len(body['paragraphs']):3} 사진 {len(local)}/{len(body['imageUrls']):3}  {it['title'][:36]}")
        time.sleep(0.4)  # 네이버 서버에 부담 주지 않도록

    DATA.mkdir(exist_ok=True)
    (DATA / "posts.json").write_text(
        json.dumps({"blogId": blog_id, "blogTitle": rss["blogTitle"], "posts": posts},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: data/posts.json  ({len(posts)}개)")


if __name__ == "__main__":
    main()
