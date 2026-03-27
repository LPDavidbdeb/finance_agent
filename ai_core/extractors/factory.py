from .strategies import VisaDesjardinsExtractor, MasterCardWealthSimpleExtractor, CompteDesjardinsExtractor, TangerineExtractor


class PDFExtractorFactory:
    @staticmethod
    def get_extractor(institution_name: str, product_type: str = None):
        """
        Select the appropriate PDF extractor.

        Legacy path: both institution_name and product_type are provided.
          The extractor is chosen by the combination (e.g. Desjardins CREDIT_CARD).

        Multi-product path (future): only institution_name is provided
          (product_type=None). The extractor must be able to parse a consolidated
          statement and emit rows with an `account_number` column for per-row routing.
          Raise ValueError until a multi-product extractor is implemented.
        """
        if "Desjardins" in institution_name:
            if product_type == "CREDIT_CARD":
                return VisaDesjardinsExtractor()
            return CompteDesjardinsExtractor()
        elif "Wealthsimple" in institution_name:
            return MasterCardWealthSimpleExtractor()
        elif "Tangerine" in institution_name and product_type is None:
            # Multi-product consolidated extractor — no product_type required.
            return TangerineExtractor()

        raise ValueError(f"No extractor built yet for {institution_name} - {product_type}")