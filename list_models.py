# list_models.py
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY missing from .env")

# Try legacy google.generativeai first
try:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    print("Using google.generativeai SDK (legacy). Listing models:")
    for m in genai.list_models():
        # `m` is a Model dataclass in the legacy SDK
        print(getattr(m, "name", str(m)))
except Exception as e1:
    print("Legacy sdk failed:", e1)

# Try the new google-genai SDK next
try:
    from google import genai as genai_new
    client = genai_new.Client()
    print("\nUsing google-genai SDK. Listing models:")
    for m in client.list_models():
        # model objects vary; print something useful
        print(getattr(m, "name", getattr(m, "model", str(m))))
except Exception as e2:
    print("google-genai sdk failed:", e2)
