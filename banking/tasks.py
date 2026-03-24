from celery import shared_task
from banking.extraction import extract_transactions_from_statement
from users.models import CustomUser
import logging

logger = logging.getLogger(__name__)

@shared_task
def extract_transactions_task(statement_import_id, user_id):
    """
    Celery task to run the extraction pipeline in the background.
    """
    from banking.models import BankStatementImport
    try:
        user = CustomUser.objects.get(id=user_id)
        extract_transactions_from_statement(statement_import_id, user)
    except CustomUser.DoesNotExist:
        logger.error(f"User with ID {user_id} not found. Background extraction failed.")
        BankStatementImport.objects.filter(id=statement_import_id).update(status=BankStatementImport.Status.FAILED)
    except Exception as e:
        logger.exception(f"Error in background extraction for statement {statement_import_id}: {str(e)}")
        BankStatementImport.objects.filter(id=statement_import_id).update(status=BankStatementImport.Status.FAILED)
