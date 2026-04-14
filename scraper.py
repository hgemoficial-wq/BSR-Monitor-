import requests
from bs4 import BeautifulSoup
import json, os, re, time, random
from datetime import datetime

PRODUCTS = [
    {"url": "https://a.co/d/02h6RhMB", "label": "Produto 1"},
    {"url": "https://a.co/d/0hltnajZ", "label": "Produto 2"},
    {"url": "https://a.co/d/09rtQ6Ee", "label": "Produto 3"},
]

HISTORY_FILE = "data/history.json"
OUTPUT_HTML  = "index.html"

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15", "Accept-Language": "pt-BR,pt;q=0.9", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
]

def fetch_bsr(url):
    session = requests.Session()
    headers = random.choice(HEADERS_LIST)
    try:
        resp = session.get(url, headers=headers, timeout=20, allow_redirects=True)
        final_url = resp.url
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.select_one("#productTitle")
        title = title_tag.get_text(strip=True) if title_tag else "Sem titulo"

        bsr = None

        # Formato Brasil: "No 272 em Cozinha" ou "Nº 14 em Potes"
        patterns = [
            r'N[oº°]\s*\.?\s*([\d.]+)\s*em\s',
            r'#([\d,]+)',
            r'rank[^\d]*([\d.]+)',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                bsr = re.sub(r'[.,]', '', m.group(1))
                break

        # Fallback: busca na tabela de especificacoes
        if not bsr:
            for row in soup.select("tr"):
                header = row.find("th") or row.find("td")
                value = row.find_all("td")
                if header and "Ranking" in header.get_text():
                    txt = row.get_text(" ", strip=True)
                    m = re.search(r'N[oº°°]\s*\.?\s*([\d.]+)', txt)
                    if m:
                        bsr = re.sub(r'[.]', '', m.group(1))
                        break

        return {
            "url": final_url,
            "title": title[:60] + ("..." if len(title) > 60 else ""),
            "bsr": int(bsr) if bsr else None,
            "error": None,
        }
    except Exception as e:
        return {"url": url, "title": "Erro", "bsr": None, "error": str(e)}

def load_history():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def generate_html(history):
    now_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    cards_html = ""
    for url_key, entries in history.items():
        if not entries:
            continue
        latest  = entries[-1]
        title   = latest.get("title", url_key)
        bsr_val = latest.get("bsr")
        label   = latest.get("label", "")
        bsr_display = f"#{bsr_val:,}" if bsr_val else "N/D"

        trend = ""
        if len(entries) >= 2:
            prev = entries[-2].get("bsr")
            curr = bsr_val
            if prev and curr:
                if curr < prev:
                    trend = '<span class="trend up">▲ Subiu</span>'
                elif curr > prev:
                    trend = '<span class="trend down">▼ Caiu</span>'
                else:
                    trend = '<span class="trend flat">— Estavel</span>'

        points = [e["bsr"] for e in entries if e.get("bsr")][-20:]
        sparkline = ""
        if len(points) > 1:
            mn, mx = min(points), max(points)
            def scale(v):
                if mx == mn: return 30
                return 60 - int((v - mn) / (mx - mn) * 50)
            coords = " ".join(f"{i*(200//(len(points)-1))},{scale(p)}" for i,p in enumerate(points))
            sparkline = f'<svg class="sparkline" viewBox="0 0 200 65" preserveAspectRatio="none"><polyline points="{coords}" fill="none" stroke="#f90" stroke-width="2.5"/></svg>'

        rows = ""
        for e in reversed(entries[-15:]):
            b = e.get("bsr")
            ts = e.get("timestamp","")
            rows += f'<tr><td>{ts}</td><td>{"#"+f"{b:,}" if b else "N/D"}</td></tr>'

        cards_html += f"""
        <div class="card">
          <div class="card-header"><div><div class="product-label">{label}</div><div class="product-title">{title}</div></div>{trend}</div>
          <div class="bsr-value">{bsr_display}</div>
          {sparkline}
          <details><summary>Ver historico ({len(entries)} registros)</summary>
          <table class="history-table"><thead><tr><th>Data/Hora</th><th>BSR</th></tr></thead><tbody>{rows}</tbody></table></details>
          <a class="product-link" href="{latest.get('url','#')}" target="_blank">Ver na Amazon ↗</a>
        </div>"""

    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>BSR Monitor</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e0e0e0;min-height:100vh;padding:24px 16px}}
header{{text-align:center;margin-bottom:32px}}
header h1{{font-size:1.8rem;color:#f90;letter-spacing:1px}}
header p{{font-size:.85rem;color:#888;margin-top:6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px;max-width:1100px;margin:0 auto}}
.card{{background:#1a1d27;border:1px solid #2a2d3a;border-radius:14px;padding:20px;display:flex;flex-direction:column;gap:12px}}
.card-header{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}}
.product-label{{font-size:.72rem;text-transform:uppercase;color:#f90;letter-spacing:1px;font-weight:600}}
.product-title{{font-size:.9rem;color:#ccc;margin-top:4px;line-height:1.3}}
.bsr-value{{font-size:2.4rem;font-weight:700;color:#fff;letter-spacing:-1px}}
.trend{{font-size:.78rem;padding:4px 10px;border-radius:20px;white-space:nowrap;font-weight:600}}
.trend.up{{background:#0d2e1a;color:#4caf50}}
.trend.down{{background:#2e1010;color:#f44336}}
.trend.flat{{background:#1e1e2e;color:#888}}
.sparkline{{width:100%;height:65px}}
details summary{{font-size:.8rem;color:#888;cursor:pointer;user-select:none}}
.history-table{{width:100%;border-collapse:collapse;margin-top:10px;font-size:.8rem}}
.history-table th,.history-table td{{padding:5px 8px;text-align:left;border-bottom:1px solid #2a2d3a}}
.history-table th{{color:#888;font-weight:500}}
.product-link{{display:inline-block;font-size:.78rem;color:#f90;text-decoration:none;margin-top:4px}}
</style></head>
<body>
<header><h1>📦 BSR Monitor</h1><p>Ultima atualizacao: {now_str} · Atualiza as 10h e meia-noite (UTC-3)</p></header>
<div class="grid">{cards_html}</div>
</body></html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    history = load_history()
    timestamp = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
    for product in PRODUCTS:
        url = product["url"]
        print(f"Buscando: {url}")
        result = fetch_bsr(url)
        result["timestamp"] = timestamp
        result["label"] = product["label"]
        if url not in history:
            history[url] = []
        history[url].append(result)
        bsr = result.get("bsr")
        print(f"   -> {result['title']} | BSR: {'#'+str(bsr) if bsr else 'nao encontrado'}")
        time.sleep(random.uniform(4, 9))
    save_history(history)
    generate_html(history)
    print("Concluido!")

if __name__ == "__main__":
    main()
