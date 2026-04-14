import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time
import random

# ─── CONFIGURAÇÕES ───────────────────────────────────────────
PRODUCTS = [
    {"url": "https://a.co/d/02h6RhMB", "label": "Produto 1"},
    {"url": "https://a.co/d/0hltnajZ", "label": "Produto 2"},
    {"url": "https://a.co/d/09rtQ6Ee", "label": "Produto 3"},
]

HISTORY_FILE = "data/history.json"
OUTPUT_HTML  = "index.html"
# ─────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_bsr(url: str) -> dict:
    """Resolve URL curta, busca a página e extrai BSR + título."""
    session = requests.Session()
    try:
        resp = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        final_url = resp.url
        soup = BeautifulSoup(resp.text, "html.parser")

        # Título
        title_tag = soup.select_one("#productTitle")
        title = title_tag.get_text(strip=True) if title_tag else "Sem título"

        # BSR — Amazon usa diferentes estruturas dependendo da categoria
        bsr = None

        # Estratégia 1: detailBullets (lista de detalhes)
        for li in soup.select("#detailBulletsWrapper_feature_div li, #detailBullets_feature_div li"):
            text = li.get_text(" ", strip=True)
            if "Best Seller" in text or "Mais Vendidos" in text or "BSR" in text:
                import re
                match = re.search(r"#([\d,.]+)", text)
                if match:
                    bsr = match.group(1).replace(",", "").replace(".", "")
                    break

        # Estratégia 2: tabela de detalhes do produto
        if not bsr:
            for row in soup.select("#productDetails_detailBullets_sections1 tr, #productDetails_techSpec_section_1 tr"):
                header = row.find("th")
                value  = row.find("td")
                if header and value:
                    if "Best Seller" in header.get_text() or "Mais Vendidos" in header.get_text():
                        import re
                        match = re.search(r"#([\d,.]+)", value.get_text())
                        if match:
                            bsr = match.group(1).replace(",", "").replace(".", "")
                            break

        # Estratégia 3: SalesRank antigo
        if not bsr:
            sr = soup.select_one("#SalesRank")
            if sr:
                import re
                match = re.search(r"#([\d,.]+)", sr.get_text())
                if match:
                    bsr = match.group(1).replace(",", "").replace(".", "")

        return {
            "url": final_url,
            "title": title[:60] + ("..." if len(title) > 60 else ""),
            "bsr": int(bsr) if bsr else None,
            "error": None,
        }

    except Exception as e:
        return {"url": url, "title": "Erro", "bsr": None, "error": str(e)}


