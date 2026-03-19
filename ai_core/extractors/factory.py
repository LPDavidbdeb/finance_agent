from .strategies import VisaDesjardinsExtractor, MasterCardWealthSimpleExtractor, CompteDesjardinsExtractor


class PDFExtractorFactory:
    @staticmethod
    def get_extractor(institution_name: str, product_type: str):
        if "Desjardins" in institution_name:
            if product_type == "CREDIT_CARD":
                return VisaDesjardinsExtractor()
            return CompteDesjardinsExtractor()
        elif "Wealthsimple" in institution_name:
            # Route all Wealthsimple accounts to this extractor for now
            return MasterCardWealthSimpleExtractor()

        raise ValueError(f"No extractor built yet for {institution_name} - {product_type}")