from django.test import TestCase
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import date

from ai_core.extractors.strategies import VisaDesjardinsExtractor
from banking.extraction import get_statement_date_from_pdf


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

    def test_year_rollover(self):
        """Test that transactions from December in a January statement are assigned the previous year."""
        extractor = VisaDesjardinsExtractor()
        df = pd.DataFrame(
            {
                "DESCRIPTION": ["28 12 Grocery", "05 01 New Year Coffee"],
                "MONTANT": ["50,00", "5,00"],
            }
        )

        # Statement from January 2026
        out = extractor.process_dataframe(df, statement_year=2026, statement_month=1)

        self.assertEqual(len(out), 2)
        # Dec transaction should be 2025
        self.assertEqual(out.iloc[0]["date"].date(), date(2025, 12, 28))
        # Jan transaction should be 2026
        self.assertEqual(out.iloc[1]["date"].date(), date(2026, 1, 5))


class StatementDateParsingTests(TestCase):
    @patch("pdfplumber.open")
    def test_parse_visa_desjardins_date(self, mock_pdf_open):
        # Mock text for Visa Desjardins
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "SOMMAIRE DE VOTRE COMPTE ... DATE DU RELEVÉ Jour 15 Mois 02 Année 2025"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf_open.return_value.__enter__.return_value = mock_pdf

        year, month = get_statement_date_from_pdf("mock_path.pdf")
        self.assertEqual(year, 2025)
        self.assertEqual(month, 2)

    @patch("pdfplumber.open")
    def test_parse_compte_desjardins_date(self, mock_pdf_open):
        # Mock text for Compte Desjardins
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "M. Louis-Philippe ... au 31 mars 2024"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf_open.return_value.__enter__.return_value = mock_pdf

        year, month = get_statement_date_from_pdf("mock_path.pdf")
        self.assertEqual(year, 2024)
        self.assertEqual(month, 3)

    @patch("pdfplumber.open")
    def test_parse_date_failure(self, mock_pdf_open):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "No date information here"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf_open.return_value.__enter__.return_value = mock_pdf

        year, month = get_statement_date_from_pdf("mock_path.pdf")
        self.assertIsNone(year)
        self.assertIsNone(month)
