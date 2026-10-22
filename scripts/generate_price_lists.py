#!/usr/bin/env python3
import csv
from collections import Counter
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
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
CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
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

# Identifier preparation runs before the public price-list generator. A code in
# Shopify is an internal identifier, not a registered GS1/EAN barcode.
IDENTIFIERS_QUERY = r"""
query CovartIdentifierAudit($after: String) {
  products(first: 250, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id title status
      variants(first: 250) {
        pageInfo { hasNextPage }
        nodes {
          id sku barcode
          anchor: metafield(namespace: "custom", key: "anchor_price") { value }
        }
      }
    }
  }
  workshop: metaobjects(type: "covart_workshop_product", first: 250) {
    pageInfo { hasNextPage }
    nodes {
      sku: field(key: "sku") { value }
      barcode: field(key: "barcode") { value }
    }
  }
  currentAppInstallation { accessScopes { handle } }
}
"""

ASSIGN_IDENTIFIERS_MUTATION = r"""
mutation CovartAssignIdentifiers($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(
    productId: $productId,
    variants: $variants,
    allowPartialUpdates: false
  ) {
    productVariants { id sku barcode }
    userErrors { field message }
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

def shopify_token():
    if CLIENT_ID and CLIENT_SECRET:
        payload = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"https://{SHOP}/admin/oauth/access_token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                token_data = json.load(response)
        except urllib.error.HTTPError as exc:
            stop(f"Shopify token request failed (HTTP {exc.code})")
        except Exception as exc:
            stop(f"Shopify token request failed ({type(exc).__name__})")
        access_token = token_data.get("access_token")
        if not access_token:
            stop("Shopify token response did not contain an access token")
        return access_token
    if TOKEN:
        return TOKEN
    stop("Configure SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET, or a legacy SHOPIFY_ADMIN_ACCESS_TOKEN")

def graphql(query=QUERY, variables=None, access_token=None):
    access_token = access_token or shopify_token()
    url = f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json"
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token,
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
    if EVENT_NAME != "schedule" or SCHEDULE_CRON == "45 * * * *":
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
    if not rows:
        stop(f"{path}: CSV contains no data rows")
    if list(rows[0].keys()) != header:
        stop(f"{path}: unexpected CSV header")

def validate_xml(path, item_name, expected_rows):
    tree = ET.parse(path)
    count = len(tree.getroot().findall(item_name))
    if count != expected_rows:
        stop(f"{path}: expected {expected_rows} XML items, got {count}")

def current_rows_match(datasets):
    try:
        manifest = json.loads((CURRENT / "manifest.json").read_text(encoding="utf-8"))
        for key, expected in datasets.items():
            path = ROOT / manifest["files"][key]
            if path.parent != CURRENT:
                return False
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                actual = list(csv.DictReader(f, delimiter=";"))
            # API ordering alone is not a price-list change; preserve duplicates.
            actual_rows = Counter(tuple(sorted(row.items())) for row in actual)
            expected_rows = Counter(tuple(sorted(row.items())) for row in expected)
            if actual_rows != expected_rows:
                return False
        return True
    except (OSError, KeyError, ValueError, csv.Error, json.JSONDecodeError):
        return False

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

def ensure_identifiers(state):
    """Fill missing SKU/internal barcode only; NEVER invent historic anchor prices."""
    token = shopify_token()
    products = []
    used_skus = set()
    used_barcodes = set()
    last_number = int(state.get("last_barcode_number", 0))
    cursor = None
    scopes = set()

    while True:
        data = graphql(IDENTIFIERS_QUERY, {"after": cursor}, token)
        scopes = {scope["handle"] for scope in data["currentAppInstallation"]["accessScopes"]}
        workshop = data["workshop"]
        if workshop["pageInfo"]["hasNextPage"]:
            stop("Identifier audit: workshop metaobjects exceed the first 250; add pagination")
        for item in workshop["nodes"]:
            for key, target in (("sku", used_skus), ("barcode", used_barcodes)):
                value = (item.get(key) or {}).get("value")
                if value:
                    target.add(value.strip())

        page = data["products"]
        for product in page["nodes"]:
            if product["variants"]["pageInfo"]["hasNextPage"]:
                stop(f"Identifier audit: more than 250 variants in {product['title']}; add pagination")
            products.append(product)
            for variant in product["variants"]["nodes"]:
                for key, target in (("sku", used_skus), ("barcode", used_barcodes)):
                    value = variant.get(key)
                    if value:
                        target.add(value.strip())
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    # Reserve all previously issued COV serials, even on archived products.
    for code in used_barcodes:
        if code.startswith("COV") and code[3:].isdigit():
            last_number = max(last_number, int(code[3:]))

    updates = []
    for product in products:
        if product["status"] != "ACTIVE":
            continue
        pending = []
        for variant in product["variants"]["nodes"]:
            anchor = (variant.get("anchor") or {}).get("value")
            if not anchor:
                stop(
                    f"Missing verified anchor price for '{product['title']}', "
                    f"variant {variant['id']}. Set custom.anchor_price in Shopify. "
                    "Historical/reference prices must not be fabricated."
                )
            item = {"id": variant["id"]}
            if not (variant.get("sku") or "").strip():
                # Stable collision-proof fallback, not a merchant-defined product code.
                candidate = "AUTO-" + variant["id"].rsplit("/", 1)[-1]
                if candidate in used_skus:
                    stop(f"Automatic SKU collision: {candidate}")
                item["sku"] = candidate
                used_skus.add(candidate)
            if not (variant.get("barcode") or "").strip():
                while True:
                    last_number += 1
                    candidate = f"COV{last_number:07d}"
                    if candidate not in used_barcodes:
                        break
                item["barcode"] = candidate
                used_barcodes.add(candidate)
            if len(item) > 1:
                pending.append(item)
        if pending:
            updates.append((product, pending))

    if updates and "write_products" not in scopes:
        stop(
            "Automatic SKU/barcode generation requires Shopify app scope "
            "'write_products'. Update Shopify app permissions used by GitHub Actions."
        )
    if "write_products" not in scopes:
        print("WARNING: Shopify GitHub app has no 'write_products' scope; "
              "automatic identifiers will need this permission for future products.")

    for product, pending in updates:
        data = graphql(ASSIGN_IDENTIFIERS_MUTATION, {
            "productId": product["id"], "variants": pending,
        }, token)["productVariantsBulkUpdate"]
        if data["userErrors"]:
            stop(
                f"Could not auto-fill identifiers for '{product['title']}': "
                + json.dumps(data["userErrors"], ensure_ascii=False)
            )
        returned = {v["id"]: v for v in data["productVariants"]}
        for item in pending:
            variant = returned.get(item["id"])
            if not variant or any(variant.get(key) != value for key, value in item.items()):
                stop(f"Shopify did not confirm identifier update for {item['id']}")
        print(f"Auto-filled identifiers for {len(pending)} variants in: {product['title']}")

    if last_number != int(state.get("last_barcode_number", 0)):
        state["last_barcode_number"] = last_number
        STATE_FILE.write_text(json.dumps(
            state, ensure_ascii=False, indent=2
        ) + "\n", encoding="utf-8")
    print(f"Identifier audit passed: {len(products)} products, "
          f"{sum(len(items) for _, items in updates)} updated variants")


def main():
    now = datetime.now(TZ)
    if not is_valid_schedule(now):
        print(f"Skipping inactive DST schedule slot: {SCHEDULE_CRON}")
        return

    state = load_state()
    today = now.date().isoformat()
    ensure_identifiers(state)
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
    # Apply the same change-only rule to scheduled, manual and push runs.
    if current_rows_match({
        "webshop_csv": products,
        "workshop_csv": workshop,
        "services_csv": services,
    }):
        print("No relevant Shopify price-list changes; publication skipped.")
        return

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
        "last_barcode_number": state.get("last_barcode_number", 0),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prune_archive(now)
    print(json.dumps(manifest, ensure_ascii=False))

if __name__ == "__main__":
    main()
