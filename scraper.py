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
OUTPUT_HTML = "index.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_bsr(url):
    try:
        session = requests.Session()
        resp = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Titulo do produto
        title_tag = soup.select_one("#productTitle")
        title = title_tag.get_text(strip=True) if title_tag else "Sem titulo"

        bsr = None

        # Procura a linha exata de "Ranking dos mais vendidos" na pagina
        for tag in soup.find_all(["td", "th", "span", "li"]):
            texto = tag.get_text(" ", strip=True)
            if "Ranking dos mais vendidos" in texto or "mais vendidos" in texto.lower():
                # Pega o numero que vem logo apos "No" ou "N\u00ba"
                m = re.search(r'N[oO\u00ba\u00b0]\s*\.?\s*([\d.]+)', texto)
                if m:
                    bsr = int(m.group(1).replace(".", ""))
                    break

        return {
            "url": resp.url,
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
            rows += f"<tr><td>{ts}</td><td>{b
