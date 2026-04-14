import json, os, re, time, random
from datetime import datetime
from playwright.sync_api import sync_playwright

PRODUCTS = [
    {"url": "https://a.co/d/02h6RhMB", "label": "Produto 1"},
    {"url": "https://a.co/d/0hltnajZ", "label": "Produto 2"},
    {"url": "https://a.co/d/09rtQ6Ee", "label": "Produto 3"},
]

HISTORY_FILE = "data/history.json"
OUTPUT_HTML = "index.html"


def fetch_bsr(url, page):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(2, 4))

        html = page.content()
        final_url = page.url

        # Titulo
        try:
            title = page.locator("#productTitle").inner_text(timeout=5000).strip()
        except:
            title = "Sem titulo"

        bsr = None

        # Busca "No [numero] em [categoria]" no texto completo da pagina
        full_text = page.inner_text("body")
        matches = re.findall(r'N[^\w]?\s*(\d[\d.]*)\s+em\s+\w', full_text)
        if matches:
            numeros = []
            for m in matches:
                try:
                    numeros.append(int(m.replace(".", "")))
                except:
                    pass
            if numeros:
                bsr = min(numeros)

        # Fallback: busca no HTML
        if not bsr:
            m = re.search(r'"salesRank[^"]*"[^:]*:\s*(\d+)', html)
            if m:
                bsr = int(m.group(1))

        return {
            "url": final_url,
            "title": title[:60] + ("..." if len(title) > 60 else ""),
            "bsr": bsr,
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
        latest = entries[-1]
        title = latest.get("title", url_key)
        bsr_val = latest.get("bsr")
        label = latest.get("label", "")
        bsr_display = f"#{bsr_val:,}".replace(",", ".") if bsr_val else "N/D"

        trend = ""
        if len(entries) >= 2:
            prev = entries[-2].get("bsr")
            curr = bsr_val
            if prev and curr:
                if curr < prev:
                    trend = '<span class="trend up">&#9650; Subiu</span>'
                elif curr > prev:
                    trend = '<span class="trend down">&#9660; Caiu</span>'
                else:
                    trend = '<span class="trend flat">&#8212; Estavel</span>'

        points = [e["bsr"] for e in entries if e.get("bsr")][-20:]
        sparkline = ""
        if len(points) > 1:
            mn, mx = min(points), max(points)
            def scale(v):
                if mx == mn:
                    return 30
                return 60 - int((v - mn) / (mx - mn) * 50)
            coords = " ".join(
                f"{i * (200 // (len(points) - 1))},{scale(p)}"
                for i, p in enumerate(points)
            )
            sparkline = f'<svg class="sparkline" viewBox="0 0 200 65" preserveAspectRatio="none"><polyline points="{coords}" fill="none" stroke="#f90" stroke-width="2.5"/></svg>'

        rows = ""
        for e in reversed(entries[-15:]):
            b = e.get("bsr")
            ts = e.get("timestamp", "")
            b_str = "#" + f"{b:,}".replace(",", ".") if b else "N/D"
            rows += f"<tr><td>{ts}</td><td>{b_str}</td></tr>"

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
            <summary>Ver historico ({len(entries)} registros)</summary>
            <table class="history-table">
              <thead><tr><th>Data/Hora</th><th>BSR</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </details>
          <a class="product-link" href="{latest.get('url', '#')}" target="_blank">Ver na Amazon &#8599;</a>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
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
    .product-link:hover{{text-decoration:underline}}
  </style>
</head>
<body>
  <header>
    <h1>&#128230; BSR Monitor</h1>
    <p>Ultima atualizacao: {now_str} &middot; Atualiza as 10h e meia-noite (UTC-3)</p>
  </header>
  <div class="grid">{cards_html}</div>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML gerado: {OUTPUT_HTML}")


def main():
    history = load_history()
    timestamp = datetime.utcnow().strftime("%d/%m/%Y %H:%M")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="pt-BR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        for product in PRODUCTS:
            url = product["url"]
            print(f"Buscando: {url}")
            result = fetch_bsr(url, page)
            result["timestamp"] = timestamp
            result["label"] = product["label"]

            if url not in history:
                history[url] = []
            history[url].append(result)

            bsr = result.get("bsr")
            print(f"   -> {result['title']} | BSR: {'#' + str(bsr) if bsr else 'nao encontrado'}")
            time.sleep(random.uniform(3, 6))

        browser.close()

    save_history(history)
    generate_html(history)
    print("Concluido!")


if __name__ == "__main__":
    main()
