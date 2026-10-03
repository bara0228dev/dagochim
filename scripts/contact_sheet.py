"""사진 전체를 번호를 붙인 모음 이미지(10x10)로 만들어 눈으로 검수할 때 씁니다."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
posts = json.loads((ROOT / "data" / "posts.json").read_text(encoding="utf-8"))["posts"]
banners = set(json.loads((ROOT / "data" / "banners.json").read_text(encoding="utf-8")))
out = ROOT / "data" / "sheets"
out.mkdir(exist_ok=True)

cells = []
for i, p in enumerate(posts, 1):
    for rel in p["images"]:
        cells.append((f"{i}-{rel.split('/')[1][:-4]}", ROOT / "data" / "img" / rel, rel in banners))

S, COLS = 120, 10
for sheet in range(0, len(cells), 100):
    chunk = cells[sheet:sheet + 100]
    rows = (len(chunk) + COLS - 1) // COLS
    canvas = Image.new("RGB", (COLS * S, rows * S), "white")
    d = ImageDraw.Draw(canvas)
    for k, (label, path, is_banner) in enumerate(chunk):
        im = Image.open(path).convert("RGB")
        im.thumbnail((S - 4, S - 4))
        x, y = (k % COLS) * S, (k // COLS) * S
        canvas.paste(im, (x + 2, y + 2))
        d.rectangle([x + 2, y + 2, x + 46, y + 16], fill="red" if is_banner else "black")
        d.text((x + 4, y + 3), label, fill="white")
    canvas.save(out / f"sheet{sheet // 100 + 1}.jpg", quality=80)
    print(f"sheet{sheet // 100 + 1}.jpg  {len(chunk)}장")
