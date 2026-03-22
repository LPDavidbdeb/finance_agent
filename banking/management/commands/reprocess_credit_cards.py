from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Sum, Value, When
from django.db.models.functions import Coalesce

from accounting.models import JournalEntry
from banking.extraction import extract_transactions_from_statement
from banking.models import BankStatementImport, FinancialProduct, StagedTransaction
from users.models import Family


class Command(BaseCommand):
    help = "Reprocess credit-card statement imports for a family with optional product/date scope."

    def add_arguments(self, parser):
        parser.add_argument("--family-id", required=True, type=str)
        parser.add_argument("--product-id", type=int)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--from-date", type=str, help="YYYY-MM-DD")

    def _sign_distribution_for_products(self, product_ids):
        qs = StagedTransaction.objects.filter(statement_import__financial_product_id__in=product_ids)
        return qs.aggregate(
            total=Count("id"),
            pos=Coalesce(Sum(Case(When(amount__gt=0, then=1), default=0, output_field=IntegerField())), Value(0)),
            neg=Coalesce(Sum(Case(When(amount__lt=0, then=1), default=0, output_field=IntegerField())), Value(0)),
            net=Coalesce(Sum("amount"), Value(0)),
        )

    def handle(self, *args, **options):
        family_id = options["family_id"]
        product_id = options.get("product_id")
        dry_run = options["dry_run"]
        from_date = options.get("from_date")

        try:
            family = Family.objects.get(id=family_id)
        except Family.DoesNotExist:
            raise CommandError(f"Family not found: {family_id}")

        products = FinancialProduct.objects.filter(
            family=family,
            product_type=FinancialProduct.ProductType.CREDIT_CARD,
        )
        if product_id:
            products = products.filter(id=product_id)

        product_ids = list(products.values_list("id", flat=True))
        if not product_ids:
            raise CommandError("No credit-card products in scope.")

        imports = BankStatementImport.objects.filter(financial_product_id__in=product_ids).order_by("id")
        if from_date:
            try:
                parsed_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("--from-date must be YYYY-MM-DD")
            imports = imports.filter(created_at__date__gte=parsed_date)

        import_ids = list(imports.values_list("id", flat=True))
        self.stdout.write(f"Family: {family_id}")
        self.stdout.write(f"Product scope: {product_ids}")
        self.stdout.write(f"Imports in scope: {len(import_ids)}")

        before = self._sign_distribution_for_products(product_ids)
        self.stdout.write(
            f"Before staged signs: total={before['total']}, +={before['pos']}, -={before['neg']}, net={before['net']}"
        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("DRY RUN COMPLETE"))
            return

        user = family.users.first()
        if not user:
            raise CommandError("No family user found to run extraction.")

        for stmt in imports:
            with transaction.atomic():
                staged_qs = StagedTransaction.objects.filter(statement_import=stmt)
                journal_entry_ids = list(
                    staged_qs.filter(journal_entry__isnull=False).values_list("journal_entry_id", flat=True)
                )

                if journal_entry_ids:
                    JournalEntry.objects.filter(id__in=journal_entry_ids).delete()

                staged_qs.delete()

                stmt.status = BankStatementImport.Status.PENDING
                stmt.processed_by_python = False
                stmt.validation_errors = None
                stmt.save(update_fields=["status", "processed_by_python", "validation_errors"])

            extract_transactions_from_statement(stmt.id, user)

        after = self._sign_distribution_for_products(product_ids)
        self.stdout.write(
            f"After staged signs: total={after['total']}, +={after['pos']}, -={after['neg']}, net={after['net']}"
        )
        self.stdout.write(self.style.SUCCESS("REPROCESS COMPLETE"))

