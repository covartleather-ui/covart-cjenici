#!/usr/bin/env python3
import csv
import json
import os
import shutil
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "current"
ARCHIVE = ROOT / "archive"
STATE_FILE = ROOT / "state.json"
TZ = ZoneInfo("Europe/Zagreb")

SHOP = os.environ.get("SHOPIFY_SHOP", "6ffdpq-40.myshopify.com")
TOKEN = os.environ.get("SHOPIFY_ADMIN_ACCESS_TOKEN", "")
API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-07")
EVENT_NAME = os.environ.get("GITHUB_EVENT_NAME", "")
SCHEDULE_CRON = os.environ.get("SCHEDULE_CRON", "")

PRODUCT_HEADER = [
    "naziv", "sifra", "marka", "jedinica_mjere", "cijena_za_jedinicu_mjere",
    "maloprodajna_cijena", "poseban_oblik_prodaje",
    "naziv_posebnog_oblika_prodaje", "sidrena_cijena", "barkod", "dostupnost",
]
SERVICE_HEADER = [
    "naziv_usluge", "maloprodajna_cijena", "poseban_oblik_prodaje",
    "naziv_posebnog_oblika_prodaje", "sidrena_cijena",
]

QUERY = r"""
query CovartPriceLists {
  products(first: 250, query: "status:active") {
    nodes {
      title
      vendor
      variants(first: 250) {
        nodes {
          sku
          barcode
          price
          compareAtPrice
          availableForSale
          anchor: metafield(namespace: "custom", key: "anchor_price") { value }
        }
      }
    }
  }
  service: metaobjects(type: "covart_service_price", first: 250) {
    nodes {
      name: field(key: "name") { value }
      current: field(key: "current_price") { value }
      anchor: field(key: "anchor_price") { value }
      special: field(key: "special_sale") { value }
      specialName: field(key: "special_sale_name") { value }
      active: field(key: "active") { value }
    }
  }
  workshop: metaobjects(type: "covart_workshop_product", first: 250) {
    nodes {
      name: field(key: "name") { value }
      sku: field(key: "sku") { value }
      brand: field(key: "brand") { value }
      unit: field(key: "unit") { value }
      current: field(key: "current_price") { value }
      anchor: field(key: "anchor_price") { value }
      special: field(key: "special_sale") { value }
      specialName: field(key: "special_sale_name") { value }
      barcode: field(key: "barcode") { value }
      availability: field(key: "availability") { value }
      active: field(key: "active") { value }
    }
  }
}
"""

def stop(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)

def money(value):
    if value is None:
        return None
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict) and "amount" in parsed:
            return float(parsed["amount"])
    except (json.JSONDecodeError, TypeError):
        pass
    return float(value)

def dec(value):
    if value is None:
        stop("Missing required monetary value")
    return f"{float(value):.2f}"

def field(node, name, default=""):
    part = node.get(name)
    if not part:
        return default
    return part.get("value", default)

def graphql():
    if not TOKEN:
        stop("SHOPIFY_ADMIN_ACCESS_TOKEN secret is not configured")
    url = f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json"
    payload = json.dumps({"query": QUERY}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": TOKEN,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        stop(f"Shopify request failed: {exc}")
    if result.get("errors"):
        stop("Shopify GraphQL returned errors: " + json.dumps(result["errors"], ensure_ascii=False))
    return result["data"]

def is_valid_schedule(now):
    if EVENT_NAME != "schedule":
        return True
    offset = int(now.utcoffset().total_seconds() // 3600)
    valid_hours = {2: {"5"}, 1: {"6"}}
    cron_hour = SCHEDULE_CRON.split()[1] if len(SCHEDULE_CRON.split()) >= 2 else ""
    return cron_hour in valid_hours.get(offset, set())

def load_state():
    if not STATE_FILE.exists():
        return {"last_sequence": 0, "last_date": None, "last_publication": None}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))

def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, delimiter=";", lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)

def xml_doc(root_name, attrs, item_name, header, rows):
    root = ET.Element(root_name, attrs)
    for row in rows:
        item = ET.SubElement(root, item_name)
        for key in header:
            child = ET.SubElement(item, key)
            child.text = str(row.get(key, ""))
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"

