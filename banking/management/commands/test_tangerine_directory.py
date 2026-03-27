"""
Dry-run validation command for the Tangerine consolidated ingestion pipeline.

Loops through every .pdf in a directory (chronologically by filename), creates a
BankStatementImport for each one, runs the full extraction pipeline synchronously,
prints a per-file summary, then rolls the entire database transaction back so the
local database is never polluted.

Usage:
    python manage.py test_tangerine_directory
    python manage.py test_tangerine_directory --dir /path/to/pdfs
    python manage.py test_tangerine_directory --dir /path/to/pdfs --family-id <uuid>
"""

import os
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

DEFAULT_DIR = "/Users/Louis-Philippe/Sites/709ruebeaudoin/data/Tangerine"


class Command(BaseCommand):
    help = (
        "Dry-run: parse every Tangerine PDF in a directory through the "
        "full extraction pipeline, print a per-file summary, then roll back."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default=DEFAULT_DIR,
            help=f"Directory containing Tangerine PDF statements (default: {DEFAULT_DIR})",
        )
        parser.add_argument(
            "--family-id",
            default=None,
            help="Family UUID to use for auto-spawned products. Defaults to first family.",
        )

    def handle(self, *args, **options):
        pdf_dir = options["dir"]
        family_id = options["family_id"]

        if not os.path.isdir(pdf_dir):
            raise CommandError(f"Directory not found: {pdf_dir}")

        pdf_files = sorted(
            f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")
        )
        if not pdf_files:
            raise CommandError(f"No PDF files found in {pdf_dir}")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Found {len(pdf_files)} PDF(s) in {pdf_dir}"
            )
        )
        self.stdout.write(
            self.style.WARNING("All database writes will be rolled back after the run.\n")
        )

        # Import inside handle() to avoid import-time Django setup issues
        from django.contrib.auth import get_user_model
        from banking.models import BankStatementImport, FinancialInstitution, FinancialProduct, StagedTransaction
        from banking.extraction import extract_transactions_from_statement
        from users.models import Family

        User = get_user_model()

        try:
            with transaction.atomic():
                # ---- Resolve institution ----
                institution = FinancialInstitution.objects.filter(name="Tangerine").first()
                if not institution:
                    raise CommandError(
                        "No FinancialInstitution named 'Tangerine' found. "
                        "Run: python manage.py seed_banks"
                    )

                # ---- Resolve family + user ----
                if family_id:
                    family = Family.objects.filter(id=family_id).first()
                    if not family:
                        raise CommandError(f"Family {family_id} not found.")
                else:
                    family = Family.objects.first()
                    if not family:
                        raise CommandError("No Family records found in the database.")

                user = User.objects.filter(family=family).first()
                if not user:
                    raise CommandError(
                        f"No user found for family '{family.name}'. "
                        "Cannot run pipeline without a user context."
                    )

                self.stdout.write(
                    f"Family: {family.name}  |  User: {user.email}  |  "
                    f"Institution: {institution.name}\n"
                )

                products_before = FinancialProduct.objects.filter(
                    institution=institution
                ).count()
                total_txs = 0
                total_spawned = 0

                # ---- Process each PDF ----
                for filename in pdf_files:
                    pdf_path = os.path.join(pdf_dir, filename)
                    products_at_start = FinancialProduct.objects.filter(
                        institution=institution
                    ).count()

                    # Create the import record (no financial_product = consolidated path)
                    stmt = BankStatementImport.objects.create(
                        institution=institution,
                        financial_product=None,
                        document_date=date(2020, 1, 1),  # placeholder — overwritten by PDF date
                        status=BankStatementImport.Status.STAGED,
                        processing_log=[],
                    )

                    # Attach the real PDF file via direct field assignment (no upload)
                    stmt.file.name = os.path.relpath(pdf_path, start="/")
                    stmt.save(update_fields=["file"])

                    try:
                        extract_transactions_from_statement(stmt.id, user)
                    except Exception as exc:
                        self.stdout.write(
                            self.style.ERROR(f"  [{filename}] PIPELINE ERROR: {exc}")
                        )
                        continue

                    stmt.refresh_from_db()
                    tx_count = StagedTransaction.objects.filter(
                        statement_import=stmt
                    ).count()
                    products_after = FinancialProduct.objects.filter(
                        institution=institution
                    ).count()
                    spawned = products_after - products_at_start

                    doc_date = stmt.document_date
                    date_str = (
                        doc_date.strftime("%B %Y") if doc_date else "date unknown"
                    )
                    status_style = (
                        self.style.SUCCESS
                        if stmt.status == BankStatementImport.Status.COMPLETED
                        else self.style.ERROR
                    )

                    spawn_note = (
                        f"  Auto-spawned {spawned} new product(s)." if spawned else ""
                    )
                    self.stdout.write(
                        status_style(
                            f"  [{filename}]  Parsed {date_str}.  "
                            f"{tx_count} transaction(s).{spawn_note}"
                        )
                    )
                    if stmt.status != BankStatementImport.Status.COMPLETED:
                        self.stdout.write(
                            self.style.ERROR(
                                f"    Status: {stmt.status}  "
                                f"Errors: {stmt.validation_errors}"
                            )
                        )

                    total_txs += tx_count
                    total_spawned += spawned

                # ---- Summary ----
                products_total = FinancialProduct.objects.filter(
                    institution=institution
                ).count()
                self.stdout.write(
                    "\n" + self.style.MIGRATE_HEADING("RUN SUMMARY")
                )
                self.stdout.write(f"  PDFs processed : {len(pdf_files)}")
                self.stdout.write(f"  Transactions   : {total_txs}")
                self.stdout.write(
                    f"  Products spawned this run : {products_total - products_before}"
                )
                self.stdout.write(
                    f"  Products total (would-be) : {products_total}"
                )

                # Force rollback — no permanent writes
                raise _Rollback()

        except _Rollback:
            self.stdout.write(
                self.style.WARNING("\nDatabase rolled back — no changes persisted.")
            )


class _Rollback(Exception):
    """Sentinel used to force a transaction rollback at the end of the dry run."""
