from .base import BaseStatementExtractor

class GenericStatementExtractor(BaseStatementExtractor):
    """A fallback extractor for unknown institutions."""
    def get_system_prompt(self) -> str:
        return (
            "Extract all transactions from the statement. "
            "You must identify the statement's starting balance and ending balance. "
            "Identify the start date, end date, and all line items with a date, description, and amount."
        )

    def get_json_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Statement start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "description": "Statement end date (YYYY-MM-DD)"},
                "starting_balance": {"type": "number"},
                "ending_balance": {"type": "number"},
                "transactions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Transaction date (YYYY-MM-DD)"},
                            "description": {"type": "string"},
                            "amount": {"type": "number"}
                        },
                        "required": ["date", "description", "amount"]
                    }
                }
            },
            "required": ["start_date", "end_date", "starting_balance", "ending_balance", "transactions"]
        }

class DesjardinsVisaExtractor(BaseStatementExtractor):
    """Extractor for Desjardins Visa credit card statements."""
    def get_system_prompt(self) -> str:
        return (
            "Extract the credit card transactions from the Desjardins Visa statement. "
            "You must extract the 'Solde précédent' as starting_balance and 'Nouveau solde' as ending_balance. "
            "Pay special attention to separating the 'Date de transaction' from the 'Date d'inscription'. "
            "The primary date for the transaction is 'Date de transaction'. "
            "Also, find and extract the total BONIDOLLARS balance into the metadata section."
        )

    def get_json_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "starting_balance": {"type": "number", "description": "Solde précédent"},
                "ending_balance": {"type": "number", "description": "Nouveau solde"},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "bonidollars_balance": {"type": "number", "description": "Total Bonidollars earned."}
                    }
                },
                "transactions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "transaction_date": {"type": "string", "description": "Date de transaction (YYYY-MM-DD)"},
                            "posting_date": {"type": "string", "description": "Date d'inscription (YYYY-MM-DD)"},
                            "description": {"type": "string"},
                            "amount": {"type": "number"}
                        },
                        "required": ["transaction_date", "posting_date", "description", "amount"]
                    }
                }
            },
            "required": ["starting_balance", "ending_balance", "transactions"]
        }

class WealthsimpleInvestmentExtractor(BaseStatementExtractor):
    """Extractor for Wealthsimple investment statements."""
    def get_system_prompt(self) -> str:
        return (
            "Extract the investment ledger from the Wealthsimple statement. "
            "You must extract the starting and ending portfolio values for the period, labelling them starting_balance and ending_balance. "
            "Ignore any portfolio performance graphs or summary charts. "
            "Extract the 'Market Value' and 'Book Value' from the summary section as statement-level metadata. "
            "For each transaction, capture the Ticker symbol and the number of Shares."
        )

    def get_json_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "starting_balance": {"type": "number", "description": "Portfolio value at the start of the period."},
                "ending_balance": {"type": "number", "description": "Portfolio value at the end of the period."},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "market_value": {"type": "number"},
                        "book_value": {"type": "number"}
                    },
                    "required": ["market_value", "book_value"]
                },
                "transactions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Transaction date (YYYY-MM-DD)"},
                            "description": {"type": "string"},
                            "ticker": {"type": "string", "description": "Stock or ETF ticker symbol"},
                            "shares": {"type": "number", "description": "Quantity of shares"},
                            "amount": {"type": "number"}
                        },
                        "required": ["date", "description", "amount"]
                    }
                }
            },
            "required": ["starting_balance", "ending_balance", "metadata", "transactions"]
        }

class TangerineSavingsExtractor(BaseStatementExtractor):
    """Extractor for Tangerine savings account statements."""
    def get_system_prompt(self) -> str:
        return (
            "Extract all transactions from the Tangerine savings account statement. "
            "You must extract the 'Starting Balance' and 'Ending Balance' for the period. "
            "If there are any mentions of a GIC (Guaranteed Investment Certificate), "
            "extract its interest rate and maturity date into a separate metadata field."
        )

    def get_json_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "starting_balance": {"type": "number"},
                "ending_balance": {"type": "number"},
                "gic_details": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "interest_rate": {"type": "number"},
                            "maturity_date": {"type": "string", "description": "YYYY-MM-DD"}
                        }
                    }
                },
                "transactions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Transaction date (YYYY-MM-DD)"},
                            "description": {"type": "string"},
                            "amount": {"type": "number"}
                        },
                        "required": ["date", "description", "amount"]
                    }
                }
            },
            "required": ["starting_balance", "ending_balance", "transactions"]
        }
