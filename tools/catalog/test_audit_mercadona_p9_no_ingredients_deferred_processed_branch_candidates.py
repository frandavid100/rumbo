from __future__ import annotations

import unittest

from audit_mercadona_p9_no_ingredients_deferred_processed_branch_candidates import candidate_payload


def row(*, top: str, level1: str, ingredients=None, perspective=9, zoom='https://example.test/x.jpg'):
    return {
        'product_id': '1',
        'name': 'x',
        'ingredients': ingredients,
        'category_path': [
            {'id': '1', 'level': '0', 'name': top},
            {'id': '2', 'level': '1', 'name': level1},
        ],
        'photos': [{'perspective': perspective, 'zoom': zoom}],
    }


class CandidatePayloadTests(unittest.TestCase):
    def test_accepts_carne_processed_subbranch(self):
        payload = candidate_payload(row(top='Carne', level1='Empanados y elaborados'))
        self.assertIsNotNone(payload)
        self.assertEqual(payload['matched_processed_level1_branches'], ['Empanados y elaborados'])
        self.assertEqual(payload['CLASSIFIED'], 0)
        self.assertEqual(payload['MENU_ELIGIBLE'], 0)

    def test_accepts_seafood_salted_subbranch(self):
        payload = candidate_payload(row(top='Marisco y pescado', level1='Salazones y ahumados'))
        self.assertIsNotNone(payload)
        self.assertEqual(payload['matched_processed_level1_branches'], ['Salazones y ahumados'])

    def test_rejects_raw_meat_branch(self):
        self.assertIsNone(candidate_payload(row(top='Carne', level1='Aves y pollo')))

    def test_rejects_live_seafood_branch(self):
        self.assertIsNone(candidate_payload(row(top='Marisco y pescado', level1='Marisco')))

    def test_rejects_bodega_even_when_packaged(self):
        self.assertIsNone(candidate_payload(row(top='Bodega', level1='Cerveza')))

    def test_rejects_structured_ingredients(self):
        self.assertIsNone(candidate_payload(row(top='Carne', level1='Empanados y elaborados', ingredients=['pollo'])))

    def test_rejects_without_p9_zoom(self):
        self.assertIsNone(candidate_payload(row(top='Carne', level1='Empanados y elaborados', perspective=1)))
        self.assertIsNone(candidate_payload(row(top='Carne', level1='Empanados y elaborados', zoom=None)))


if __name__ == '__main__':
    unittest.main()
