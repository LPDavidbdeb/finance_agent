import re
from django.core.management.base import BaseCommand
from categorization.models import TransactionMappingRule
from banking.models import StagedTransaction
from categorization.services import normalize_text

class Command(BaseCommand):
    help = 'Audits TransactionMappingRules to count how many StagedTransactions they match.'

    def handle(self, *args, **options):
        rules = TransactionMappingRule.objects.all()
        transactions = StagedTransaction.objects.all()
        
        self.stdout.write(f"Analyzing {rules.count()} rules against {transactions.count()} transactions...\n")
        
        # Pre-calculate normalized descriptions for performance
        normalized_txs = [
            (tx, normalize_text(tx.raw_description)) for tx in transactions
        ]

        zero_match_rules = []
        total_matched = 0

        for rule in rules:
            # Clean the rule's search text using the same aggressive logic
            clean_search_text = re.sub(r'\s+', ' ', rule.search_text).strip().lower()
            
            match_count = 0
            for tx, norm_desc in normalized_txs:
                if clean_search_text in norm_desc:
                    match_count += 1
            
            if match_count == 0:
                zero_match_rules.append((rule, clean_search_text))
            else:
                self.stdout.write(f"[SUCCESS] Rule '{clean_search_text}' matched {match_count} transactions.")
                total_matched += match_count

        self.stdout.write(self.style.WARNING(f"\n--- AUDIT COMPLETE ---"))
        self.stdout.write(f"Total successful rule applications: {total_matched}")
        self.stdout.write(f"Found {len(zero_match_rules)} rules with ZERO matches:")
        
        for rule, clean_text in zero_match_rules:
            self.stdout.write(f"  - Rule ID: {rule.id} | Search Text: '{clean_text}' | Merchant: {rule.merchant.name}")
