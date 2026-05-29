#!/usr/bin/env python3
"""
투자모임 포트폴리오 자동 갱신기 (클라우드 버전)

portfolio.json 읽기 → 네이버 증권에서 현재가 조회 → index.html 생성

시세는 한국거래소(KRX) 종가 기준으로, 키움/네이버 증권과 동일합니다.
GitHub Actions에서 매주 월요일 9AM KST에 자동 실행.
"""

import json
import urllib.request
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent
DATA = ROOT / "portfolio.json"
OUT = ROOT / "index.html"

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def fmt(n):
    return f"{n:,.0f}"


def fmt_pl(n):
    sign = "+" if n > 0 else ("−" if n < 0 else "")
    return f"{sign}{abs(n):,.0f}원"


def fmt_rate(r):
    sign = "+" if r > 0 else ("−" if r < 0 else "")
    return f"{sign}{abs(r):.2f}%"


def _naver_price(code: str) -> float:
    """네이버 증권 종가(KRX 기준 — 키움·네이버와 동일)."""
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    deals = data.get("dealTrendInfos")
    if deals and deals[0].get("closePrice"):
        return float(deals[0]["closePrice"].replace(",", ""))
    for item in data.get("totalInfos", []):
        if item.get("code") == "closePrice":
            return float(str(item["value"]).replace(",", ""))
    raise RuntimeError(f"네이버 응답에 종가 없음: {code}")


def _yahoo_price(code: str, market: str) -> float:
    """야후(yfinance) 종가 — 네이버 실패 시 백업. KS=KOSPI, KQ=KOSDAQ."""
    import yfinance as yf  # 백업 경로에서만 필요

    h = yf.Ticker(f"{code}.{market}").history(period="5d")
    if h.empty:
        raise RuntimeError(f"야후 시세 없음: {code}.{market}")
    return float(h["Close"].iloc[-1])


def fetch_price(code: str, market: str = "") -> float:
    """현재가 조회: 네이버(주력) → 실패 시 야후(백업)."""
    try:
        return _naver_price(code)
    except Exception as e:
        print(f"  ⚠️  네이버 조회 실패({code}): {e} — 야후로 폴백")
        return _yahoo_price(code, market)


def build_rows(members):
    rows = []
    for m in members:
        try:
            price = fetch_price(m["code"], m["market"])
        except Exception as e:
            print(f"⚠️  {m['stock']} 시세 조회 실패: {e} — 매입가로 폴백")
            price = m["avg_price"]
        cur = m["qty"] * price
        pl = cur - m["buy_amount"]
        rate = (pl / m["buy_amount"] * 100) if m["buy_amount"] > 0 else 0
        rows.append({
            "member": m["name"],
            "stock": m["stock"],
            "code": m["code"],
            "qty": m["qty"],
            "avg": m["avg_price"],
            "price": price,
            "buy": m["buy_amount"],
            "cur": cur,
            "pl": pl,
            "rate": rate,
            "mine": m.get("mine", False),
        })
    rows.sort(key=lambda r: r["rate"], reverse=True)
    return rows


def build_card(rank, r):
    direction = "up" if r["pl"] >= 0 else "down"
    if rank in MEDALS:
        rank_html = f'<div class="rank gold"><span class="medal">{MEDALS[rank]}</span></div>'
    else:
        rank_html = f'<div class="rank">{rank}</div>'
    badge = ""
    if rank == 1:
        badge = ' <span class="badge">선두</span>'
    if r["mine"]:
        badge = ' <span class="badge mine">나</span>'
    return f"""  <div class="card {direction}">
    {rank_html}
    <div class="who">
      <div class="name">{r['member']}{badge}</div>
      <div class="stock">{r['stock']} · {fmt(r['price'])}원</div>
      <div class="amt">매입 <b>{fmt(r['buy'])}</b> → 평가 <b>{fmt(r['cur'])}</b></div>
    </div>
    <div class="perf"><div class="rate">{fmt_rate(r['rate'])}</div><div class="pl">{fmt_pl(r['pl'])}</div></div>
  </div>"""


CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root { --bg:#0d1117; --panel:#161b22; --panel-2:#1c232d; --line:#2a313c; --txt:#e7ecf3; --txt-dim:#8b96a5; --up:#ff4d6d; --up-soft:rgba(255,77,109,.12); --down:#4d8dff; --down-soft:rgba(77,141,255,.12); --gold:#f5c451; }
  body { background: radial-gradient(1200px 600px at 80% -10%, rgba(255,77,109,.08), transparent 60%), radial-gradient(900px 500px at -10% 110%, rgba(77,141,255,.07), transparent 60%), var(--bg); font-family:'IBM Plex Sans KR',sans-serif; color:var(--txt); min-height:100vh; display:flex; justify-content:center; padding:32px 18px 56px; }
  .wrap { width:100%; max-width:520px; }
  .top-label { font-size:12px; letter-spacing:.22em; color:var(--txt-dim); text-transform:uppercase; margin-bottom:6px; }
  .title { font-family:'Bebas Neue',sans-serif; font-size:44px; line-height:.95; letter-spacing:.02em; margin-bottom:2px; }
  .title .kr { font-family:'IBM Plex Sans KR'; font-weight:700; font-size:26px; display:block; letter-spacing:-.01em; margin-top:4px; }
  .date { font-size:12px; color:var(--txt-dim); margin-top:8px; }
  .nav { margin:16px 0 4px; }
  .nav a { display:inline-block; font-size:13px; color:var(--gold); text-decoration:none; padding:7px 14px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }
  .nav a:hover { border-color:var(--gold); }
  .summary { margin:22px 0 26px; padding:20px 22px; background:linear-gradient(135deg,var(--panel-2),var(--panel)); border:1px solid var(--line); border-radius:18px; position:relative; overflow:hidden; }
  .summary::after { content:""; position:absolute; right:-40px; top:-40px; width:160px; height:160px; background:radial-gradient(circle,rgba(255,77,109,.25),transparent 70%); }
  .summary.down-summary::after { background:radial-gradient(circle,rgba(77,141,255,.25),transparent 70%); }
  .summary .lbl { font-size:12px; color:var(--txt-dim); letter-spacing:.1em; }
  .summary .total { font-family:'Bebas Neue',sans-serif; font-size:52px; line-height:1; margin:6px 0 2px; }
  .summary .rate { font-size:16px; font-weight:600; }
  .summary.up-summary .total, .summary.up-summary .rate { color:var(--up); }
  .summary.down-summary .total, .summary.down-summary .rate { color:var(--down); }
  .summary .sub { display:flex; gap:24px; margin-top:16px; border-top:1px solid var(--line); padding-top:14px; }
  .summary .sub div span { display:block; }
  .summary .sub .k { font-size:11px; color:var(--txt-dim); margin-bottom:3px; }
  .summary .sub .v { font-size:15px; font-weight:600; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:16px 18px; margin-bottom:12px; display:grid; grid-template-columns:44px 1fr auto; gap:14px; align-items:center; position:relative; overflow:hidden; animation:rise .5s both; }
  .card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px; }
  .card.up::before { background:var(--up); } .card.down::before { background:var(--down); }
  .rank { font-family:'Bebas Neue',sans-serif; font-size:30px; text-align:center; color:var(--txt-dim); line-height:1; }
  .rank.gold { color:var(--gold); } .medal { font-size:22px; }
  .who .name { font-size:17px; font-weight:700; }
  .who .stock { font-size:13px; color:var(--txt-dim); margin-top:3px; }
  .who .amt { font-size:11px; color:var(--txt-dim); margin-top:7px; }
  .who .amt b { color:#b9c3d1; font-weight:500; }
  .perf { text-align:right; } .perf .rate { font-size:21px; font-weight:700; line-height:1; }
  .perf .pl { font-size:12.5px; margin-top:5px; font-weight:500; }
  .up .perf .rate, .up .perf .pl { color:var(--up); } .down .perf .rate, .down .perf .pl { color:var(--down); }
  .badge { display:inline-block; font-size:10px; padding:2px 7px; border-radius:6px; margin-left:6px; vertical-align:middle; background:var(--up-soft); color:var(--up); font-weight:600; }
  .badge.mine { background:rgba(245,196,81,.14); color:var(--gold); }
  .foot { text-align:center; font-size:11px; color:var(--txt-dim); margin-top:22px; letter-spacing:.04em; }
  .auto-stamp { text-align:center; font-size:10px; color:var(--txt-dim); margin-top:6px; opacity:.6; }
  @keyframes rise { from{opacity:0; transform:translateY(12px);} to{opacity:1; transform:none;} }
  .card:nth-child(1){animation-delay:.05s} .card:nth-child(2){animation-delay:.10s}
  .card:nth-child(3){animation-delay:.15s} .card:nth-child(4){animation-delay:.20s}
  .card:nth-child(5){animation-delay:.25s} .card:nth-child(6){animation-delay:.30s}
  .card:nth-child(7){animation-delay:.35s} .card:nth-child(8){animation-delay:.40s}
"""


def build_html(rows, now_kst):
    total_buy = sum(r["buy"] for r in rows)
    total_cur = sum(r["cur"] for r in rows)
    total_pl = sum(r["pl"] for r in rows)
    total_rate = (total_pl / total_buy * 100) if total_buy > 0 else 0
    summary_class = "up-summary" if total_pl >= 0 else "down-summary"
    arrow = "▲" if total_pl >= 0 else "▼"
    date_display = now_kst.strftime("%Y.%m.%d")
    stamp = now_kst.strftime("%Y-%m-%d %H:%M KST")
    cards = "\n\n".join(build_card(i + 1, r) for i, r in enumerate(rows))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>투자 모임 포트폴리오 · {date_display}</title>
<meta property="og:title" content="투자 모임 포트폴리오 {date_display}">
<meta property="og:description" content="총 손익 {fmt_pl(total_pl)} ({fmt_rate(total_rate)})">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Gowun+Dodum&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

  <div class="top-label">소수점 투자 모임 · 키움증권 위탁종합</div>
  <div class="title">PORTFOLIO<span class="kr">우리 모임 잔고 결산</span></div>
  <div class="date">{date_display} 기준 · 8인 참여</div>

  <div class="nav"><a href="news.html">📰 오늘의 종목 뉴스 보기 →</a></div>

{cards}

  <div class="foot">투자의 길, 함께 떠들면 덜 외로워요 🤝</div>
  <div class="auto-stamp">자동 갱신: {stamp}</div>

</div>
</body>
</html>
"""


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    rows = build_rows(data["members"])
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    html = build_html(rows, now)
    OUT.write_text(html, encoding="utf-8")
    total_pl = sum(r["pl"] for r in rows)
    print(f"✓ {OUT.name} 생성")
    print(f"  {now.strftime('%Y-%m-%d %H:%M KST')}")
    print(f"  총 손익 {fmt_pl(total_pl)}")


if __name__ == "__main__":
    main()