def validate_csv(path, expected_rows, header):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    if len(rows) != expected_rows:
        stop(f"{path}: expected {expected_rows} rows, got {len(rows)}")
    if not rows:\n        stop(f"{path}: CSV contains no data rows")\n    if list(rows[0].keys()) != header:\n        stop(f"{path}: unexpected CSV header")

def validate_xml(path, item_name, expected_rows):
    tree = ET.parse(path)
    count = len(tree.getroot().findall(item_name))
    if count != expected_rows:
        stop(f"{path}: expected {expected_rows} XML items, got {count}")

def clean_current():
    CURRENT.mkdir(parents=True, exist_ok=True)
    for p in CURRENT.iterdir():
        if p.is_file() and p.suffix.lower() in {".csv", ".xml"}:
            p.unlink()

def prune_archive(now):
    cutoff = now.date() - timedelta(days=40)
    if not ARCHIVE.exists():
        return
    for p in ARCHIVE.iterdir():
        if not p.is_dir():
            continue
        try:
            day = datetime.strptime(p.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day < cutoff:
            shutil.rmtree(p)

def main():
    now = datetime.now(TZ)
    if not is_valid_schedule(now):
        print(f"Skipping inactive DST schedule slot: {SCHEDULE_CRON}")
        return

    state = load_state()
    today = now.date().isoformat()
    if EVENT_NAME == "schedule" and state.get("last_date") == today:
        print(f"Today's publication already exists ({today}); fallback run skipped.")
        return

    data = graphql()
    products = []
    for p in data["products"]["nodes"]:
        for v in p["variants"]["nodes"]:
            price = float(v["price"])
            compare = float(v["compareAtPrice"]) if v.get("compareAtPrice") is not None else None
            sale = compare is not None and compare > price
            anchor = money(v.get("anchor", {}).get("value") if v.get("anchor") else None)
            if not v.get("sku") or not v.get("barcode") or anchor is None:
                stop(f"Missing SKU/barcode/anchor price for Shopify variant in product: {p['title']}")
            products.append({
                "naziv": p["title"],
                "sifra": v["sku"],
                "marka": p.get("vendor") or "Covart",
                "jedinica_mjere": "kom",
                "cijena_za_jedinicu_mjere": dec(price),
                "maloprodajna_cijena": dec(price),
                "poseban_oblik_prodaje": "DA" if sale else "NE",
                "naziv_posebnog_oblika_prodaje": "Sniženje" if sale else "",
                "sidrena_cijena": dec(anchor),
                "barkod": v["barcode"],
                "dostupnost": "DOSTUPNO" if v["availableForSale"] else "NEDOSTUPNO",
            })

    workshop_only = []
    for n in data["workshop"]["nodes"]:
        if field(n, "active") != "true":
            continue
        price = money(field(n, "current"))
        anchor = money(field(n, "anchor"))
        sale = field(n, "special") == "true"
        required = {
            "name": field(n, "name"), "sku": field(n, "sku"), "brand": field(n, "brand"),
            "unit": field(n, "unit"), "barcode": field(n, "barcode"),
            "availability": field(n, "availability"),
        }
        if any(not x for x in required.values()) or price is None or anchor is None:
            stop("Workshop-only metaobject is missing required data: " + json.dumps(required, ensure_ascii=False))
        workshop_only.append({
            "naziv": required["name"],
            "sifra": required["sku"],
            "marka": required["brand"],
            "jedinica_mjere": required["unit"],
            "cijena_za_jedinicu_mjere": dec(price),
            "maloprodajna_cijena": dec(price),
            "poseban_oblik_prodaje": "DA" if sale else "NE",
            "naziv_posebnog_oblika_prodaje": field(n, "specialName") if sale else "",
            "sidrena_cijena": dec(anchor),
            "barkod": required["barcode"],
            "dostupnost": required["availability"],
        })

    services = []
    for n in data["service"]["nodes"]:
        if field(n, "active") != "true":
            continue
        price = money(field(n, "current"))
        anchor = money(field(n, "anchor"))
        name = field(n, "name")
        sale = field(n, "special") == "true"
        if not name or price is None or anchor is None:
            stop("Service metaobject is missing required data")
        services.append({
            "naziv_usluge": name,
            "maloprodajna_cijena": dec(price),
            "poseban_oblik_prodaje": "DA" if sale else "NE",
            "naziv_posebnog_oblika_prodaje": field(n, "specialName") if sale else "",
            "sidrena_cijena": dec(anchor),
        })

    if not products or not services:
        stop("Source returned an empty required dataset")

    workshop = products + workshop_only
    sequence = int(state.get("last_sequence", 0)) + 1
    seq = f"{sequence:06d}"
    stamp = now.strftime("%Y%m%d-%H%M")
    iso = now.isoformat(timespec="seconds")

    names = {
        "webshop_csv": f"webshop_jarcec-2-10298-igrisce_WEB01_{seq}_{stamp}_proizvodi.csv",
        "webshop_xml": f"webshop_jarcec-2-10298-igrisce_WEB01_{seq}_{stamp}_proizvodi.xml",
        "workshop_csv": f"pokretni-poslovni-prostor_jarcec-2-10298-igrisce_PPP01_{seq}_{stamp}_proizvodi.csv",
        "workshop_xml": f"pokretni-poslovni-prostor_jarcec-2-10298-igrisce_PPP01_{seq}_{stamp}_proizvodi.xml",
        "services_csv": f"usluzni-objekt_jarcec-2-10298-igrisce_USL01_{seq}_{stamp}_usluge.csv",
        "services_xml": f"usluzni-objekt_jarcec-2-10298-igrisce_USL01_{seq}_{stamp}_usluge.xml",
    }

    clean_current()
    day_archive = ARCHIVE / today
    day_archive.mkdir(parents=True, exist_ok=True)

    current_paths = {k: CURRENT / v for k, v in names.items()}
    write_csv(current_paths["webshop_csv"], PRODUCT_HEADER, products)
    write_csv(current_paths["workshop_csv"], PRODUCT_HEADER, workshop)
    write_csv(current_paths["services_csv"], SERVICE_HEADER, services)

    common = {
        "trgovac": "Covart, obrt za proizvodnju i usluge",
        "adresa": "Jarčec 2, 10298 Igrišće",
        "broj_pohrane": seq,
        "datum_vrijeme": iso,
        "valuta": "EUR",
    }
    current_paths["webshop_xml"].write_text(xml_doc(
        "cjenik_proizvoda", {**common, "objekt": "Webshop", "oznaka_objekta": "WEB01"},
        "proizvod", PRODUCT_HEADER, products), encoding="utf-8")
    current_paths["workshop_xml"].write_text(xml_doc(
        "cjenik_proizvoda", {**common, "objekt": "Pokretni poslovni prostor", "oznaka_objekta": "PPP01"},
        "proizvod", PRODUCT_HEADER, workshop), encoding="utf-8")
    current_paths["services_xml"].write_text(xml_doc(
        "cjenik_usluga", {**common, "objekt": "Uslužni objekt", "oznaka_objekta": "USL01"},
        "usluga", SERVICE_HEADER, services), encoding="utf-8")

    validate_csv(current_paths["webshop_csv"], len(products), PRODUCT_HEADER)
    validate_csv(current_paths["workshop_csv"], len(workshop), PRODUCT_HEADER)
    validate_csv(current_paths["services_csv"], len(services), SERVICE_HEADER)
    validate_xml(current_paths["webshop_xml"], "proizvod", len(products))
    validate_xml(current_paths["workshop_xml"], "proizvod", len(workshop))
    validate_xml(current_paths["services_xml"], "usluga", len(services))

    for p in current_paths.values():
        shutil.copy2(p, day_archive / p.name)

    manifest = {
        "merchant": "Covart, obrt za proizvodnju i usluge",
        "published_at": iso,
        "storage_sequence": seq,
        "currency": "EUR",
        "files": {k: f"current/{v}" for k, v in names.items()},
        "counts": {
            "webshop_products": len(products),
            "workshop_products": len(workshop),
            "services_and_delivery": len(services),
        },
    }
    (CURRENT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    STATE_FILE.write_text(json.dumps({
        "last_sequence": sequence,
        "last_date": today,
        "last_publication": iso,
        "counts": manifest["counts"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prune_archive(now)
    print(json.dumps(manifest, ensure_ascii=False))

if __name__ == "__main__":
    main()
