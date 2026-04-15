import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finance_backend.settings.local')
import django
django.setup()

from users.models import Family
from accounting.models import Account, JournalEntry, TransactionLine, CategoryMonthlyStat, InsightFact, AnalysisRun

families = Family.objects.all()
print('families', families.count())
print('analysis_runs', AnalysisRun.objects.count())
print('insight_facts', InsightFact.objects.count())
print('category_monthly_stats', CategoryMonthlyStat.objects.count())
for f in families:
    print(
        'FAMILY', f.id, f.name,
        'accounts', Account.objects.filter(family=f).count(),
        'journal_entries', JournalEntry.objects.filter(family=f).count(),
        'reconciled', JournalEntry.objects.filter(family=f, is_reconciled=True).count(),
        'lines', TransactionLine.objects.filter(journal_entry__family=f).count(),
        'reconciled_lines', TransactionLine.objects.filter(journal_entry__family=f, journal_entry__is_reconciled=True).count(),
    )

