"""블로그 본문에서 작업 인원·시간과 고객 문의 문장을 뽑습니다. build.py 가 가져다 씁니다."""
import re

CREW = [r"작업\s*인원\s*:?\s*(?:기사\s*|숙련\s*기사\s*|문\s*수리\s*설비\s*전문가\s*)?(\d)\s*명",
        r"기사\s*(\d)\s*명", r"숙련\s*기사\s*(\d)\s*명", r"전문가\s*(\d)\s*명", r"(\d)\s*명이\s*(?:방문|투입|처음|출동)"]
TIME = [r"(?:작업|소요)\s*시간\s*:?\s*(?:총\s*|약\s*)?(\d+)\s*시간(?:\s*(\d+)\s*분)?",
        r"(\d+)\s*시간\s*(\d+)\s*분\s*만에", r"약?\s*(\d+)\s*시간\s*(?:만에|동안|정도)",
        r"총\s*(\d+)\s*시간\s*소요", r"(\d+)\s*일\s*만에"]


def crew_hours(paragraphs):
    text = " ".join(paragraphs)
    crew = None
    for pat in CREW:
        m = re.search(pat, text)
        if m:
            crew = int(m.group(1))
            break
    hours = None
    for pat in TIME:
        m = re.search(pat, text)
        if m:
            if "일" in pat and "시간" not in pat:
                hours = ("day", int(m.group(1)))
            else:
                mins = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 0
                hours = ("hour", int(m.group(1)) + mins / 60)
            break
    return crew, hours


def quotes(paragraphs, limit=110):
    """고객이 한 말로 보이는 따옴표 문장. 홍보성 문구는 거릅니다."""
    out, buf = [], None
    for p in paragraphs:
        s = p.strip()
        if buf is None and s[:1] in "“\"":
            buf = s
        elif buf is not None:
            buf += " " + s
        if buf is not None and (buf.rstrip()[-1:] in "”\"" and len(buf) > 2):
            q = buf.strip("“”\" ").strip()
            buf = None
            if 20 <= len(q) <= limit and not re.search(r"낯설지|이런 이야기|이런 상황|않을까$", q):
                out.append(q)
        elif buf is not None and len(buf) > limit * 2:
            buf = None
    return out


if __name__ == "__main__":
    import json, sys
    from pathlib import Path
    sys.stdout.reconfigure(encoding="utf-8")
    posts = json.loads((Path(__file__).resolve().parent.parent / "data/posts.json").read_text(encoding="utf-8"))["posts"]
    for i, p in enumerate(posts, 1):
        c, h = crew_hours(p["paragraphs"])
        q = quotes(p["paragraphs"])
        hs = "-" if h is None else (f"{h[1]}일" if h[0] == "day" else f"{h[1]:g}시간")
        print(f"[{i:2}] 인원 {c or '-'}  시간 {hs:6}  문의 {len(q)}  {q[0][:40] if q else ''}")
