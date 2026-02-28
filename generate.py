import requests
import json
import os
from datetime import datetime, timezone, timedelta

TOKEN = os.environ.get("SYMPLA_TOKEN")
EVENT_ID = "3315673"
BRT = timezone(timedelta(hours=-3))

CUPONS_MAP = {
    "BemVindoSPIW26": "Marktech Meta",
    "SPIW2026": "Marktech Google",
    "EBEstadao": "EBEstadao",
    "EmmRIW": "EmmRIW",
}
CUPONS = ["Orgânico", "Marktech Meta", "Marktech Google", "EBEstadao", "EmmRIW"]
COLORS = ["#00d9ff", "#9b5cf6", "#4d9fff", "#ff8c42", "#ff4dab"]


def get_all_participants():
    participants = []
    page = 1
    while True:
        url = f"https://api.sympla.com.br/public/v3/events/{EVENT_ID}/participants"
        r = requests.get(url, headers={"s-token": TOKEN}, params={"page_size": 200, "page": page})
        data = r.json()
        items = data.get("data", [])
        if not items:
            break
        participants.extend(items)
        if not data.get("pagination", {}).get("has_next", False):
            break
        page += 1
    return participants


def classify_cupom(p):
    disc = p.get("discount_code_name", "") or ""
    for code, name in CUPONS_MAP.items():
        if code in disc:
            return name
    return "Orgânico"


def process(participants):
    by_day = {}
    by_origin = {c: {"t": 0, "c": 0, "p": 0, "r": 0} for c in CUPONS}
    total = {"t": 0, "c": 0, "p": 0}

    for p in participants:
        created = p.get("created_date", "") or p.get("updated_date", "") or ""
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(BRT)
            dia = dt.strftime("%d/%m")
        except:
            dia = "??"

        cupom = classify_cupom(p)
        status = p.get("order_status", "")
        confirmado = status in ("A", "approved", "Aprovado")
        valor = float(p.get("amount", 0) or 0)

        if dia not in by_day:
            by_day[dia] = {"total": 0, "confirmados": 0, "pendentes": 0, "orig": {}}
        if cupom not in by_day[dia]["orig"]:
            by_day[dia]["orig"][cupom] = {"t": 0, "c": 0, "p": 0}

        by_day[dia]["total"] += 1
        by_origin[cupom]["t"] += 1
        total["t"] += 1

        if confirmado:
            by_day[dia]["confirmados"] += 1
            by_day[dia]["orig"][cupom]["c"] += 1
            by_origin[cupom]["c"] += 1
            by_origin[cupom]["r"] += valor
            total["c"] += 1
        else:
            by_day[dia]["pendentes"] += 1
            by_day[dia]["orig"][cupom]["p"] += 1
            by_origin[cupom]["p"] += 1
            total["p"] += 1

    return by_day, by_origin, total


def fmt_brl(v):
    s = f"{v:,.0f}".replace(",", ".")
    return f"R$ {s}"


def generate_html(by_day, by_origin, total):
    now = datetime.now(BRT)
    ts = now.strftime("%d/%m/%Y · %Hh%M")
    dias = sorted(by_day.keys())
    ndias = len(dias)
    rec_conf = sum(by_origin[c]["r"] for c in CUPONS)
    taxa = round(total["c"] / total["t"] * 100) if total["t"] else 0

    orig_data = {}
    for c in CUPONS:
        o = by_origin[c]
        if o["t"] > 0:
            orig_data[c] = {"t": o["t"], "c": o["c"], "p": o["p"], "r": fmt_brl(o["r"])}

    # Inject data as JSON into template
    dias_json = json.dumps(dias, ensure_ascii=False)
    by_day_json = json.dumps(by_day, ensure_ascii=False)
    orig_json = json.dumps(orig_data, ensure_ascii=False)
    cupons_json = json.dumps(CUPONS, ensure_ascii=False)
    colors_json = json.dumps(COLORS)

    html = open("template.html").read()
    html = html.replace("__TIMESTAMP__", ts)
    html = html.replace("__TOTAL__", str(total["t"]))
    html = html.replace("__CONF__", str(total["c"]))
    html = html.replace("__PEND__", str(total["p"]))
    html = html.replace("__TAXA__", str(taxa))
    html = html.replace("__RECEITA__", fmt_brl(rec_conf))
    html = html.replace("__NDIAS__", str(ndias))
    html = html.replace("__DIAS_JSON__", dias_json)
    html = html.replace("__BY_DAY_JSON__", by_day_json)
    html = html.replace("__ORIG_JSON__", orig_json)
    html = html.replace("__CUPONS_JSON__", cupons_json)
    html = html.replace("__COLORS_JSON__", colors_json)
    return html


if __name__ == "__main__":
    print("Buscando participantes...")
    participants = get_all_participants()
    print(f"Total: {len(participants)}")
    by_day, by_origin, total = process(participants)
    html = generate_html(by_day, by_origin, total)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html gerado com sucesso!")
