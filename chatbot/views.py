# chatbot/views.py
import json
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# Import the helpers from rag_utils (make sure these exist in rag_utils.py)
from .rag_utils import (
    get_response_from_json,
    find_relevant_pdf_chunks,
    generate_suggestions_from_faq,
    detect_lang_from_text,
)
from .models import Conversation
import re  # For extracting suggestions


# --- 1. Load API Key and Configure Gemini ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in .env file.")
    genai.configure(api_key=GEMINI_API_KEY)

    # --- This is our System Instruction (Persona) ---
    SYSTEM_INSTRUCTION = """
    You are "Ask PU", a specialized AI assistant *only for Pondicherry University*.
    Your personality is friendly, concise, and professional.
    Your *sole purpose* is to answer questions directly related to Pondicherry University,
    using your internal knowledge. This includes its courses, departments, faculty,
    facilities, admissions, history, location, events, rules, etc.

    *CRITICAL INSTRUCTION:* If the user asks a question that is *NOT* specifically
    about Pondicherry University (e.g., general knowledge like 'What is the capital
    of France?', current world events, facts about other places), you *MUST* politely
    decline to answer. State clearly that you can only provide information about
    Pondicherry University.

    *Follow-up Suggestion:* AFTER providing an answer about Pondicherry University,
    suggest ONE relevant follow-up question the user might logically ask next.
    Phrase it naturally (e.g., "Would you also like to know about...?"). If you
    suggest a follow-up, append a tag like [SUGGESTION: specific topic suggested]
    to the VERY END of your response.
    """

    # Initialize the Gemini model
    gemini_model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        system_instruction=SYSTEM_INSTRUCTION
    )

    print("✅ Gemini model configured successfully.")

except Exception as e:
    print(f"❌ FATAL ERROR: Could not configure Gemini: {e}")
    gemini_model = None


# --- Helper: Extract suggestion tag ---
def extract_suggestion(text):
    match = re.search(r'\[SUGGESTION:\s*(.*?)\s*\]', text)
    if match:
        suggestion = match.group(1).strip()
        cleaned_text = text[:match.start()].strip()
        return cleaned_text, suggestion
    return text, None


# --- Main Chat API View ---
class ChatbotAPIView(APIView):

    def post(self, request, *args, **kwargs):
        user_message = (request.data.get('message') or '').strip()
        history = request.data.get('history', []) or []

        if not user_message:
            return Response({'error': 'Message cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        if not gemini_model:
            return Response({'error': 'AI Model is not configured. Check server logs.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        bot_response = ""
        bot_response_raw = ""
        original_user_message_for_db = user_message

        # --- Suggestion Handling ---
        is_affirmative = user_message.lower() in ['yes', 'yep', 'yeah', 'ok', 'okay', 'sure', 'please', 'do it']
        last_bot_message_text = history[-1]['text'] if history and history[-1].get('sender') == 'bot' else None
        suggested_topic = None

        if last_bot_message_text:
            _, suggested_topic = extract_suggestion(last_bot_message_text)

        if is_affirmative and suggested_topic:
            print(f"--- Affirmative reply detected. User accepted suggestion: '{suggested_topic}' ---")
            user_message = suggested_topic
            history = history[:-1]  # use history before suggestion

        # --- Detect user language (en | hi | ml) ---
        user_lang = detect_lang_from_text(user_message)
        print(f"Detected user language: {user_lang}")

        # --- Step A: Try JSON FAQ first (try prefer_lang if available) ---
        try:
            json_answer, score = get_response_from_json(user_message, prefer_lang=user_lang)
        except TypeError:
            # fallback if rag_utils.get_response_from_json expects single arg
            json_answer, score = get_response_from_json(user_message)

        # If JSON FAQ is a confident match, return immediately + suggestions
        if json_answer and score >= 4:
            Conversation.objects.create(
                user_message=user_message,
                bot_response=json_answer,
                language=user_lang
            )
            suggestions = generate_suggestions_from_faq(user_message, n=3, prefer_lang=user_lang)
            return Response({
                'response': json_answer,
                'source': 'FAQ JSON',
                'lang': user_lang,
                'suggestions': suggestions
            }, status=status.HTTP_200_OK)

        # --- Step B: Try PDF Search (RAG) ---
        pdf_chunks = find_relevant_pdf_chunks(user_message)
        pdf_context = None
        user_prompt = user_message  # default to the user's raw message
        used_rag = False

        if pdf_chunks:
            used_rag = True
            pdf_context = "\n\n".join(pdf_chunks)

            # small language hint to ask model to respond in user's language
            lang_hint = {
                'en': "Answer in English.",
                'hi': "Answer in Hindi (हिन्दी).",
                'ml': "Answer in Malayalam (മലയാളം)."
            }.get(user_lang, "Answer in English.")

            user_prompt = (
                f"The user asked: {user_message}\n\n"
                f"Refer to the following official Pondicherry University documents for context:\n\n{pdf_context}\n\n"
                f"Now provide a concise, factual answer using only the given context when possible.\n{lang_hint}"
            )

            print("PDF context found — using RAG prompt for Gemini.")

        # --- Step C: Send to Gemini (with history) ---
        try:
            # Build chat history for Gemini (if your client provides it)
            chat_history_for_gemini = []
            for msg in history:
                role = "user" if msg.get('sender') == 'user' else "model"
                chat_history_for_gemini.append({
                    "role": role,
                    "parts": [{"text": msg.get("text", "")}]
                })

            chat_session = gemini_model.start_chat(history=chat_history_for_gemini)

            print(f"--- Sending to Gemini (RAG={used_rag}): '{user_prompt[:200]}' ---")
            response = chat_session.send_message(user_prompt)

            # response.text holds final text in typical genai SDK
            bot_response_raw = getattr(response, "text", "") or (response.get("text") if isinstance(response, dict) else "")
            print(f"--- Final Answer from Gemini: '{bot_response_raw[:200]}...' ---")

        except google_exceptions.InvalidArgument as e:
            print(f"❌ Error during Gemini chat (InvalidArgument - 400): {e}")
            bot_response_raw = "I'm sorry, I couldn't process that request. Please try rephrasing."
        except Exception as e:
            print(f"❌ Error during Gemini chat session: {e}")
            bot_response_raw = "I'm sorry, I'm having trouble connecting to my knowledge base. Please try again later."

        # --- Clean response (remove suggestion tag) ---
        bot_response, auto_suggestion = extract_suggestion(bot_response_raw)

        # Save to DB with detected language
        Conversation.objects.create(
            user_message=original_user_message_for_db,
            bot_response=bot_response,
            language=user_lang
        )

        # Generate UI suggestions (language aware) — prefer intent-based suggestions from faqs
        try:
            suggestions = generate_suggestions_from_faq(user_message, n=3, prefer_lang=user_lang)
        except Exception:
            suggestions = ["Admissions", "Fee Structure", "About the campus"]

        # If Gemini returned an inline suggestion tag, prefer that as first suggestion
        if auto_suggestion and auto_suggestion not in suggestions:
            suggestions.insert(0, auto_suggestion)
            suggestions = suggestions[:3]

        return Response({
            'response': bot_response,
            'source': 'Gemini (RAG)' if used_rag else 'Gemini',
            'lang': user_lang,
            'suggestions': suggestions
        }, status=status.HTTP_200_OK)
# --- End of ChatbotAPIView ---