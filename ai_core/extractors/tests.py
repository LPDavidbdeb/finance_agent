from django.test import TestCase
import pandas as pd

from ai_core.extractors.strategies import VisaDesjardinsExtractor


class VisaDesjardinsExtractorSignTests(TestCase):
    def test_purchase_positive_and_cr_negative(self):
        extractor = VisaDesjardinsExtractor()
        df = pd.DataFrame(
            {
                "DESCRIPTION": ["05 03 Grocery", "12 03 Paiement carte"],
                "MONTANT": ["123,45", "775,00 CR"],
            }
        )

        out = extractor.process_dataframe(df, statement_year=2026, statement_month=3)

        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(float(out.iloc[0]["amount"]), 123.45, places=2)
        self.assertAlmostEqual(float(out.iloc[1]["amount"]), -775.00, places=2)

    def test_minus_kept_negative(self):
        extractor = VisaDesjardinsExtractor()
        df = pd.DataFrame(
            {
                "DESCRIPTION": ["15 03 Refund"],
                "MONTANT": [" - 25,50 "],
            }
        )

        out = extractor.process_dataframe(df, statement_year=2026, statement_month=3)

        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(float(out.iloc[0]["amount"]), -25.50, places=2)

