from decimal import Decimal
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

    def test_find_matching_rule_with_amount_bounds(self):
        """Test that rules with amount bounds are correctly prioritized and filtered."""
        # Create two merchants for the same search string but different amount ranges
        merchant_car = Merchant.objects.create(family=self.family, name="CAR INSURANCE")
        merchant_house = Merchant.objects.create(family=self.family, name="HOUSE INSURANCE")

        # Rule for small amounts (Car)
        rule_car = TransactionMappingRule.objects.create(
            merchant=merchant_car,
            search_text="INSURANCE",
            max_amount=100.00
        )
        # Rule for large amounts (House)
        rule_house = TransactionMappingRule.objects.create(
            merchant=merchant_house,
            search_text="INSURANCE",
            min_amount=100.01
        )

        # 1. Test Car Insurance ($50.00)
        match_small = find_matching_rule("INSURANCE CO", self.institution.id, self.family.id, transaction_amount=Decimal("50.00"))
        self.assertEqual(match_small, rule_car)
        self.assertEqual(match_small.merchant.name, "CAR INSURANCE")

        # 2. Test House Insurance ($500.00)
        match_large = find_matching_rule("INSURANCE CO", self.institution.id, self.family.id, transaction_amount=Decimal("500.00"))
        self.assertEqual(match_large, rule_house)
        self.assertEqual(match_large.merchant.name, "HOUSE INSURANCE")

        # 3. Test absolute amount (Credit/Refund of $50.00)
        match_credit = find_matching_rule("INSURANCE CO", self.institution.id, self.family.id, transaction_amount=Decimal("-50.00"))
        self.assertEqual(match_credit, rule_car)

    def test_find_matching_rule_prioritize_bounded_over_unbounded(self):
        """Test that a bounded rule wins over an unbounded rule of same length/search."""
        merchant_gen = Merchant.objects.create(family=self.family, name="GENERIC INSURANCE")
        merchant_spec = Merchant.objects.create(family=self.family, name="SPECIFIC INSURANCE")

        # Unbounded rule
        TransactionMappingRule.objects.create(
            merchant=merchant_gen,
            search_text="INSURANCE"
        )
        # Bounded rule
        rule_spec = TransactionMappingRule.objects.create(
            merchant=merchant_spec,
            search_text="INSURANCE",
            min_amount=50.00,
            max_amount=150.00
        )

        # Amount in range should hit specific rule
        match = find_matching_rule("INSURANCE", self.institution.id, self.family.id, transaction_amount=Decimal("100.00"))
        self.assertEqual(match, rule_spec)
        self.assertEqual(match.merchant.name, "SPECIFIC INSURANCE")
