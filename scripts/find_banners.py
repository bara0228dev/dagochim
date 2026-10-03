"""
여러 글에 반복해서 들어간 홍보 카드·배너 이미지를 찾아 data/banners.json 에 저장합니다.
같은 그림이 서로 다른 글 3개 이상에 나오면 '현장 사진이 아닌 반복 이미지'로 봅니다.
"""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "data" / "img"


def dhash(path, size=16):
    im = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (px[r * (size + 1) + c] > px[r * (size + 1) + c + 1])
    return bits


def main():
    items = []
    for f in sorted(IMG.glob("*/*.jpg")):
        items.append((f.parent.name, f.name, dhash(f)))

    groups = []  # [hash, [(post, file)]]
    for post, name, h in items:
        for g in groups:
            if bin(g[0] ^ h).count("1") <= 20:   # 256비트 중 20비트 이내 차이 = 같은 그림
                g[1].append((post, name))
                break
        else:
            groups.append([h, [(post, name)]])

    banners = []
    for _, members in groups:
        posts = {p for p, _ in members}
        if len(posts) >= 3:
            banners += [f"{p}/{n}" for p, n in members]
            print(f"반복 이미지: 글 {len(posts)}개에 등장  예) {members[0][0]}/{members[0][1]}")
    (ROOT / "data" / "banners.json").write_text(json.dumps(sorted(banners), indent=1), encoding="utf-8")
    print(f"제외 대상 {len(banners)}장 / 전체 {len(items)}장 -> data/banners.json")


if __name__ == "__main__":
    main()
