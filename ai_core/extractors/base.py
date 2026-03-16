import google.generativeai as genai
from abc import ABC, abstractmethod
from banking.models import BankStatementImport
import json

class BaseStatementExtractor(ABC):
    """
    Abstract base class for statement extraction using a Template Method Pattern.
    """

    def __init__(self):
        # Configure the Gemini client (ensure API key is set in environment)
        genai.configure()
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Returns the specific system prompt for the AI model.
        This must be implemented by subclasses.
        """
        pass

    @abstractmethod
    def get_json_schema(self) -> dict:
        """
        Returns the JSON schema that the AI's output must conform to.
        This must be implemented by subclasses.
        """
        pass

    def execute(self, file_path: str, statement_import_id: int) -> dict:
        """
        The main execution template method.
        """
        print(f"Starting extraction for statement import ID: {statement_import_id}")

        # 1. Upload the file to Google's servers
        print(f"Uploading file: {file_path}")
        uploaded_file = genai.upload_file(path=file_path)

        try:
            # 2. Call the model with the specific prompt and schema
            prompt = self.get_system_prompt()
            schema = self.get_json_schema()

            print("Sending request to Gemini API...")
            response = self.model.generate_content(
                [prompt, uploaded_file],
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=schema
                )
            )

            # 3. Save the raw JSON to the BankStatementImport record
            print("Processing response and saving to database...")
            import_record = BankStatementImport.objects.get(id=statement_import_id)
            
            # The response text is a JSON string
            raw_json_text = response.text
            import_record.raw_ai_extraction = raw_json_text
            import_record.save(update_fields=['raw_ai_extraction'])
            
            print("Successfully saved AI extraction to the database.")
            
            # Return the parsed JSON dictionary
            return json.loads(raw_json_text)

        finally:
            # 4. Clean up the uploaded file
            print(f"Deleting uploaded file: {uploaded_file.name}")
            genai.delete_file(uploaded_file.name)
            print("File cleanup complete.")
