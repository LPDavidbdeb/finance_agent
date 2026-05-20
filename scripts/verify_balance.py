from accounting.models import Account, TransactionLine
from django.db.models import Sum
from users.models import Family

family = Family.objects.get(name="709rueBeaudoin")

def get_branch_balance(name):
    account = Account.objects.filter(family=family, name=name).first()
    if not account: return 0
    ids = account.get_descendants(include_self=True).values_list('id', flat=True)
    return TransactionLine.objects.filter(account_id__in=ids).aggregate(Sum('amount'))['amount__sum'] or 0

total_assets = get_branch_balance("Assets")
total_liabilities = get_branch_balance("Liabilities")

print(f"TOTAL ASSETS:      ${total_assets:,.2f}")
print(f"TOTAL LIABILITIES: ${total_liabilities:,.2f}")
print(f"NET WORTH:         ${(total_assets + total_liabilities):,.2f}")
