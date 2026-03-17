from datetime import date
from dateutil.relativedelta import relativedelta
from enum import Enum

class PaymentFrequency(str, Enum):
    DAILY = 'DAILY'
    WEEKLY = 'WEEKLY'
    BIWEEKLY = 'BIWEEKLY'
    MONTHLY = 'MONTHLY'
    ANNUALLY = 'ANNUALLY'

def compute_n_periods(target_date: date, frequency: PaymentFrequency, start_date: date = None) -> int:
    """
    Calculates "n" (number of periods) for actuarial formulas to figure out 
    required funding PMTs to hit specific milestone dates.
    """
    if start_date is None:
        start_date = date.today()

    if target_date <= start_date:
        return 0

    if frequency in [PaymentFrequency.DAILY, PaymentFrequency.WEEKLY, PaymentFrequency.BIWEEKLY]:
        # Use raw timedelta days
        delta_days = (target_date - start_date).days
        
        if frequency == PaymentFrequency.DAILY:
            return delta_days
        elif frequency == PaymentFrequency.WEEKLY:
            return delta_days // 7
        elif frequency == PaymentFrequency.BIWEEKLY:
            return delta_days // 14
            
    elif frequency in [PaymentFrequency.MONTHLY, PaymentFrequency.ANNUALLY]:
        # Use dateutil to accurately count calendar passing
        delta = relativedelta(target_date, start_date)
        
        total_months = (delta.years * 12) + delta.months
        
        # If there are residual days, we generally round down for conservative PMT calculations,
        # but you can adjust this logic based on exact business requirements.
        
        if frequency == PaymentFrequency.MONTHLY:
            return total_months
        elif frequency == PaymentFrequency.ANNUALLY:
            return delta.years

    return 0
