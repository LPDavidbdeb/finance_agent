from django.test import TestCase
from django.contrib.auth import get_user_model
from users.models import Family
from accounting.models import Account, JournalEntry, TransactionLine
from decimal import Decimal
from ninja_jwt.tokens import AccessToken
from test_client_factory import get_test_client

User = get_user_model()


class AccountingApiTest(TestCase):
    def setUp(self):
        self.client = get_test_client()

        # Create Families
        self.family_a = Family.objects.create(name="Family A")
        self.family_b = Family.objects.create(name="Family B")
        
        # Create Users
        self.user_a = User.objects.create_user("user_a@example.com", "password", family=self.family_a)
        self.user_b = User.objects.create_user("user_b@example.com", "password", family=self.family_b)

        # Create Tokens
        self.token_a = str(AccessToken.for_user(self.user_a))
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}
        
        # Create Accounts for Family A
        self.cash_a = Account.objects.create(name="Cash A", account_type=Account.AccountType.ASSET, family=self.family_a)
        self.expense_a = Account.objects.create(name="Expense A", account_type=Account.AccountType.EXPENSE, family=self.family_a)
        
        # Create Accounts for Family B
        self.cash_b = Account.objects.create(name="Cash B", account_type=Account.AccountType.ASSET, family=self.family_b)

    def test_get_account_tree_isolation(self):
        """Test that account tree only returns accounts for the user's family."""
        response = self.client.get("/accounts/tree", headers=self.headers_a)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify only family_a accounts are returned
        account_names = [a['name'] for a in data]
        self.assertIn("Cash A", account_names)
        self.assertIn("Expense A", account_names)
        self.assertNotIn("Cash B", account_names)

    def test_create_journal_entry_success(self):
        """Test successful creation of a balanced journal entry."""
        payload = {
            "date": "2023-01-01",
            "description": "Test Entry",
            "lines": [
                {"account_id": self.cash_a.id, "amount": -100.00},
                {"account_id": self.expense_a.id, "amount": 100.00}
            ]
        }
        response = self.client.post("/accounting/journal-entry", json=payload, headers=self.headers_a)
        self.assertEqual(response.status_code, 200)
        
        # Verify database
        entry = JournalEntry.objects.get(description="Test Entry", family=self.family_a)
        self.assertEqual(entry.lines.count(), 2)
        self.assertEqual(entry.lines.get(account=self.expense_a).amount, Decimal("100.00"))

    def test_create_journal_entry_unbalanced(self):
        """Test that an unbalanced journal entry fails."""
        payload = {
            "date": "2023-01-01",
            "description": "Unbalanced Entry",
            "lines": [
                {"account_id": self.cash_a.id, "amount": -100.00},
                {"account_id": self.expense_a.id, "amount": 50.00}
            ]
        }
        response = self.client.post("/accounting/journal-entry", json=payload, headers=self.headers_a)
        self.assertEqual(response.status_code, 400)
        self.assertIn("must sum to zero", response.json()['detail'])

    def test_create_journal_entry_wrong_family_account(self):
        """Test that using an account from another family fails."""
        payload = {
            "date": "2023-01-01",
            "description": "Cross-family Entry",
            "lines": [
                {"account_id": self.cash_a.id, "amount": -100.00},
                {"account_id": self.cash_b.id, "amount": 100.00}
            ]
        }
        response = self.client.post("/accounting/journal-entry", json=payload, headers=self.headers_a)
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found in your family", response.json()['detail'])

    def test_delete_account_isolation(self):
        """Test that a user cannot delete an account from another family."""
        response = self.client.delete(f"/accounts/{self.cash_b.id}", headers=self.headers_a)
        self.assertNotEqual(response.status_code, 200)
        self.assertTrue(Account.objects.filter(id=self.cash_b.id).exists())

    def test_get_spending_evolution(self):
        """Test the spending evolution report."""
        # Create an 'Expenses' root
        root_exp = Account.objects.create(name="Expenses", account_type=Account.AccountType.EXPENSE, family=self.family_a)
        sub_exp = Account.objects.create(name="Food", account_type=Account.AccountType.EXPENSE, family=self.family_a, parent=root_exp)
        
        # Create some journal entries and lines
        je = JournalEntry.objects.create(family=self.family_a, date="2023-01-15", description="Groceries")
        TransactionLine.objects.create(journal_entry=je, account=sub_exp, amount=Decimal("150.00"))
        TransactionLine.objects.create(journal_entry=je, account=self.cash_a, amount=Decimal("-150.00"))
        
        response = self.client.get("/accounting/spending-evolution?start_date=2023-01-01&end_date=2023-12-31&interval=monthly", headers=self.headers_a)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data) > 0)
        self.assertEqual(data[0]['amount'], 150.00)

    def test_get_spending_by_category(self):
        """Test the spending by category report."""
        root_exp = Account.objects.create(name="Expenses", account_type=Account.AccountType.EXPENSE, family=self.family_a)
        cat_food = Account.objects.create(name="Food", account_type=Account.AccountType.EXPENSE, family=self.family_a, parent=root_exp)
        cat_rent = Account.objects.create(name="Rent", account_type=Account.AccountType.EXPENSE, family=self.family_a, parent=root_exp)
        
        je1 = JournalEntry.objects.create(family=self.family_a, date="2023-01-15", description="Groceries")
        TransactionLine.objects.create(journal_entry=je1, account=cat_food, amount=Decimal("150.00"))
        TransactionLine.objects.create(journal_entry=je1, account=self.cash_a, amount=Decimal("-150.00"))
        
        je2 = JournalEntry.objects.create(family=self.family_a, date="2023-01-20", description="Rent payment")
        TransactionLine.objects.create(journal_entry=je2, account=cat_rent, amount=Decimal("1000.00"))
        TransactionLine.objects.create(journal_entry=je2, account=self.cash_a, amount=Decimal("-1000.00"))
        
        response = self.client.get("/accounting/spending-by-category?start_date=2023-01-01&end_date=2023-01-31", headers=self.headers_a)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Should be sorted by amount descending
        self.assertEqual(data[0]['category'], "Rent")
        self.assertEqual(data[0]['amount'], 1000.00)
        self.assertEqual(data[1]['category'], "Food")
        self.assertEqual(data[1]['amount'], 150.00)

    def test_get_annual_statements(self):
        """Test the annual statements report."""
        # Setup tree
        root_rev = Account.objects.create(name="Revenue", account_type=Account.AccountType.REVENUE, family=self.family_a)
        root_exp = Account.objects.create(name="Expenses", account_type=Account.AccountType.EXPENSE, family=self.family_a)
        root_asset = Account.objects.create(name="Assets", account_type=Account.AccountType.ASSET, family=self.family_a)
        
        # Add some transactions for 2023
        je1 = JournalEntry.objects.create(family=self.family_a, date="2023-06-01", description="Salary")
        TransactionLine.objects.create(journal_entry=je1, account=root_rev, amount=Decimal("-5000.00"))
        TransactionLine.objects.create(journal_entry=je1, account=root_asset, amount=Decimal("5000.00"))
        
        je2 = JournalEntry.objects.create(family=self.family_a, date="2023-06-15", description="Rent")
        TransactionLine.objects.create(journal_entry=je2, account=root_exp, amount=Decimal("1200.00"))
        TransactionLine.objects.create(journal_entry=je2, account=root_asset, amount=Decimal("-1200.00"))
        
        response = self.client.get("/accounting/annual-statements?year=2023", headers=self.headers_a)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['income_statement']['revenue'], 5000.00)
        self.assertEqual(data['income_statement']['expenses'], 1200.00)
        self.assertEqual(data['income_statement']['net_income'], 3800.00)
        self.assertEqual(data['balance_sheet']['assets'], 3800.00) # 5000 - 1200

