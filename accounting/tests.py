from django.test import TestCase
from django.contrib.auth import get_user_model
from ninja.testing import TestClient
from finance_backend.api import api
from users.models import Family
from accounting.models import Account, JournalEntry, TransactionLine
from decimal import Decimal
from ninja_jwt.tokens import AccessToken

User = get_user_model()

class AccountingApiTest(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        
        # Create Families
        self.family_a = Family.objects.create(name="Family A")
        self.family_b = Family.objects.create(name="Family B")
        
        # Create Users
        self.user_a = User.objects.create_user(email="user_a@example.com", password="password", family=self.family_a)
        self.user_b = User.objects.create_user(email="user_b@example.com", password="password", family=self.family_b)
        
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
