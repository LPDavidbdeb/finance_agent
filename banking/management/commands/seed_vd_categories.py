import runpy
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from banking.models import FinancialInstitution
from categorization.models import Merchant, TransactionMappingRule
from users.models import Family
import os


class Command(BaseCommand):
    help = 'Seeds Desjardins non-unique-provider merchants and mapping rules from vd_not_unique_provider_dict.'

    def handle(self, *args, **kwargs):
        # 1. Load dictionary
        file_path = os.path.join(settings.BASE_DIR, 'vd_categories.py')
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"vd_categories.py not found in {settings.BASE_DIR}"))
            return

        try:
            vd_data = runpy.run_path(file_path).get('vd_not_unique_provider_dict')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading file: {e}"))
            return

        if not vd_data:
            self.stdout.write(self.style.ERROR("'vd_not_unique_provider_dict' not found in file."))
            return

        # 2. Resolve family and institution
        family = Family.objects.first()
        if not family:
            self.stdout.write(self.style.ERROR("No family found in database."))
            return

        try:
            desjardins = FinancialInstitution.objects.get(name='Desjardins')
        except FinancialInstitution.DoesNotExist:
            self.stdout.write(self.style.ERROR("Institution 'Desjardins' not found."))
            return

        merchants_created = 0
        rules_created = 0

        with transaction.atomic():
            for banner_name, search_strings in vd_data.items():
                merchant, created = Merchant.objects.get_or_create(
                    name=banner_name.strip().upper(),
                    family=family,
                    defaults={'is_unique_provider': False, 'default_account': None}
                )
                if created:
                    merchants_created += 1
                elif merchant.is_unique_provider:
                    merchant.is_unique_provider = False
                    merchant.save()

                self.stdout.write(f"\n{'[+]' if created else '[=]'} Merchant: {merchant.name}")

                for search_string in search_strings:
                    _, r_created = TransactionMappingRule.objects.get_or_create(
                        merchant=merchant,
                        search_text=search_string,
                        institution=desjardins,
                    )
                    if r_created:
                        self.stdout.write(self.style.SUCCESS(f"    [+] Rule: {search_string}"))
                        rules_created += 1
                    else:
                        self.stdout.write(f"    [=] Exists: {search_string}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone — {merchants_created} merchants created, {rules_created} rules created."
        ))