class AccountManagementTest(TestCase):
    def setUp(self):
        self.client = get_test_client()
        self.family1 = Family.objects.create(name="Family 1")
        self.family2 = Family.objects.create(name="Family 2")
        
        self.user1 = User.objects.create_user("u1@test.com", "password", family=self.family1)
        self.user2 = User.objects.create_user("u2@test.com", "password", family=self.family2)

        self.token1 = str(AccessToken.for_user(self.user1))
        self.headers1 = {"Authorization": f"Bearer {self.token1}"}
        
        # Root accounts for family 1
        self.root_asset = Account.objects.create(
            name="Assets", account_type=Account.AccountType.ASSET, family=self.family1
        )
        
        # Root for family 2
        self.root_asset_f2 = Account.objects.create(
            name="Assets F2", account_type=Account.AccountType.ASSET, family=self.family2
        )

    def test_create_account_success(self):
        payload = {"name": "Bank Account", "parent_id": self.root_asset.id}
        response = self.client.post("/accounting/accounts", json=payload, headers=self.headers1)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        # Note: Model normalizes name to UPPERCASE
        self.assertEqual(data["name"], "BANK ACCOUNT")
        self.assertEqual(data["account_type"], "ASSET")
        
        new_acc = Account.objects.get(id=data["id"])
        self.assertEqual(new_acc.family, self.family1)

    def test_create_account_cross_family_rejected(self):
        # User 1 tries to create child under User 2's root
        payload = {"name": "Evil Hack", "parent_id": self.root_asset_f2.id}
        response = self.client.post("/accounting/accounts", json=payload, headers=self.headers1)
        self.assertEqual(response.status_code, 404)

    def test_create_account_duplicate_rejected(self):
        Account.objects.create(name="DUPLICATE", parent=self.root_asset, account_type="ASSET", family=self.family1)
        payload = {"name": "Duplicate", "parent_id": self.root_asset.id}
        response = self.client.post("/accounting/accounts", json=payload, headers=self.headers1)
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", response.json()["detail"])

    def test_delete_account_success(self):
        acc = Account.objects.create(name="To Delete", parent=self.root_asset, account_type="ASSET", family=self.family1)
        response = self.client.delete(f"/accounting/accounts/{acc.id}", headers=self.headers1)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Account.objects.filter(id=acc.id).exists())

    def test_delete_account_with_history_rejected(self):
        acc = Account.objects.create(name="Protected", parent=self.root_asset, account_type="ASSET", family=self.family1)
        je = JournalEntry.objects.create(family=self.family1, date="2025-01-01", description="Test")
        TransactionLine.objects.create(journal_entry=je, account=acc, amount=Decimal("100.00"))
        
        response = self.client.delete(f"/accounting/accounts/{acc.id}", headers=self.headers1)
        self.assertEqual(response.status_code, 400)
        self.assertIn("transaction history", response.json()["detail"])

    def test_delete_non_leaf_rejected(self):
        parent = Account.objects.create(name="Parent", parent=self.root_asset, account_type="ASSET", family=self.family1)
        Account.objects.create(name="Child", parent=parent, account_type="ASSET", family=self.family1)
        
        response = self.client.delete(f"/accounting/accounts/{parent.id}", headers=self.headers1)
        self.assertEqual(response.status_code, 400)
        self.assertIn("has sub-accounts", response.json()["detail"])
