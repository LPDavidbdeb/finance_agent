from ninja import Router, Schema
from ninja_jwt.authentication import JWTAuth
from django.core.management import call_command
from django.core.management.base import CommandError
import io
from typing import List, Optional

router = Router(auth=JWTAuth())

class CommandRequestIn(Schema):
    command: str
    args: List[str] = []

class CommandResponseOut(Schema):
    success: bool
    output: str
    error: Optional[str] = None

# Safety: White-list of allowed commands
ALLOWED_COMMANDS = [
    'ledger_reset',
    'reprocess_all_statements',
    'verify_ledger_integrity',
    'fix_inverted_transactions'
]

@router.get("/celery-status")
def get_celery_status(request):
    """
    Checks if the Celery worker is running by inspecting active workers.
    """
    from finance_backend.celery import app
    try:
        # We use a timeout to avoid hanging if the broker is unreachable
        inspect = app.control.inspect(timeout=1.0)
        active_workers = inspect.active()
        is_running = active_workers is not None and len(active_workers) > 0
        return {"is_running": is_running, "worker_count": len(active_workers) if active_workers else 0}
    except Exception as e:
        return {"is_running": False, "error": str(e)}

@router.post("/run-command", response=CommandResponseOut)
def run_management_command(request, payload: CommandRequestIn):
    """
    Executes a white-listed Django management command and returns the output.
    Only accessible by superusers for safety.
    """
    if not request.auth.is_superuser:
        return {
            "success": False, 
            "output": "", 
            "error": "Access Denied: Only superusers can run maintenance commands."
        }

    if payload.command not in ALLOWED_COMMANDS:
        return {
            "success": False, 
            "output": "", 
            "error": f"Command '{payload.command}' is not in the allowed white-list."
        }

    # Capture stdout and stderr
    out = io.StringIO()
    err = io.StringIO()
    
    try:
        # Resolve arguments (e.g. ['--confirm'] or ['--family-id', 'uuid'])
        # Split args into pos and kwargs if needed, but call_command handles list of strings mostly
        # We need to parse --flags from the list
        
        call_command(payload.command, *payload.args, stdout=out, stderr=err)
        
        return {
            "success": True,
            "output": out.getvalue(),
            "error": err.getvalue() or None
        }
    except CommandError as e:
        return {
            "success": False,
            "output": out.getvalue(),
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "output": out.getvalue(),
            "error": f"Internal System Error: {str(e)}"
        }
