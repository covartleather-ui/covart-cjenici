"""Offline regression tests for Covart's identifier generator."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_price_lists as mod


def audit(*, sku=None, barcode=None, anchor="60.00", write=True):
    return {
        "currentAppInstallation": {
            "accessScopes": [{"handle": "write_products" if write else "read_products"}]
        },
        "workshop": {
            "pageInfo": {"hasNextPage": False},
            "nodes": [{"sku": {"value": "RAD-001"}, "barcode": {"value": "COV0000107"}}],
        },
        "products": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [{
                "id": "gid://shopify/Product/10",
                "title": "Test novcanik",
                "status": "ACTIVE",
                "variants": {
                    "pageInfo": {"hasNextPage": False},
                    "nodes": [{
                        "id": "gid://shopify/ProductVariant/42",
                        "sku": sku,
                        "barcode": barcode,
                        "anchor": {"value": anchor} if anchor is not None else None,
                    }],
                },
            }],
        },
    }


class IdentifierTests(unittest.TestCase):
    def call_audit(self, source):
        mutations = []
        def fake_graphql(query, variables=None, access_token=None):
            if query == mod.IDENTIFIERS_QUERY:
                return source
            self.assertEqual(query, mod.ASSIGN_IDENTIFIERS_MUTATION)
            mutations.append(variables)
            return {"productVariantsBulkUpdate": {
                "productVariants": variables["variants"], "userErrors": [],
            }}

        with tempfile.TemporaryDirectory() as d:
            state = {"last_sequence": 30, "last_date": "2026-10-20"}
            with patch.object(mod, "shopify_token", return_value="test-token"), \
                 patch.object(mod, "graphql", side_effect=fake_graphql), \
                 patch.object(mod, "STATE_FILE", Path(d) / "state.json"):
                mod.ensure_identifiers(state)
            return state, mutations

    def test_missing_identifiers_get_unique_stable_codes(self):
        state, mutations = self.call_audit(audit())
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0]["productId"], "gid://shopify/Product/10")
        update = mutations[0]["variants"][0]
        self.assertEqual(update["sku"], "AUTO-42")
        self.assertEqual(update["barcode"], "COV0000108")
        self.assertEqual(state["last_barcode_number"], 108)

    def test_existing_identifiers_remain_unchanged(self):
        state, mutations = self.call_audit(audit(
            sku="NOV-MIN-01", barcode="COV0000108", write=False
        ))
        self.assertFalse(mutations)
        self.assertEqual(state["last_barcode_number"], 108)

    def test_missing_historical_anchor_price_is_not_invented(self):
        with self.assertRaises(SystemExit):
            self.call_audit(audit(anchor=None))

    def test_missing_write_scope_blocks_new_codes(self):
        with self.assertRaises(SystemExit):
            self.call_audit(audit(write=False))


if __name__ == "__main__":
    unittest.main()
