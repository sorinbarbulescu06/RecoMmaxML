import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Config:
    # Folosim .strip() ca sa evitam spatiile goale puse din greseala
    API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-3.1-flash-lite").strip()

    @classmethod
    def has_api(cls) -> bool:
        # E valid doar daca avem string si daca nu e valoarea default din .env.example
        return bool(cls.API_KEY and cls.API_KEY != "your_api_key_here")