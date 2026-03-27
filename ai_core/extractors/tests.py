from django.test import TestCase
import pandas as pd
from unittest.mock import patch, MagicMock, call
from datetime import date

from ai_core.extractors.strategies import VisaDesjardinsExtractor, TangerineExtractor
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

        out, _ = extractor.process_dataframe(df, statement_year=2026, statement_month=3)

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

        out, _ = extractor.process_dataframe(df, statement_year=2026, statement_month=3)

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
        out, _ = extractor.process_dataframe(df, statement_year=2026, statement_month=1)

        self.assertEqual(len(out), 2)
        # Dec transaction should be 2025
        self.assertEqual(out.iloc[0]["date"].date(), date(2025, 12, 28))
        # Jan transaction should be 2026
        self.assertEqual(out.iloc[1]["date"].date(), date(2026, 1, 5))


class TangerineExtractorTests(TestCase):
    """
    Mock-based tests for TangerineExtractor routing logic.

    These tests never touch a real PDF. pdfplumber and tabula are both mocked so
    we can verify that:
      1. Pass 1 correctly maps account numbers to ProductType values.
      2. Pass 2 correctly assigns account_number and inferred_product_type to rows.
      3. The sign convention is respected (outflow = negative, inflow = positive).
      4. Rows from different accounts are correctly segregated in the output.

    test_real_world_january_2023_structure uses the exact account-number string
    from a real January 2023 Tangerine statement to pin the parsing behaviour
    against real-world data before the E2E command is run.
    """

    def _make_pdf_mock(self, page_texts: list[str]):
        """Return a pdfplumber context-manager mock whose pages return given texts."""
        pages = []
        for text in page_texts:
            page = MagicMock()
            page.extract_text.return_value = text
            pages.append(page)
        pdf = MagicMock()
        pdf.pages = pages
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=pdf)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_routing_assigns_correct_account_number_and_product_type(self, mock_pdf_open, mock_tabula):
        """
        Two-section statement: chequing (12345) and savings (67890).
        Verify that every row gets the right account_number and inferred_product_type.
        """
        page_texts = [
            # Page 1 — summary table ("coup d'oeil")
            "Compte(s) en un coup d'oeil\n"
            "Compte-chèques 12345   $500.00\n"
            "Compte épargne 67890   $1 000.00\n",
            # Page 2 — chequing section header + table
            "Détails - Compte-chèques - 12345\n"
            "Date Description Retraits Dépôts\n",
            # Page 3 — savings section header + table
            "Détails - Compte épargne - 67890\n"
            "Date Description Retraits Dépôts\n",
        ]
        mock_pdf_open.return_value = self._make_pdf_mock(page_texts)

        chequing_df = pd.DataFrame({
            'Date':        ['2024-01-15', '2024-01-20'],
            'Description': ['GROCERY STORE', 'PAYROLL DEPOSIT'],
            'Retraits':    [50.00, 0.00],
            'Dépôts':      [0.00, 2000.00],
        })
        savings_df = pd.DataFrame({
            'Date':        ['2024-01-31'],
            'Description': ['INTEREST'],
            'Retraits':    [0.00],
            'Dépôts':      [5.25],
        })
        # tabula is called once per section (2 sections)
        mock_tabula.side_effect = [[chequing_df], [savings_df]]

        extractor = TangerineExtractor()
        result, mismatch = extractor.extract('dummy.pdf', 2024, 1)

        self.assertFalse(mismatch)
        self.assertEqual(len(result), 3, "Expected 2 chequing rows + 1 savings row")

        chequing_rows = result[result['account_number'] == '12345']
        savings_rows  = result[result['account_number'] == '67890']

        self.assertEqual(len(chequing_rows), 2)
        self.assertEqual(len(savings_rows), 1)

        self.assertTrue(all(chequing_rows['inferred_product_type'] == 'CHECKING'))
        self.assertTrue(all(savings_rows['inferred_product_type'] == 'SAVINGS'))

    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_sign_convention_withdrawal_negative_deposit_positive(self, mock_pdf_open, mock_tabula):
        """
        Withdrawals must produce negative amounts; deposits must produce positive amounts.
        """
        page_texts = [
            "Compte(s) en un coup d'oeil\nCompte-chèques 11111   $100.00\n",
            "Détails - Compte-chèques - 11111\nDate Description Retraits Dépôts\n",
        ]
        mock_pdf_open.return_value = self._make_pdf_mock(page_texts)

        mock_tabula.return_value = [pd.DataFrame({
            'Date':        ['2024-03-01', '2024-03-05', '2024-03-10'],
            'Description': ['COFFEE SHOP', 'SALARY', 'TRANSFER OUT'],
            'Retraits':    [4.75,   0.00,   250.00],
            'Dépôts':      [0.00,   3000.00, 0.00],
        })]

        extractor = TangerineExtractor()
        result, _ = extractor.extract('dummy.pdf', 2024, 3)

        self.assertEqual(len(result), 3)
        coffee   = result[result['description'] == 'COFFEE SHOP'].iloc[0]
        salary   = result[result['description'] == 'SALARY'].iloc[0]
        transfer = result[result['description'] == 'TRANSFER OUT'].iloc[0]

        self.assertAlmostEqual(float(coffee['amount']),   -4.75,    places=2)
        self.assertAlmostEqual(float(salary['amount']),   3000.00,  places=2)
        self.assertAlmostEqual(float(transfer['amount']), -250.00,  places=2)

    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_celi_account_maps_to_investment(self, mock_pdf_open, mock_tabula):
        """
        Account labelled 'CELI' in the summary must get inferred_product_type='INVESTMENT'.
        """
        page_texts = [
            "Compte(s) en un coup d'oeil\nCELI 99999   $5 000.00\n",
            "Détails - CELI - 99999\nDate Description Retraits Dépôts\n",
        ]
        mock_pdf_open.return_value = self._make_pdf_mock(page_texts)

        mock_tabula.return_value = [pd.DataFrame({
            'Date':        ['2024-06-15'],
            'Description': ['CONTRIBUTION'],
            'Retraits':    [0.00],
            'Dépôts':      [500.00],
        })]

        extractor = TangerineExtractor()
        result, _ = extractor.extract('dummy.pdf', 2024, 6)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['inferred_product_type'], 'INVESTMENT')
        self.assertEqual(result.iloc[0]['account_number'], '99999')

    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_unknown_account_falls_back_to_checking(self, mock_pdf_open, mock_tabula):
        """
        If Pass 1 doesn't recognise an account number, the row gets 'CHECKING' as fallback.
        """
        page_texts = [
            # Summary page with no recognisable keyword for account 55555
            "Compte(s) en un coup d'oeil\nCompte X 55555   $0.00\n",
            "Détails - Compte X - 55555\nDate Description Retraits Dépôts\n",
        ]
        mock_pdf_open.return_value = self._make_pdf_mock(page_texts)

        mock_tabula.return_value = [pd.DataFrame({
            'Date':        ['2024-02-01'],
            'Description': ['MYSTERY TXN'],
            'Retraits':    [10.00],
            'Dépôts':      [0.00],
        })]

        extractor = TangerineExtractor()
        result, _ = extractor.extract('dummy.pdf', 2024, 2)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['inferred_product_type'], 'CHECKING')

    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_real_world_january_2023_structure(self, mock_pdf_open, mock_tabula):
        """
        Pins behaviour against the real four-account structure found in a
        January 2023 Tangerine consolidated statement.

        Pass 1 assertions (direct call to _pass1_infer_product_types):
          3014873044  Compte d'épargne → SAVINGS
          3403209360  (CELI)           → INVESTMENT
          3805015509  CPG libre d'impôt → INVESTMENT
          3805041041  CPG libre d'impôt → INVESTMENT

        Pass 2 assertions (via full extract()):
          All output rows carry account_number='3014873044' and
          inferred_product_type='SAVINGS'.
        """
        SUMMARY_PAGE = (
            "Compte(s) en un coup d'oeil\n"
            "Compte d'épargne Tangerine 3014873044\n"
            "(CELI) 3403209360\n"
            "CPG libre d'impôt 3805015509\n"
            "CPG libre d'impôt 3805041041"
        )
        SECTION_PAGE = (
            "Détails - Compte d'épargne Tangerine - 3014873044\n"
            "Date Description Retraits Dépôts\n"
        )

        # Both Pass 1 and _find_section_pages open the same PDF; return the
        # same two-page mock for every call to pdfplumber.open().
        mock_pdf_open.return_value = self._make_pdf_mock([SUMMARY_PAGE, SECTION_PAGE])

        mock_tabula.return_value = [pd.DataFrame({
            'Date':        ['2023-01-15', '2023-01-20'],
            'Description': ['VIREMENT ENTRANT', 'FRAIS MENSUELS'],
            'Retraits':    [0.00, 5.00],
            'Dépôts':      [1000.00, 0.00],
        })]

        extractor = TangerineExtractor()

        # ---- Pass 1 assertion ----
        # Build a standalone pdfplumber-module mock so we can call the private
        # method directly without going through extract() a second time.
        mock_plumber = MagicMock()
        mock_plumber.open.return_value = self._make_pdf_mock([SUMMARY_PAGE])
        product_types = extractor._pass1_infer_product_types('dummy.pdf', mock_plumber)

        self.assertEqual(product_types.get('3014873044'), 'SAVINGS',
                         "Compte d'épargne must map to SAVINGS")
        self.assertEqual(product_types.get('3403209360'), 'INVESTMENT',
                         "CELI must map to INVESTMENT")
        self.assertEqual(product_types.get('3805015509'), 'INVESTMENT',
                         "CPG libre d'impôt must map to INVESTMENT")
        self.assertEqual(product_types.get('3805041041'), 'INVESTMENT',
                         "CPG libre d'impôt must map to INVESTMENT")

        # ---- Pass 2 assertion (via full extract()) ----
        result, mismatch = extractor.extract('dummy.pdf', 2023, 1)

        self.assertFalse(mismatch)
        self.assertEqual(len(result), 2, "Expected 2 transactions from the savings section")
        self.assertTrue(
            (result['account_number'] == '3014873044').all(),
            "All rows must be tagged to the savings account number"
        )
        self.assertTrue(
            (result['inferred_product_type'] == 'SAVINGS').all(),
            "All rows must carry SAVINGS as inferred_product_type"
        )
        # Sign convention: deposit → positive, withdrawal → negative
        virement = result[result['description'] == 'VIREMENT ENTRANT'].iloc[0]
        frais    = result[result['description'] == 'FRAIS MENSUELS'].iloc[0]
        self.assertAlmostEqual(float(virement['amount']),  1000.0, places=2)
        self.assertAlmostEqual(float(frais['amount']),      -5.0,  places=2)

    @patch('tabula.read_pdf')
    @patch('pdfplumber.open')
    def test_empty_statement_returns_empty_dataframe(self, mock_pdf_open, mock_tabula):
        """
        A PDF with no 'Détails' section headers must return an empty DataFrame
        with the correct column schema.
        """
        page_texts = [
            "Compte(s) en un coup d'oeil\nNo accounts here.\n",
            "Some other page with no section header.\n",
        ]
        mock_pdf_open.return_value = self._make_pdf_mock(page_texts)
        mock_tabula.return_value = []

        extractor = TangerineExtractor()
        result, mismatch = extractor.extract('dummy.pdf', 2024, 1)

        self.assertFalse(mismatch)
        self.assertTrue(result.empty)
        self.assertListEqual(list(result.columns), TangerineExtractor.OUTPUT_COLUMNS)


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
