import json
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Conversation # Only import Conversation
import re # For extracting suggestions

# --- 1. Load API Key and Configure Gemini ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in .env file.")
    genai.configure(api_key=GEMINI_API_KEY)
    
    # --- This is our System Instruction (Persona) ---
    # We tell the AI how to behave.
    SYSTEM_INSTRUCTION = """
    You are "Ask PU", a specialized AI assistant *only for Pondicherry University*.
    Your personality is friendly, concise, and professional.
    Your *sole purpose* is to answer questions directly related to Pondicherry University, using your internal knowledge. This includes its courses, departments, faculty (if known generally), facilities, admissions, history, location, events, rules, etc.

    *CRITICAL INSTRUCTION:* If the user asks a question that is *NOT* specifically about Pondicherry University (e.g., general knowledge like 'What is the capital of France?', current world events, facts about other places), you *MUST* politely decline to answer. State clearly that you can only provide information about Pondicherry University.

    *Follow-up Suggestion:* AFTER providing an answer about Pondicherry University, suggest ONE relevant follow-up question the user might logically ask next. Phrase it naturally (e.g., "Would you also like to know about...?"). 
    If you suggest a follow-up, append a tag like [SUGGESTION: specific topic suggested] to the VERY END of your response. If no logical follow-up comes to mind, omit the suggestion and the tag.
    """
    
    # Initialize the Gemini model with our persona
    gemini_model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        system_instruction=SYSTEM_INSTRUCTION
    )
    
    # Start a chat session. This will automatically remember history.
    # We create a new session for every API call for simplicity,
    # but pass history from the client.
    print("✅ Gemini model configured successfully.")

except Exception as e:
    print(f"❌ FATAL ERROR: Could not configure Gemini: {e}")
    gemini_model = None

# --- Helper to extract suggestion (remains the same) ---
def extract_suggestion(text):
    match = re.search(r'\[SUGGESTION:\s*(.*?)\s*\]', text)
    if match:
        suggestion = match.group(1).strip()
        cleaned_text = text[:match.start()].strip()
        return cleaned_text, suggestion
    return text, None

# --- The Main API View (Now SIMPLE) ---
class ChatbotAPIView(APIView):

    def post(self, request, *args, **kwargs):
        user_message = request.data.get('message', '').strip()
        history = request.data.get('history', []) # History from client

        if not user_message:
            return Response({'error': 'Message cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not gemini_model:
            return Response({'error': 'AI Model is not configured. Check server logs.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        bot_response = ""
        bot_response_raw = ""
        original_user_message_for_db = user_message

        # --- Suggestion Handling Logic ---
        is_affirmative = user_message.lower() in ['yes', 'yep', 'yeah', 'ok', 'okay', 'sure', 'please', 'do it']
        last_bot_message_text = history[-1]['text'] if history and history[-1]['sender'] == 'bot' else None
        suggested_topic = None

        if last_bot_message_text:
            _, suggested_topic = extract_suggestion(last_bot_message_text)

        if is_affirmative and suggested_topic:
            print(f"--- Affirmative reply detected. User accepted suggestion: '{suggested_topic}' ---")
            user_message = suggested_topic # Override user message for this turn
            history = history[:-1] # Use history *before* the bot's suggestion
        # --- End Suggestion Handling ---
        
        try:
            # --- Start a new chat session for this request ---
            # We pass the history from the client to the model
            chat_history_for_gemini = []
            for msg in history:
                role = "user" if msg.get('sender') == 'user' else "model"
                chat_history_for_gemini.append({"role": role, "parts": [{"text": msg.get("text", "")}]})
            
            # Start a chat with the existing history
            chat_session = gemini_model.start_chat(history=chat_history_for_gemini)
            
            print(f"--- Sending to Gemini: '{user_message}' ---")
            # Send the new message
            response = chat_session.send_message(user_message)

            bot_response_raw = response.text
            print(f"--- Final Answer from Gemini: '{bot_response_raw[:100]}...' ---")

        except google_exceptions.InvalidArgument as e:
            print(f"❌ Error during Gemini chat (InvalidArgument - 400): {e}")
            bot_response_raw = "I'm sorry, I couldn't process that request. Please try rephrasing."
        except Exception as e:
            print(f"❌ Error during Gemini chat session: {e}")
            bot_response_raw = "I'm sorry, I'm having trouble connecting to my knowledge base. Please try again later."

        # --- Clean the final response (remove suggestion tag) ---
        bot_response, _ = extract_suggestion(bot_response_raw)

        # Log conversation
        Conversation.objects.create(
            user_message=original_user_message_for_db,
            bot_response=bot_response,
            language='en' 
        )
        return Response({'response': bot_response}, status=status.HTTP_200_OK)