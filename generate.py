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
HISTORY = ROOT / "history.json"
RANK_OUT = ROOT / "rank.html"

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

# 추이 차트 종목별 라인 색상(최대 8개 순환).
LINE_COLORS = [
    "#ff4d6d", "#4d8dff", "#f5c451", "#3ddc97",
    "#b78bff", "#ff9f43", "#5ad1e6", "#e85d9e",
]


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


def week_key(dt):
    """ISO 주차 키 — 같은 주 재실행 시 스냅샷을 덮어쓰기 위한 식별자. 예: '2026-W22'."""
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def load_history():
    if not HISTORY.exists():
        return {"snapshots": []}
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except Exception:
        return {"snapshots": []}


def update_history(rows, now_kst):
    """이번 주 순위 스냅샷을 history.json에 기록(같은 주면 갱신). 갱신된 history 반환."""
    hist = load_history()
    snaps = hist.setdefault("snapshots", [])
    snap = {
        "week": week_key(now_kst),
        "date": now_kst.strftime("%Y-%m-%d"),
        "ranks": [
            {"stock": r["stock"], "member": r["member"],
             "rank": i + 1, "rate": round(r["rate"], 2)}
            for i, r in enumerate(rows)
        ],
    }
    if snaps and snaps[-1]["week"] == snap["week"]:
        snaps[-1] = snap  # 같은 주 재실행 → 덮어쓰기
    else:
        snaps.append(snap)
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    return hist


def _delta_html(cur_rank, prev_rank):
    """전주 대비 순위 변동 칩 HTML."""
    if prev_rank is None:
        return '<span class="delta new">NEW</span>'
    diff = prev_rank - cur_rank  # 양수 = 순위 상승
    if diff > 0:
        return f'<span class="delta up">▲{diff}</span>'
    if diff < 0:
        return f'<span class="delta down">▼{abs(diff)}</span>'
    return '<span class="delta flat">−</span>'


def build_rank_table(rows, hist):
    snaps = hist["snapshots"]
    # 직전 주(이번 주 스냅샷을 제외한 마지막)의 종목별 순위.
    prev = {}
    if len(snaps) >= 2:
        for e in snaps[-2]["ranks"]:
            prev[e["stock"]] = e["rank"]
    trs = []
    for i, r in enumerate(rows):
        rank = i + 1
        medal = MEDALS.get(rank, "")
        rank_cell = f'{medal} {rank}' if medal else f'{rank}'
        rate_cls = "up" if r["rate"] >= 0 else "down"
        delta = _delta_html(rank, prev.get(r["stock"]))
        trs.append(
            f'    <tr>'
            f'<td class="c-rank">{rank_cell}</td>'
            f'<td class="c-stock"><b>{r["stock"]}</b><span class="mem">{r["member"]}</span></td>'
            f'<td class="c-rate {rate_cls}">{fmt_rate(r["rate"])}</td>'
            f'<td class="c-delta">{delta}</td>'
            f'</tr>'
        )
    return (
        '  <table class="rank-table">\n'
        '    <thead><tr><th>순위</th><th>종목</th><th>수익률</th><th>전주대비</th></tr></thead>\n'
        '    <tbody>\n' + "\n".join(trs) + '\n    </tbody>\n'
        '  </table>'
    )


