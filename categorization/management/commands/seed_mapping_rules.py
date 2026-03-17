from django.core.management.base import BaseCommand

from banking.models import FinancialInstitution
from categorization.models import TransactionMappingRule
from dictionairies import banniere_dict_vd, banniere_dict_ws


class Command(BaseCommand):
    help = "Seed transaction mapping rules from Wealthsimple and Visa Desjardins dictionaries"

    def handle(self, *args, **options):
        wealthsimple = self._find_institution(["Wealthsimple"])
        desjardins = self._find_institution(["Desjardins"])

        if not wealthsimple:
            self.stdout.write(self.style.WARNING("Wealthsimple institution not found; skipping Wealthsimple rules."))
        else:
            ws_count = self._seed_dict(banniere_dict_ws, wealthsimple)
            self.stdout.write(self.style.SUCCESS(f"Seeded/verified {ws_count} Wealthsimple rules."))

        if not desjardins:
            self.stdout.write(self.style.WARNING("Desjardins institution not found; skipping Desjardins rules."))
        else:
            vd_count = self._seed_dict(banniere_dict_vd, desjardins)
            self.stdout.write(self.style.SUCCESS(f"Seeded/verified {vd_count} Desjardins rules."))

    def _find_institution(self, names):
        for name in names:
            institution = FinancialInstitution.objects.filter(name__iexact=name).first()
            if institution:
                return institution
        return None

    def _seed_dict(self, mapping_dict, institution):
        count = 0
        for merchant_name, search_values in mapping_dict.items():
            if not isinstance(search_values, list):
                continue

            for search_text in search_values:
                if not search_text:
                    continue

                TransactionMappingRule.objects.get_or_create(
                    search_text=search_text.strip(),
                    institution=institution,
                    defaults={
                        "merchant_name": merchant_name,
                        "target_account": None,
                    },
                )
                count += 1
        return count

