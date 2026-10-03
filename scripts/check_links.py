"""dist/ 안의 모든 페이지를 훑어 내부 링크·사진·CSS 경로가 실제 파일로 존재하는지 확인합니다."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

DIST = Path(__file__).resolve().parent.parent / "dist"
sys.stdout.reconfigure(encoding="utf-8")

pages = list(DIST.rglob("index.html"))
broken, checked = [], 0
for page in pages:
    html = page.read_text(encoding="utf-8")
    for ref in re.findall(r'(?:href|src)="([^"]+)"', html):
        if ref.startswith(("http", "tel:", "sms:", "mailto:", "#")):
            continue
        path = unquote(urlparse(ref).path)
        if not path.startswith("/"):
            continue
        target = DIST / path.lstrip("/")
        if path.endswith("/"):
            target = target / "index.html"
        checked += 1
        if not target.exists():
            broken.append((page.relative_to(DIST).as_posix(), ref))

print(f"페이지 {len(pages)}개 · 내부 링크/파일 {checked}개 확인")
if broken:
    print(f"깨진 링크 {len(broken)}개:")
    for p, r in broken[:30]:
        print(f"  {p} -> {r}")
else:
    print("깨진 링크 0개")