def build_trend_svg(hist):
    """주차별 순위 추이 라인 차트(인라인 SVG). 1위가 맨 위."""
    snaps = hist["snapshots"]
    # 색상은 현재(마지막) 스냅샷의 순위 순서대로 종목에 고정 배정.
    stocks = [e["stock"] for e in snaps[-1]["ranks"]]
    color = {s: LINE_COLORS[i % len(LINE_COLORS)] for i, s in enumerate(stocks)}
    n = len(stocks)
    W = len(snaps)

    pad_l, pad_r, pad_t, pad_b = 30, 14, 16, 28
    row_h = 24
    plot_h = max((n - 1) * row_h, row_h)
    plot_w = max(180, (W - 1) * 96) if W > 1 else 180
    vb_w = pad_l + plot_w + pad_r
    vb_h = pad_t + plot_h + pad_b

    def x(i):
        return pad_l + (plot_w / 2 if W == 1 else i / (W - 1) * plot_w)

    def y(rank):
        return pad_t + (0 if n == 1 else (rank - 1) / (n - 1) * plot_h)

    parts = [f'<svg viewBox="0 0 {vb_w:.0f} {vb_h:.0f}" class="trend" role="img" aria-label="순위 추이">']
    # 가로 격자 + 순위 라벨.
    for rank in range(1, n + 1):
        yy = y(rank)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l + plot_w}" y2="{yy:.1f}" class="grid"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{yy + 3:.1f}" class="ylab">{rank}</text>')
    # 세로 주차 라벨.
    for i, s in enumerate(snaps):
        parts.append(f'<text x="{x(i):.1f}" y="{vb_h - 9:.0f}" class="xlab">{s["date"][5:]}</text>')
    # 라인이 좌→우로 그려지는 시간(초). 점은 이 흐름에 맞춰 순서대로 등장.
    draw_dur = 1.2

    # 종목별 라인 + 점. (점은 주차 인덱스 i를 보존해 등장 딜레이 계산)
    for stock in stocks:
        pts = []
        for i, s in enumerate(snaps):
            rk = next((e["rank"] for e in s["ranks"] if e["stock"] == stock), None)
            if rk is not None:
                pts.append((i, x(i), y(rk)))
        if not pts:
            continue
        c = color[stock]
        if len(pts) >= 2:
            poly = " ".join(f"{px:.1f},{py:.1f}" for _, px, py in pts)
            # pathLength="1" → dash 애니메이션을 길이와 무관하게 정규화.
            parts.append(f'<polyline class="line" pathLength="1" points="{poly}" fill="none" stroke="{c}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
        for i, px, py in pts:
            frac = 0 if W <= 1 else i / (W - 1)
            delay = 0.15 + frac * draw_dur
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{c}" style="animation-delay:{delay:.2f}s"/>')
    parts.append('</svg>')

    legend = '<div class="legend">' + "".join(
        f'<span class="lg"><i style="background:{color[s]}"></i>{s}</span>' for s in stocks
    ) + '</div>'
    return "\n".join(parts) + "\n" + legend


RANK_CSS = """
  * { margin:0; padding:0; box-sizing:border-box; }
  :root { --bg:#0d1117; --panel:#161b22; --panel-2:#1c232d; --line:#2a313c; --txt:#e7ecf3; --txt-dim:#8b96a5; --up:#ff4d6d; --down:#4d8dff; --gold:#f5c451; }
  body { background: radial-gradient(1200px 600px at 80% -10%, rgba(245,196,81,.06), transparent 60%), radial-gradient(900px 500px at -10% 110%, rgba(77,141,255,.06), transparent 60%), var(--bg); font-family:'IBM Plex Sans KR',sans-serif; color:var(--txt); min-height:100vh; display:flex; justify-content:center; padding:32px 18px 56px; }
  .wrap { width:100%; max-width:560px; }
  .top-label { font-size:12px; letter-spacing:.22em; color:var(--txt-dim); text-transform:uppercase; margin-bottom:6px; }
  .title { font-family:'Bebas Neue',sans-serif; font-size:44px; line-height:.95; letter-spacing:.02em; }
  .title .kr { font-family:'IBM Plex Sans KR'; font-weight:700; font-size:24px; display:block; letter-spacing:-.01em; margin-top:4px; }
  .date { font-size:12px; color:var(--txt-dim); margin-top:8px; }
  .nav { margin:14px 0 24px; display:flex; gap:8px; flex-wrap:wrap; }
  .nav a { font-size:13px; color:var(--link,#4d8dff); text-decoration:none; padding:7px 14px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }
  .nav a:hover { border-color:#4d8dff; }
  .section-h { font-size:13px; color:var(--txt-dim); letter-spacing:.04em; margin:0 2px 10px; }
  .rank-table { width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:14px; overflow:hidden; }
  .rank-table th { font-size:11px; color:var(--txt-dim); font-weight:500; text-align:left; padding:11px 14px; border-bottom:1px solid var(--line); letter-spacing:.04em; }
  .rank-table td { padding:13px 14px; border-bottom:1px solid var(--line); font-size:14px; }
  .rank-table tr:last-child td { border-bottom:none; }
  .c-rank { font-family:'Bebas Neue',sans-serif; font-size:19px; width:54px; color:var(--gold); }
  .c-stock b { font-weight:700; } .c-stock .mem { display:block; font-size:11px; color:var(--txt-dim); margin-top:2px; }
  .c-rate { font-weight:700; text-align:right; } .c-rate.up { color:var(--up); } .c-rate.down { color:var(--down); }
  .c-delta { text-align:right; width:74px; }
  .delta { font-size:12.5px; font-weight:700; padding:3px 8px; border-radius:7px; }
  .delta.up { color:var(--up); background:rgba(255,77,109,.12); }
  .delta.down { color:var(--down); background:rgba(77,141,255,.12); }
  .delta.flat { color:var(--txt-dim); }
  .delta.new { color:var(--gold); background:rgba(245,196,81,.13); font-size:11px; }
  .chart-box { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px 14px 12px; margin-top:24px; }
  .trend { width:100%; height:auto; display:block; }
  .trend .grid { stroke:var(--line); stroke-width:1; }
  .trend .ylab { fill:var(--txt-dim); font-size:10px; text-anchor:end; font-family:'Bebas Neue',sans-serif; }
  .trend .xlab { fill:var(--txt-dim); font-size:9px; text-anchor:middle; }
  .trend .line { stroke-dasharray:1; stroke-dashoffset:1; animation:draw 1.2s ease forwards; }
  .trend circle { opacity:0; transform-box:fill-box; transform-origin:center; animation:pop .45s cubic-bezier(.34,1.56,.64,1) forwards; }
  @keyframes draw { to { stroke-dashoffset:0; } }
  @keyframes pop { 0% { opacity:0; transform:scale(.2); } 60% { opacity:1; transform:scale(1.35); } 100% { opacity:1; transform:scale(1); } }
  @media (prefers-reduced-motion: reduce) {
    .trend .line { animation:none; stroke-dashoffset:0; }
    .trend circle { animation:none; opacity:1; transform:none; }
  }
  .legend { display:flex; flex-wrap:wrap; gap:9px 14px; margin-top:12px; padding-top:12px; border-top:1px solid var(--line); }
  .lg { font-size:11.5px; color:var(--txt-dim); display:inline-flex; align-items:center; gap:5px; }
  .lg i { width:11px; height:3px; border-radius:2px; display:inline-block; }
  .note { font-size:12px; color:var(--txt-dim); margin-top:12px; font-style:italic; text-align:center; }
  .foot { text-align:center; font-size:11px; color:var(--txt-dim); margin-top:24px; letter-spacing:.04em; }
  .auto-stamp { text-align:center; font-size:10px; color:var(--txt-dim); margin-top:6px; opacity:.6; }
"""


def build_rank_html(rows, hist, now_kst):
    date_display = now_kst.strftime("%Y.%m.%d")
    stamp = now_kst.strftime("%Y-%m-%d %H:%M KST")
    table = build_rank_table(rows, hist)
    n_weeks = len(hist["snapshots"])
    if n_weeks >= 2:
        chart = (
            '  <div class="section-h">📈 주차별 순위 추이 (1위가 맨 위)</div>\n'
            f'  <div class="chart-box">\n{build_trend_svg(hist)}\n  </div>'
        )
    else:
        chart = (
            '  <div class="section-h">📈 주차별 순위 추이</div>\n'
            f'  <div class="chart-box">\n{build_trend_svg(hist)}\n'
            '    <div class="note">이번 주가 기준선이에요. 다음 주부터 순위 선이 이어집니다 🌱</div>\n'
            '  </div>'
        )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>순위 변동 · {date_display}</title>
<meta property="og:title" content="순위 변동 {date_display}">
<meta property="og:description" content="우리 모임 종목별 주차 순위 변동">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Gowun+Dodum&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{RANK_CSS}</style>
</head>
<body>
<div class="wrap">

  <div class="top-label">소수점 투자 모임 · 순위 변동</div>
  <div class="title">RANKING<span class="kr">주차별 순위 변동</span></div>
  <div class="date">{date_display} 기준 · {n_weeks}주차 누적 · 수익률 순</div>

  <div class="nav"><a href="index.html">← 잔고 결산</a><a href="news.html">📰 종목 뉴스</a></div>

  <div class="section-h">🏆 이번 주 순위</div>
{table}

{chart}

  <div class="foot">매주 월요일 자동 갱신 · 순위는 수익률 기준 📊</div>
  <div class="auto-stamp">자동 갱신: {stamp}</div>

</div>
</body>
</html>
"""


CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root { --bg:#0d1117; --panel:#161b22; --panel-2:#1c232d; --line:#2a313c; --txt:#e7ecf3; --txt-dim:#8b96a5; --up:#ff4d6d; --up-soft:rgba(255,77,109,.12); --down:#4d8dff; --down-soft:rgba(77,141,255,.12); --gold:#f5c451; }
  body { background: radial-gradient(1200px 600px at 80% -10%, rgba(255,77,109,.08), transparent 60%), radial-gradient(900px 500px at -10% 110%, rgba(77,141,255,.07), transparent 60%), var(--bg); font-family:'IBM Plex Sans KR',sans-serif; color:var(--txt); min-height:100vh; display:flex; justify-content:center; padding:32px 18px 56px; }
  .wrap { width:100%; max-width:520px; }
  .top-label { font-size:12px; letter-spacing:.22em; color:var(--txt-dim); text-transform:uppercase; margin-bottom:6px; }
  .title { font-family:'Bebas Neue',sans-serif; font-size:44px; line-height:.95; letter-spacing:.02em; margin-bottom:2px; }
  .title .kr { font-family:'IBM Plex Sans KR'; font-weight:700; font-size:26px; display:block; letter-spacing:-.01em; margin-top:4px; }
  .date { font-size:12px; color:var(--txt-dim); margin-top:8px; }
  .nav { margin:16px 0 4px; display:flex; gap:8px; flex-wrap:wrap; }
  .nav a { font-size:13px; color:var(--gold); text-decoration:none; padding:7px 14px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }
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

  <div class="nav"><a href="news.html">📰 오늘의 종목 뉴스</a><a href="rank.html">📊 순위 변동</a></div>

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

    # 이번 주 순위 스냅샷 기록 후 순위 변동 페이지 생성.
    hist = update_history(rows, now)
    RANK_OUT.write_text(build_rank_html(rows, hist, now), encoding="utf-8")

    total_pl = sum(r["pl"] for r in rows)
    print(f"✓ {OUT.name} 생성")
    print(f"✓ {RANK_OUT.name} 생성 — {len(hist['snapshots'])}주차 누적")
    print(f"  {now.strftime('%Y-%m-%d %H:%M KST')}")
    print(f"  총 손익 {fmt_pl(total_pl)}")


if __name__ == "__main__":
    main()
