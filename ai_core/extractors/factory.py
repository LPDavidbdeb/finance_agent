from .strategies import (
    DesjardinsVisaExtractor,
    WealthsimpleInvestmentExtractor,
    TangerineSavingsExtractor,
    GenericStatementExtractor
)

def get_extractor(institution_name: str, product_type: str):
    """
    Factory function to retrieve the correct statement extractor strategy based on
    the financial institution and product type.
    """
    mapping = {
        ("Desjardins", "CREDIT_CARD"): DesjardinsVisaExtractor,
        ("Wealthsimple", "INVESTMENT"): WealthsimpleInvestmentExtractor,
        ("Tangerine", "SAVINGS"): TangerineSavingsExtractor,
        # Add more specific extractors here as they are created
    }

    # Attempt to fetch the specific strategy class
    strategy_class = mapping.get((institution_name, product_type))

    # Fallback to the generic extractor if no specific strategy is found
    if strategy_class is None:
        strategy_class = GenericStatementExtractor

    # Initialize and return the instantiated class
    return strategy_class()