def load_history() -> dict:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_history(history: dict):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def generate_html(history: dict):
    now_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

    # Monta cards + sparklines por produto
    cards_html = ""
    for url_key, entries in history.items():
        if not entries:
            continue
        latest  = entries[-1]
        title   = latest.get("title", url_key)
        bsr_val = latest.get("bsr")
        label   = latest.get("label", "")

        bsr_display = f"#{bsr_val:,}" if bsr_val else "N/D"

        # Tendência
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
                    trend = '<span class="trend flat">— Estável</span>'

        # Sparkline (últimos 20 pontos)
        points = [e["bsr"] for e in entries if e.get("bsr")][-20:]
        sparkline = ""
        if len(points) > 1:
            mn, mx = min(points), max(points)
            def scale(v):
                if mx == mn:
                    return 30
                return 60 - int((v - mn) / (mx - mn) * 50)
            coords = " ".join(
                f"{i * (200 // (len(points)-1))},{scale(p)}"
                for i, p in enumerate(points)
            )
            sparkline = f'''
            <svg class="sparkline" viewBox="0 0 200 65" preserveAspectRatio="none">
              <polyline points="{coords}" fill="none" stroke="#f90" stroke-width="2.5"/>
            </svg>'''

        # Tabela de histórico
        rows = ""
        for e in reversed(entries[-15:]):
            b = e.get("bsr")
            ts = e.get("timestamp", "")
            rows += f'<tr><td>{ts}</td><td>{"#"+str(f"{b:,}") if b else "N/D"}</td></tr>'

        cards_html += f"""
        <div class="card">
          <div class="card-header">
            <div>
              <div class="product-label">{label}</div>
              <div class="product-title">{title}</div>
            </div>
            {trend}
          </div>
          <div class="bsr-value">{bsr_display}</div>
          {sparkline}
          <details>
            <summary>Ver histórico ({len(entries)} registros)</summary>
            <table class="history-table">
              <thead><tr><th>Data/Hora</th><th>BSR</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </details>
          <a class="product-link" href="{latest.get('url','#')}" target="_blank">
            Ver na Amazon ↗
          </a>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>BSR Monitor</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0f1117;
      color: #e0e0e0;
      min-height: 100vh;
      padding: 24px 16px;
    }}
    header {{
      text-align: center;
      margin-bottom: 32px;
    }}
    header h1 {{
      font-size: 1.8rem;
      color: #f90;
      letter-spacing: 1px;
    }}
    header p {{
      font-size: 0.85rem;
      color: #888;
      margin-top: 6px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 20px;
      max-width: 1100px;
      margin: 0 auto;
    }}
    .card {{
      background: #1a1d27;
      border: 1px solid #2a2d3a;
      border-radius: 14px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
    }}
    .product-label {{
      font-size: 0.72rem;
      text-transform: uppercase;
      color: #f90;
      letter-spacing: 1px;
      font-weight: 600;
    }}
    .product-title {{
      font-size: 0.9rem;
      color: #ccc;
      margin-top: 4px;
      line-height: 1.3;
    }}
    .bsr-value {{
      font-size: 2.4rem;
      font-weight: 700;
      color: #fff;
      letter-spacing: -1px;
    }}
    .trend {{ font-size: 0.78rem; padding: 4px 10px; border-radius: 20px; white-space: nowrap; font-weight: 600; }}
    .trend.up   {{ background: #0d2e1a; color: #4caf50; }}
    .trend.down {{ background: #2e1010; color: #f44336; }}
    .trend.flat {{ background: #1e1e2e; color: #888; }}
    .sparkline {{ width: 100%; height: 65px; }}
    details summary {{
      font-size: 0.8rem;
      color: #888;
      cursor: pointer;
      user-select: none;
    }}
    .history-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
      font-size: 0.8rem;
    }}
    .history-table th, .history-table td {{
      padding: 5px 8px;
      text-align: left;
      border-bottom: 1px solid #2a2d3a;
    }}
    .history-table th {{ color: #888; font-weight: 500; }}
    .product-link {{
      display: inline-block;
      font-size: 0.78rem;
      color: #f90;
      text-decoration: none;
      margin-top: 4px;
    }}
    .product-link:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <header>
    <h1>📦 BSR Monitor</h1>
    <p>Última atualização: {now_str} · Atualiza às 10h e meia-noite (UTC-3)</p>
  </header>
  <div class="grid">
    {cards_html}
  </div>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML gerado: {OUTPUT_HTML}")


def main():
    history = load_history()
    timestamp = datetime.utcnow().strftime("%d/%m/%Y %H:%M")

    for product in PRODUCTS:
        url = product["url"]
        print(f"🔍 Buscando: {url}")
        result = fetch_bsr(url)
        result["timestamp"] = timestamp
        result["label"]     = product["label"]

        key = url  # usa a URL curta como chave
        if key not in history:
            history[key] = []
        history[key].append(result)

        bsr = result.get("bsr")
        print(f"   → {result['title']} | BSR: {'#'+str(bsr) if bsr else 'não encontrado'}")

        # Pausa aleatória pra não levar ban
        time.sleep(random.uniform(3, 7))

    save_history(history)
    generate_html(history)
    print("✅ Concluído!")


if __name__ == "__main__":
    main()
