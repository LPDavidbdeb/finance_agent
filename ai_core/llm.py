import google.generativeai as genai
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Centralized client for interacting with Gemini models.
    Uses settings from Django configuration.
    """
    _initialized = False

    @classmethod
    def _initialize(cls):
        if not cls._initialized:
            api_key = getattr(settings, 'GEMINI_API_KEY', None)
            if not api_key:
                logger.warning("GEMINI_API_KEY not found in settings. Gemini features will be disabled.")
                return False
            
            genai.configure(api_key=api_key)
            cls._initialized = True
        return cls._initialized

    @classmethod
    def get_model(cls, model_name=None):
        if not cls._initialize():
            return None
        
        if model_name is None:
            model_name = getattr(settings, 'DEFAULT_GEMINI_MODEL', 'gemini-3.1-flash-lite')
        
        # Ensure model name has the correct prefix
        if not model_name.startswith('models/'):
            model_name = f"models/{model_name}"
            
        try:
            return genai.GenerativeModel(model_name)
        except Exception as e:
            logger.error(f"Error initializing Gemini model {model_name}: {str(e)}")
            return None

    @classmethod
    def generate_content(cls, prompt, model_name=None):
        model = cls.get_model(model_name)
        if not model:
            return None
        
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {str(e)}")
            return None
