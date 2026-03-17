from google import genai
from google.genai import types
from abc import ABC, abstractmethod
from banking.models import BankStatementImport
import json
import os
from dotenv import load_dotenv

load_dotenv()

class BaseStatementExtractor(ABC):
    """
    Abstract base class for statement extraction using a Template Method Pattern.
    """

    def __init__(self):
        # Configure the new Gemini client
        api_key = os.environ.get("GEMINI_API_KEY", "")
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.5-flash'

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
        uploaded_file = self.client.files.upload(file=file_path)

        try:
            # 2. Call the model with the specific prompt and schema
            prompt = self.get_system_prompt()
            schema = self.get_json_schema()

            print("Sending request to Gemini API...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, uploaded_file],
                config=types.GenerateContentConfig(
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
            self.client.files.delete(name=uploaded_file.name)
            print("File cleanup complete.")