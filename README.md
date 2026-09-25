# Covart machine-readable price lists

Official public machine-readable price-list repository for **Covart, obrt za proizvodnju i usluge**.

## Publication structure

- `current/` contains the latest published CSV/XML files.
- `current/manifest.json` identifies the exact latest filenames and publication metadata.
- `archive/YYYY-MM-DD/` contains previous published versions.
- `state.json` stores the next-publication sequence state.
- `scripts/generate_price_lists.py` generates and validates the datasets.
- `.github/workflows/publish-price-lists.yml` performs scheduled publication.

The publication workflow uses Europe/Zagreb local time and is designed to publish at about **07:15**, with a later fallback slot if the primary scheduled run did not complete. It can also be started manually with **Run workflow**, which is useful after a service-price change.

The repository intentionally keeps more than 30 days of archive availability (40-day retention buffer in the generator).

## Data sets

1. Webshop products
2. Workshop products (webshop products plus workshop-only products)
3. Services and delivery

CSV and XML versions of each data set are generated from Shopify structured data.

## Security

No Shopify credential or API token is stored in this public repository. The workflow expects the GitHub Actions repository secret:

`SHOPIFY_ADMIN_ACCESS_TOKEN`

The Shopify shop domain is non-secret and is configured as `6ffdpq-40.myshopify.com`.

Initial publication: **2026-09-25**, storage sequence **000001**.
