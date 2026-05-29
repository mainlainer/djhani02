#!/usr/bin/env python3
"""
종목별 데일리 뉴스 게시판 생성기

portfolio.json 의 8개 종목 → 네이버 증권에서 각 종목 최신 뉴스 1건 조회
→ news.html 생성 (제목 + 본문 발췌 + 출처 + 시각 + 원문 링크).

시세(generate.py)와 동일하게 네이버를 출처로 사용.
GitHub Actions에서 매일 아침(장 시작 전) 자동 실행.
"""

import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
DATA = ROOT / "portfolio.json"
OUT = ROOT / "news.html"

# 기사에서 쓰이는 종목 별칭(표기 차이 보정). portfolio.json의 stock 이름은 기본 포함.
ALIASES = {
    "035420": ["네이버"],       # NAVER → 기사에선 보통 '네이버'
    "105560": ["KB", "국민"],  # KB금융 → KB금융지주/국민은행 등
}


def fetch_latest_news(code: str, keywords=None):
    """네이버 증권 종목 뉴스 1건. 실패 시 None.

    keywords가 주어지면 제목·본문에 종목명이 포함된 최신 기사를 우선 선택하고,
    그런 기사가 없으면 최신 기사로 폴백한다(반환값 matched=False).
    """
    url = f"https://m.stock.naver.com/api/news/stock/{code}?pageSize=20&page=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            groups = json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠️  뉴스 조회 실패({code}): {e}")
        return None

    # 응답은 클러스터(그룹) 배열 — items 평탄화 후 제목 있는 기사만 추림
    # (네이버가 가끔 제목 빈 항목을 섞어 보냄).
    items = []
    for g in groups:
        items.extend(g.get("items", []))
    items = [it for it in items if (it.get("titleFull") or it.get("title") or "").strip()]
    if not items:
        return None

    # datetime(YYYYMMDDHHMM) 기준 최신순 정렬.
    items.sort(key=lambda it: it.get("datetime", ""), reverse=True)

    # 종목명 포함 기사 우선 → 없으면 최신 기사로 폴백.
    matched = True
    it = None
    if keywords:
        for cand in items:
            text = (cand.get("titleFull") or cand.get("title") or "") + (cand.get("body") or "")
            if any(kw in text for kw in keywords):
                it = cand
                break
    if it is None:
        it = items[0]
        matched = not keywords  # 키워드가 없었으면 매칭 개념 자체가 없음
    return {
        "title": it.get("titleFull") or it.get("title", "").strip(),
        "body": (it.get("body") or "").strip(),
        "office": it.get("officeName", ""),
        "datetime": it.get("datetime", ""),
        "url": it.get("mobileNewsUrl", ""),
        "matched": matched,
    }


def fmt_when(dt: str) -> str:
    """'202605291728' → '05/29 17:28'."""
    if len(dt) < 12:
        return ""
    return f"{dt[4:6]}/{dt[6:8]} {dt[8:10]}:{dt[10:12]}"


CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root { --bg:#0d1117; --panel:#161b22; --panel-2:#1c232d; --line:#2a313c; --txt:#e7ecf3; --txt-dim:#8b96a5; --accent:#f5c451; --link:#4d8dff; }
  body { background: radial-gradient(1200px 600px at 80% -10%, rgba(245,196,81,.06), transparent 60%), radial-gradient(900px 500px at -10% 110%, rgba(77,141,255,.06), transparent 60%), var(--bg); font-family:'IBM Plex Sans KR',sans-serif; color:var(--txt); min-height:100vh; display:flex; justify-content:center; padding:32px 18px 56px; }
  .wrap { width:100%; max-width:560px; }
  .top-label { font-size:12px; letter-spacing:.22em; color:var(--txt-dim); text-transform:uppercase; margin-bottom:6px; }
  .title { font-family:'Bebas Neue',sans-serif; font-size:44px; line-height:.95; letter-spacing:.02em; }
  .title .kr { font-family:'IBM Plex Sans KR'; font-weight:700; font-size:24px; display:block; letter-spacing:-.01em; margin-top:4px; }
  .date { font-size:12px; color:var(--txt-dim); margin-top:8px; }
  .nav { margin:14px 0 26px; display:flex; gap:8px; flex-wrap:wrap; }
  .nav a { font-size:13px; color:var(--link); text-decoration:none; padding:7px 14px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }
  .nav a:hover { border-color:var(--link); }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:18px 20px; margin-bottom:14px; position:relative; overflow:hidden; animation:rise .5s both; }
  .card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--accent); }
  .head { display:flex; align-items:baseline; gap:10px; margin-bottom:11px; }
  .ticker { font-size:16px; font-weight:700; }
  .member { font-size:11px; color:var(--txt-dim); }
  .headline { font-size:15.5px; font-weight:600; line-height:1.45; color:var(--txt); text-decoration:none; display:block; }
  .headline:hover { color:var(--accent); }
  .body { font-size:13px; color:var(--txt-dim); line-height:1.6; margin-top:9px; }
  .meta { font-size:11px; color:var(--txt-dim); margin-top:11px; letter-spacing:.02em; }
  .meta .src { color:#b9c3d1; }
  .empty { font-size:13px; color:var(--txt-dim); margin-top:9px; font-style:italic; }
  .foot { text-align:center; font-size:11px; color:var(--txt-dim); margin-top:22px; letter-spacing:.04em; }
  .auto-stamp { text-align:center; font-size:10px; color:var(--txt-dim); margin-top:6px; opacity:.6; }
  @keyframes rise { from{opacity:0; transform:translateY(12px);} to{opacity:1; transform:none;} }
  .card:nth-child(1){animation-delay:.04s} .card:nth-child(2){animation-delay:.08s}
  .card:nth-child(3){animation-delay:.12s} .card:nth-child(4){animation-delay:.16s}
  .card:nth-child(5){animation-delay:.20s} .card:nth-child(6){animation-delay:.24s}
  .card:nth-child(7){animation-delay:.28s} .card:nth-child(8){animation-delay:.32s}
"""


def build_card(m, news):
    head = f"""<div class="head"><span class="ticker">{m['stock']}</span><span class="member">{m['name']} 보유</span></div>"""
    if not news:
        return f"""  <div class="card">
    {head}
    <div class="empty">최근 뉴스를 불러오지 못했어요.</div>
  </div>"""
    when = fmt_when(news["datetime"])
    meta = f'<span class="src">{news["office"]}</span> · {when}' if when else f'<span class="src">{news["office"]}</span>'
    headline = (
        f'<a class="headline" href="{news["url"]}" target="_blank" rel="noopener">{news["title"]}</a>'
        if news["url"]
        else f'<div class="headline">{news["title"]}</div>'
    )
    return f"""  <div class="card">
    {head}
    {headline}
    <div class="body">{news['body']}</div>
    <div class="meta">{meta}</div>
  </div>"""


def build_html(cards_html, now_kst):
    date_display = now_kst.strftime("%Y.%m.%d")
    stamp = now_kst.strftime("%Y-%m-%d %H:%M KST")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>오늘의 종목 뉴스 · {date_display}</title>
<meta property="og:title" content="오늘의 종목 뉴스 {date_display}">
<meta property="og:description" content="우리 모임 8개 종목 데일리 뉴스 요약">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Gowun+Dodum&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

  <div class="top-label">소수점 투자 모임 · 데일리 종목 뉴스</div>
  <div class="title">NEWS<span class="kr">오늘의 종목 소식</span></div>
  <div class="date">{date_display} 기준 · 종목별 최신 1건</div>

  <div class="nav"><a href="index.html">← 잔고 결산</a><a href="rank.html">📊 순위 변동</a></div>

{cards_html}

  <div class="foot">뉴스는 네이버 증권 제공 · 제목 클릭 시 원문으로 이동 📰</div>
  <div class="auto-stamp">자동 갱신: {stamp}</div>

</div>
</body>
</html>
"""


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cards = []
    for m in data["members"]:
        keywords = [m["stock"]] + ALIASES.get(m["code"], [])
        news = fetch_latest_news(m["code"], keywords)
        if not news:
            mark = "✗"
        elif news["matched"]:
            mark = "✓"
        else:
            mark = "≈"  # 폴백(시장 뉴스)
        print(f"  {mark} {m['stock']} ({m['code']})")
        cards.append(build_card(m, news))
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    html = build_html("\n\n".join(cards), now)
    OUT.write_text(html, encoding="utf-8")
    print(f"✓ {OUT.name} 생성 — {now.strftime('%Y-%m-%d %H:%M KST')}")


if __name__ == "__main__":
    main()
