from django.test import TestCase
from banking.models import FinancialInstitution
from accounting.models import Account
from categorization.models import TransactionMappingRule
from categorization.services import find_matching_rule

class CategorizationTest(TestCase):
    def setUp(self):
        self.institution = FinancialInstitution.objects.create(name="RBC")
        self.account = Account.objects.create(name="Groceries", account_type=Account.AccountType.EXPENSE)
        
        # Institution-specific rule
        self.rule_rbc = TransactionMappingRule.objects.create(
            search_text="WAL-MART",
            merchant_name="Walmart RBC",
            target_account=self.account,
            institution=self.institution
        )
        
        # Global rule
        self.rule_global = TransactionMappingRule.objects.create(
            search_text="COSTCO",
            merchant_name="Costco Wholesale",
            target_account=self.account,
            institution=None
        )

    def test_find_matching_rule_institution_specific(self):
        """Test that institution-specific rules are preferred."""
        rule = find_matching_rule("WAL-MART SUPERCENTER", self.institution.id)
        self.assertEqual(rule, self.rule_rbc)
        self.assertEqual(rule.merchant_name, "Walmart RBC")

    def test_find_matching_rule_global(self):
        """Test that global rules are used when no institution rule exists."""
        rule = find_matching_rule("COSTCO GAS", self.institution.id)
        self.assertEqual(rule, self.rule_global)
        self.assertEqual(rule.merchant_name, "Costco Wholesale")

    def test_find_matching_rule_no_match(self):
        """Test that None is returned if no rule matches."""
        rule = find_matching_rule("UNKNOWN MERCHANT", self.institution.id)
        self.assertIsNone(rule)
