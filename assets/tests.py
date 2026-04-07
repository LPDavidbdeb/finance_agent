from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from users.models import Family, FamilyMember
from accounting.models import Account
from assets.models import TangibleAsset

class TangibleAssetModelTest(TestCase):
    def setUp(self):
        self.family = Family.objects.create(name="Asset Family")
        self.member = FamilyMember.objects.create(
            family=self.family, 
            first_name="John", 
            last_name="Doe",
            date_of_birth="1980-01-01"
        )
        self.asset_account = Account.objects.create(
            name="Real Estate",
            account_type='ASSET',
            family=self.family
        )
        self.expense_account = Account.objects.create(
            name="Food",
            account_type='EXPENSE',
            family=self.family
        )

    def test_create_tangible_asset_success(self):
        asset = TangibleAsset.objects.create(
            family=self.family,
            account=self.asset_account,
            name="Main Residence",
            purchase_value=Decimal("500000.00"),
            current_market_value=Decimal("550000.00")
        )
        self.assertEqual(asset.name, "Main Residence")
        self.assertEqual(asset.account.account_type, 'ASSET')

    def test_tangible_asset_requires_asset_account(self):
        # Linking to an EXPENSE account should fail validation
        asset = TangibleAsset(
            family=self.family,
            account=self.expense_account,
            name="Invalid Asset",
            purchase_value=Decimal("100.00"),
            current_market_value=Decimal("100.00")
        )
        with self.assertRaises(ValidationError):
            asset.save()

    def test_tangible_asset_relationships(self):
        # Test optional links
        asset = TangibleAsset.objects.create(
            family=self.family,
            account=self.asset_account,
            member=self.member,
            name="Personal Car",
            purchase_value=Decimal("30000.00"),
            current_market_value=Decimal("25000.00")
        )
        self.assertEqual(asset.member, self.member)
        self.assertEqual(self.member.tangible_assets.first(), asset)
