# chatbot/rag_utils.py
import os
import json
import re
import logging
from typing import List, Tuple, Optional, Dict

try:
    from PyPDF2 import PdfReader  # keep if you use PDF search
except Exception:
    PdfReader = None

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAQ_FILE_PATH = os.path.join(BASE_DIR, "faqs.json")
PDF_FOLDER_PATH = os.path.join(BASE_DIR, "documents")

# Load the intents structure
try:
    with open(FAQ_FILE_PATH, "r", encoding="utf-8") as f:
        FAQS_RAW = json.load(f)
    INTENTS = FAQS_RAW.get("intents") if isinstance(FAQS_RAW, dict) else FAQS_RAW
    if not isinstance(INTENTS, list):
        logger.warning("faqs.json 'intents' not found or malformed; expecting list")
        INTENTS = []
    logger.info("Loaded %d intents from %s", len(INTENTS), FAQ_FILE_PATH)
except FileNotFoundError:
    logger.warning("FAQ file not found at %s", FAQ_FILE_PATH)
    INTENTS = []
except Exception as e:
    logger.exception("Failed to load faqs.json: %s", e)
    INTENTS = []


def _normalize(text: str) -> str:
    """Lowercase + remove punctuation (but keep unicode letters)"""
    if not text:
        return ""
    text = text.lower()
    # keep unicode letters, numbers and spaces, remove punctuation
    text = re.sub(r"[^\w\s\u00A0-\uFFFF]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Build an index of pattern -> (intent, lang) for quick matching
_PATTERN_INDEX: List[Dict] = []
for intent in INTENTS:
    tag = intent.get("tag", "")
    patterns = intent.get("patterns", {}) or {}
    responses = intent.get("responses", {}) or {}
    # patterns is dict of language -> list
    if isinstance(patterns, dict):
        for lang_code, pat_list in patterns.items():
            if not isinstance(pat_list, list):
                continue
            for pat in pat_list:
                pat_norm = _normalize(pat)
                if not pat_norm:
                    continue
                _PATTERN_INDEX.append({
                    "pattern": pat_norm,
                    "tag": tag,
                    "lang": lang_code,
                    "responses": responses
                })
    elif isinstance(patterns, list):
        # legacy: patterns as list (no language)
        for pat in patterns:
            pat_norm = _normalize(pat)
            if not pat_norm:
                continue
            _PATTERN_INDEX.append({
                "pattern": pat_norm,
                "tag": tag,
                "lang": "en",
                "responses": responses
            })

# optional: sort index by pattern length desc to prefer long patterns
_PATTERN_INDEX.sort(key=lambda x: len(x["pattern"]), reverse=True)


def get_response_from_json(user_message: str, prefer_lang: str = "en") -> Tuple[Optional[str], int]:
    """
    Returns (answer, score).
    - Scans configured intents.patterns (all languages).
    - If an exact pattern match occurs -> very high score.
    - Else tries containment of pattern words -> lower score.
    - prefer_lang: 'en','hi','ml' - pick response in that language if available, else any available language.
    """
    if not INTENTS or not _PATTERN_INDEX:
        return None, 0

    msg_norm = _normalize(user_message)

    best_answer = None
    best_score = 0
    best_tag = None

    # 1) Exact pattern match (highest priority)
    for item in _PATTERN_INDEX:
        if item["pattern"] == msg_norm:
            # pick response by preferred language if present
            resp_dict = item.get("responses") or {}
            answer = None
            if prefer_lang and prefer_lang in resp_dict:
                arr = resp_dict.get(prefer_lang)
                if isinstance(arr, list) and arr:
                    answer = arr[0]
            # fallback to any language available
            if not answer:
                for v in resp_dict.values():
                    if isinstance(v, list) and v:
                        answer = v[0]
                        break
            if answer:
                return answer, 100 + len(msg_norm)  # very high score for exact

    # 2) Containment match: check if pattern words are present in message
    # We'll treat each pattern as candidate; score by length of matched pattern
    for item in _PATTERN_INDEX:
        pat = item["pattern"]
        if pat and pat in msg_norm:
            score = len(pat)
            if score > best_score:
                resp_dict = item.get("responses") or {}
                answer = None
                if prefer_lang and prefer_lang in resp_dict:
                    arr = resp_dict.get(prefer_lang)
                    if isinstance(arr, list) and arr:
                        answer = arr[0]
                if not answer:
                    for v in resp_dict.values():
                        if isinstance(v, list) and v:
                            answer = v[0]
                            break
                if answer:
                    best_score = score
                    best_answer = answer
                    best_tag = item.get("tag")

    # 3) If still nothing, attempt token-based fuzzy match: check overlap of keywords
    if not best_answer:
        tokens = set(re.findall(r'\b\w{3,}\b', msg_norm))
        if tokens:
            for intent in INTENTS:
                # gather all patterns text for that intent
                all_patterns = []
                patterns_block = intent.get("patterns") or {}
                if isinstance(patterns_block, dict):
                    for pats in patterns_block.values():
                        if isinstance(pats, list):
                            all_patterns.extend([_normalize(p) for p in pats if p])
                elif isinstance(patterns_block, list):
                    all_patterns.extend([_normalize(p) for p in patterns_block if p])
                combined = " ".join(all_patterns)
                if not combined:
                    continue
                matches = sum(1 for t in tokens if t in combined)
                if matches >= 2:
                    # choose prefer_lang response if available
                    resp_dict = intent.get("responses") or {}
                    answer = None
                    if prefer_lang and prefer_lang in resp_dict:
                        arr = resp_dict.get(prefer_lang)
                        if isinstance(arr, list) and arr:
                            answer = arr[0]
                    if not answer:
                        for v in resp_dict.values():
                            if isinstance(v, list) and v:
                                answer = v[0]
                                break
                    if answer:
                        return answer, matches

    if best_answer:
        return best_answer, best_score

    return None, 0


def generate_suggestions_from_faq(user_message: str, n: int = 3, prefer_lang: str = "en") -> List[str]:
    """
    Produce up to `n` suggested follow-up *question* strings based on faqs.json.
    Strategy:
      - Tokenize the user_message and compare against intent patterns in preferred language first.
      - Score candidates by token overlap and pattern length, then return top N unique patterns.
      - If there are not enough relevant suggestions, append a small set of useful fallbacks.
    """
    suggestions: List[str] = []
    if not INTENTS or not _PATTERN_INDEX or not user_message:
        return ["Admissions", "Fee Structure", "About the campus"][:n]

    msg_norm = _normalize(user_message)
    tokens = set(re.findall(r'\b\w{3,}\b', msg_norm))
    candidates: List[Tuple[int, str]] = []

    # Search patterns preferring prefer_lang
    for item in _PATTERN_INDEX:
        pat_text = item.get("pattern", "")
        if not pat_text:
            continue
        # prefer patterns in same language as prefer_lang
        lang_score = 1 if item.get("lang") == prefer_lang else 0
        # score token overlap
        p_tokens = set(re.findall(r'\b\w{3,}\b', pat_text))
        overlap = len(tokens & p_tokens)
        total_score = overlap * 10 + len(pat_text.split()) + (5 * lang_score)
        if overlap > 0:
            candidates.append((total_score, pat_text))

    # Sort candidates by score desc
    candidates.sort(key=lambda x: -x[0])

    seen = set()
    for _, p in candidates:
        # convert normalized pattern back to a nicer display if possible: try to find original pattern string
        pretty = None
        for intent in INTENTS:
            patterns_block = intent.get("patterns") or {}
            # check prefer_lang patterns first
            if isinstance(patterns_block, dict) and prefer_lang in patterns_block:
                for orig in patterns_block.get(prefer_lang, []):
                    if _normalize(orig) == p:
                        pretty = orig.strip()
                        break
                if pretty:
                    break
            # check other languages
            if isinstance(patterns_block, dict):
                for lang_k, arr in patterns_block.items():
                    for orig in (arr or []):
                        if _normalize(orig) == p:
                            pretty = orig.strip()
                            break
                    if pretty:
                        break
            elif isinstance(patterns_block, list):
                for orig in patterns_block:
                    if _normalize(orig) == p:
                        pretty = orig.strip()
                        break
            if pretty:
                break

        pretty_text = pretty or p.capitalize()
        if pretty_text not in seen and pretty_text.lower() != user_message.lower():
            suggestions.append(pretty_text)
            seen.add(pretty_text)
        if len(suggestions) >= n:
            break

    # If not enough suggestions, add useful fallbacks (localized if possible)
    if len(suggestions) < n:
        fallback_en = ["Admissions", "Fee Structure", "About the campus", "How do I apply?"]
        fallback_hi = ["प्रवेश प्रक्रिया", "शुल्क संरचना", "कैंपस के बारे में"]
        fallback_ml = ["പ്രവേശന നടപടിക്രമം", "ഫീസ് ഘടന", "ക്യാമ്പസിനെ കുറിച്ച്"]

        fallback = {"en": fallback_en, "hi": fallback_hi, "ml": fallback_ml}.get(prefer_lang, fallback_en)
        for f in fallback:
            if f not in seen:
                suggestions.append(f)
                seen.add(f)
            if len(suggestions) >= n:
                break

    return suggestions[:n]


def detect_lang_from_text(text: str) -> str:
    """
    Very small heuristic language detector based on common words/characters.
    Returns 'en'|'hi'|'ml' (default 'en').
    This is intentionally simple — swap for a real language-detector if needed.
    """
    if not text:
        return "en"
    t = text.strip().lower()
    # check for Devanagari characters (Hindi)
    if re.search(r'[\u0900-\u097F]', t):
        return "hi"
    # check for Malayalam block
    if re.search(r'[\u0D00-\u0D7F]', t):
        return "ml"
    # check for a few Hindi words (in latin script)
    hi_words = ["namaste", "namaskaram", "dhanyavaad", "shukriya", "kaise", "kya"]
    for w in hi_words:
        if w in t:
            return "hi"
    # fallback to english
    return "en"


# Keep your existing find_relevant_pdf_chunks implementation below if you use PDFs.
def find_relevant_pdf_chunks(user_message: str, max_chunks: int = 3) -> List[str]:
    if not os.path.isdir(PDF_FOLDER_PATH):
        logger.warning("PDF folder not found: %s", PDF_FOLDER_PATH)
        return []
    if not user_message:
        return []
    keywords = set(re.findall(r'\b\w{4,}\b', user_message.lower()))
    if not keywords:
        return []
    results: List[str] = []
    if PdfReader is None:
        logger.warning("PyPDF2 not available; PDF search disabled.")
        return results
    try:
        for filename in os.listdir(PDF_FOLDER_PATH):
            if not filename.lower().endswith(".pdf"):
                continue
            path = os.path.join(PDF_FOLDER_PATH, filename)
            try:
                reader = PdfReader(path)
                for pnum, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    paragraphs = re.split(r'\n\s*\n', text)
                    for para in paragraphs:
                        para_lower = para.lower()
                        matches = sum(1 for k in keywords if k in para_lower)
                        if matches >= 2 and len(para.strip()) > 50:
                            results.append(para.strip().replace("\n", " "))
                            if len(results) >= max_chunks:
                                return results
            except Exception as e:
                logger.exception("error reading %s: %s", filename, e)
    except Exception as e:
        logger.exception("pdf search error: %s", e)
    return results
