from django.core.management.base import BaseCommand
from banking.models import FinancialInstitution

class Command(BaseCommand):
    help = 'Seeds the database with major Canadian financial institutions.'

    def handle(self, *args, **kwargs):
        institutions = [
            "Desjardins",
            "National Bank of Canada",
            "Royal Bank of Canada (RBC)",
            "Toronto-Dominion Bank (TD)",
            "Bank of Montreal (BMO)",
            "Scotiabank",
            "Canadian Imperial Bank of Commerce (CIBC)",
            "Tangerine",
            "Wealthsimple",
            "Sun Life Financial"
        ]

        count = 0
        for name in institutions:
            obj, created = FinancialInstitution.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created institution: {name}'))
                count += 1
            else:
                self.stdout.write(self.style.WARNING(f'Institution already exists: {name}'))

        self.stdout.write(self.style.SUCCESS(f'\nFinished seeding. Added {count} new institutions.'))