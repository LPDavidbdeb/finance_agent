from decimal import Decimal, InvalidOperation


def validate_pdf_magic_bytes(file_content: bytes) -> None:
    """Raise ValueError when uploaded bytes do not match a PDF signature."""
    if not file_content.startswith(b"%PDF"):
        raise ValueError("Only PDF files are accepted.")

def validate_statement_math(raw_json: dict) -> list[str]:
    """
    Performs strict mathematical validation on the extracted statement data.
    Returns a list of error strings, which is empty if validation passes.
    """
    errors = []
    
    try:
        # 1. Extract balances and transactions
        starting_balance = Decimal(str(raw_json['starting_balance']))
        ending_balance = Decimal(str(raw_json['ending_balance']))
        transactions = raw_json.get('transactions', [])

        if not transactions:
            errors.append("The AI did not extract any transactions.")

        # 2. Sum the transaction amounts using Decimal
        sum_of_transactions = sum(Decimal(str(tx['amount'])) for tx in transactions)

        # 3. Calculate the expected ending balance
        expected_ending = starting_balance + sum_of_transactions
        
        # 4. Compare expected vs actual ending balance
        # We allow a small tolerance for potential rounding differences.
        tolerance = Decimal('0.01')
        if abs(expected_ending - ending_balance) > tolerance:
            error_msg = (
                f"Math validation failed. "
                f"Starting: {starting_balance:.2f} + "
                f"Transactions Sum: {sum_of_transactions:.2f} = "
                f"Expected Ending: {expected_ending:.2f}. "
                f"Actual Ending Balance was: {ending_balance:.2f}."
            )
            errors.append(error_msg)

    except (KeyError, TypeError) as e:
        errors.append(f"Validation failed due to missing key in AI JSON: {str(e)}. The AI's output was malformed.")
    except InvalidOperation as e:
        errors.append(f"Validation failed due to invalid number format in AI JSON: {str(e)}. Check balances and amounts.")
    
    return errors
