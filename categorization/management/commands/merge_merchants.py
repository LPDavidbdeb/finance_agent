from django.core.management.base import BaseCommand
from django.db import transaction
from categorization.models import Merchant, TransactionMappingRule
from banking.models import StagedTransaction

class Command(BaseCommand):
    help = 'Merges duplicate Merchant entries into a target Merchant.'

    def add_arguments(self, parser):
        parser.add_argument('--target', type=int, required=True, help='ID of the Merchant to keep.')
        parser.add_argument('--sources', type=int, nargs='+', required=True, help='IDs of the Merchants to merge and delete.')

    def handle(self, *args, **options):
        target_id = options['target']
        source_ids = options['sources']

        if target_id in source_ids:
            self.stderr.write(self.style.ERROR('Target ID cannot be in the sources list.'))
            return

        with transaction.atomic():
            # 1. Validation
            try:
                target_merchant = Merchant.objects.get(id=target_id)
            except Merchant.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Target Merchant with ID {target_id} does not exist.'))
                return

            source_merchants = Merchant.objects.filter(id__in=source_ids)
            if source_merchants.count() != len(source_ids):
                found_ids = set(source_merchants.values_list('id', flat=True))
                missing_ids = set(source_ids) - found_ids
                self.stderr.write(self.style.ERROR(f'Source Merchant IDs not found: {missing_ids}'))
                return

            # Verify same family
            for source in source_merchants:
                if source.family_id != target_merchant.family_id:
                    self.stderr.write(self.style.ERROR(f'Merchant {source.name} (ID {source.id}) belongs to a different family.'))
                    return

            source_names = list(source_merchants.values_list('name', flat=True))

            # 2. Transfer Rules
            rules = TransactionMappingRule.objects.filter(merchant_id__in=source_ids)
            rules_count = rules.count()
            rules.update(merchant=target_merchant)

            # 3. Historical Cleanup (StagedTransactions)
            # Find transactions where clean_description exactly matches the names of the source merchants
            txs = StagedTransaction.objects.filter(clean_description__in=source_names)
            tx_count = txs.count()
            txs.update(clean_description=target_merchant.name)

            # 4. Deletion
            deleted_count = source_merchants.count()
            source_merchants.delete()

            self.stdout.write(self.style.SUCCESS(
                f'Successfully merged {deleted_count} merchants into "{target_merchant.name}" (ID {target_id}).\n'
                f'Rules transferred: {rules_count}\n'
                f'Transactions updated: {tx_count}'
            ))
