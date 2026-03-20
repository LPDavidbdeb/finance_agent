from django.test import TestCase
from banking.models import FinancialInstitution
from accounting.models import Account
from users.models import Family
from categorization.models import TransactionMappingRule, Merchant
from categorization.services import find_matching_rule

class CategorizationTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Test Family")
        self.institution = FinancialInstitution.objects.create(name="RBC")
        self.account = Account.objects.create(name="Groceries", account_type=Account.AccountType.EXPENSE, family=self.family)
        
        # Create Merchants
        self.merchant_walmart = Merchant.objects.create(
            family=self.family,
            name="Walmart RBC",
            default_account=self.account
        )
        self.merchant_costco = Merchant.objects.create(
            family=self.family,
            name="Costco Wholesale",
            default_account=self.account
        )

        # Institution-specific rule
        self.rule_rbc = TransactionMappingRule.objects.create(
            merchant=self.merchant_walmart,
            search_text="WAL-MART",
            institution=self.institution
        )
        
        # Global rule
        self.rule_global = TransactionMappingRule.objects.create(
            merchant=self.merchant_costco,
            search_text="COSTCO",
            institution=None
        )

    def test_find_matching_rule_institution_specific(self):
        """Test that institution-specific rules are preferred."""
        rule = find_matching_rule("WAL-MART SUPERCENTER", self.institution.id, self.family.id)
        self.assertEqual(rule, self.rule_rbc)
        self.assertEqual(rule.merchant.name, "WALMART RBC")

    def test_find_matching_rule_global(self):
        """Test that global rules are used when no institution rule exists."""
        rule = find_matching_rule("COSTCO GAS", self.institution.id, self.family.id)
        self.assertEqual(rule, self.rule_global)
        self.assertEqual(rule.merchant.name, "COSTCO WHOLESALE")

    def test_find_matching_rule_no_match(self):
        """Test that None is returned if no rule matches."""
        rule = find_matching_rule("UNKNOWN MERCHANT", self.institution.id, self.family.id)
        self.assertIsNone(rule)
