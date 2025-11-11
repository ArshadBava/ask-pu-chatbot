# chatbot/utils.py
import re

# Unicode ranges for Malayalam and Devanagari (Hindi)
_RE_MALAYALAM = re.compile(r'[\u0D00-\u0D7F]')
_RE_DEVANAGARI = re.compile(r'[\u0900-\u097F]')

def detect_lang_from_text(text: str) -> str:
    """
    Very small heuristic detector:
      - returns 'ml' if Malayalam characters found
      - returns 'hi' if Devanagari (Hindi) found
      - otherwise returns 'en'
    Works well for ML / HI / EN inputs (good for chat UI).
    """
    if not text or not text.strip():
        return 'en'
    if _RE_MALAYALAM.search(text):
        return 'ml'
    if _RE_DEVANAGARI.search(text):
        return 'hi'
    return 'en'
