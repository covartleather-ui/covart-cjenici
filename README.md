# Covart machine-readable price lists

Official public machine-readable price-list repository for **Covart, obrt za proizvodnju i usluge**.

## Publication structure

- `current/` contains the latest published CSV/XML files.
- `current/manifest.json` identifies the exact latest filenames and publication metadata.
- `archive/YYYY-MM-DD/` contains previous published versions.
- `state.json` stores the next-publication sequence state.
- `scripts/generate_price_lists.py` generates and validates the datasets.
- `.github/workflows/publish-price-lists.yml` performs scheduled publication.

Daily scheduling is handled outside GitHub Actions by the connected automation. A separate hourly change watch publishes again only when relevant Shopify price-list data changes. The GitHub Actions workflow is intentionally **manual-only** as a fallback.

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

## Storefront delivery

Each successful publication is also copied into Shopify Files. Covart then creates a merchant-domain redirect of the form `https://covart-shop.com/cjenici/YYYY-MM-DD/<filename>` to the Shopify-hosted file. The public `/pages/cjenik` page points to these Covart-domain URLs, while this repository remains the independent publication archive and generation state store.

Test publication **000002** was completed on **2026-09-25 at 18:08 Europe/Zagreb** before the 2026-10-01 rollout.
