import json
import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .ml_engine import get_bot_response
from .models import Conversation

# --- RAG Setup: Load the indexed library (only once when the server starts) ---
import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer

RAG_INDEX = None
RAG_CHUNKS = None
RAG_MODEL = None
try:
    print("--- Loading RAG Index and Model ---")
    RAG_INDEX = faiss.read_index("rag_data/faiss_index.bin")
    with open("rag_data/text_chunks.pkl", "rb") as f:
        RAG_CHUNKS = pickle.load(f)
    RAG_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    print("✅ RAG components loaded successfully.")
except Exception as e:
    print(f"❌ WARNING: Could not load RAG components: {e}. PDF search will be disabled.")

# --- BRAIN 1: The Humanizer (for known facts from intents.json) ---
def humanize_response(factual_answer, user_message, history, intent_tag):
    if intent_tag in ['greeting', 'goodbye', 'thanks', 'chitchat_generic', 'chitchat_ask', 'chitchat_whoareyou']:
        return factual_answer
    
    API_KEY = "YOUR_GEMINI_API_KEY" # Replace with your key
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"

    formatted_history = ""
    for msg in history[-4:]:
        role = "User" if msg.get('sender') == 'user' else "Model"
        formatted_history += f"{role}: {msg.get('text', '')}\n"

    prompt = f"""
    You are Ask PU, a helpful university assistant. Your personality is friendly, concise, and direct.
    Your task is to rephrase the given "Factual Answer" into a natural, conversational response that directly answers the "User's Current Question".
    Use the "Conversation History" for context if needed.

    **Conversation History:**
    {formatted_history}
    **User's Current Question:** "{user_message}"
    **Factual Answer to use:** "{factual_answer}"

    **Strict Rules:**
    1. Directly answer the user's question using ONLY the information from the "Factual Answer".
    2. Do NOT add greetings like "Hi there" or "Of course!".
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(API_URL, json=payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Error in humanize_response: {e}")
        return factual_answer

# --- BRAIN 2: The Librarian (searches local PDF) ---
def get_pdf_rag_response(user_message, history):
    if not RAG_INDEX or not RAG_CHUNKS or not RAG_MODEL:
        print("--- PDF RAG components not loaded, skipping. ---")
        return "FALLBACK_TO_WEB_SEARCH"

    print("--- Engaging PDF RAG ---")
    question_embedding = RAG_MODEL.encode([user_message])
    distances, indices = RAG_INDEX.search(np.array(question_embedding, dtype=np.float32), k=3)

    context = "\n".join([RAG_CHUNKS[i] for i in indices[0]])

    API_KEY = "YOUR_GEMINI_API_KEY" # Replace with your key
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"
    
    prompt = f"""
    You are Ask PU, an expert AI assistant for Pondicherry University.
    Your task is to answer the user's question based ONLY on the provided "Context from Official Documents".

    **Context from Official Documents:**
    ---
    {context}
    ---

    **User's Question:** "{user_message}"

    **Strict Rules:**
    1.  If the answer to the question is present in the context, answer it directly.
    2.  If the answer is NOT in the context, you MUST respond with exactly the phrase: "FALLBACK_TO_WEB_SEARCH".
    3.  **Persona Guardrail:** If the user's question is not about Pondicherry University, its courses, or academic life, respond with: "I can only answer questions about Pondicherry University."
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        generated_text = data['candidates'][0]['content']['parts'][0]['text'].strip()
        return generated_text
    except Exception as e:
        print(f"Error in get_pdf_rag_response: {e}")
        return "FALLBACK_TO_WEB_SEARCH"

# --- BRAIN 3: The Researcher (Live Web Search) ---
def get_live_rag_response(user_message, history):
    API_KEY = "AIzaSyDAyRW8jQFNkVPEgi-jXyqcw7uBra4ebZU" # Replace with your key
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"
    
    gemini_history = []
    for msg in history[-4:]:
        role = "user" if msg.get('sender') == 'user' else "model"
        gemini_history.append({"role": role, "parts": [{"text": msg.get("text", "")}]})
    
    current_message = {"role": "user", "parts": [{"text": user_message}]}
    contents = gemini_history + [current_message]

    payload = {
        "contents": contents,
        "tools": [{"google_search_retrieval": {}}],
        "systemInstruction": {
            "parts": [{
                "text": """You are "Ask PU", an expert AI assistant for Pondicherry University. Your primary goal is to provide accurate answers to user questions based on a real-time Google Search.

                **Strict Rules:**
                1.  **Grounding is Mandatory:** Your answer MUST be based on the information you find from your web search.
                2.  **Handle Uncertainty:** If you cannot find a direct answer, you MUST state that you couldn't find specific information.
                3.  **Persona Guardrail:** If the user's question is not about Pondicherry University, its courses, or academic life, you MUST politely decline by saying: "I can only answer questions about Pondicherry University."
                """
            }]
        }
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Error in get_live_rag_response: {e}")
        return "I'm having trouble with my live search at the moment. Please try again."

# --- The Main API View with the 3-Layer Cascade ---
class ChatbotAPIView(APIView):
    def post(self, request, *args, **kwargs):
        user_message = request.data.get('message', '')
        history = request.data.get('history', [])
        
        if not user_message:
            return Response({'error': 'Message cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        bot_response = ""

        # --- LAYER 1: Check the fine-tuned model (the "Expert") ---
        factual_response, intent_tag = get_bot_response(user_message)
        
        if intent_tag and intent_tag != "unknown_fallback":
            print("--- Using Layer 1: Fine-tuned Model ---")
            bot_response = humanize_response(factual_response, user_message, history, intent_tag)
        else:
            # --- LAYER 2: Check the local PDF (the "Librarian") ---
            print("--- Layer 1 failed. Engaging Layer 2: PDF RAG ---")
            pdf_response = get_pdf_rag_response(user_message, history)
            
            if pdf_response and "FALLBACK_TO_WEB_SEARCH" not in pdf_response:
                bot_response = pdf_response
            else:
                # --- LAYER 3: Use Live Web Search (the "Researcher") ---
                print("--- Layer 2 failed. Engaging Layer 3: Live Web Search RAG ---")
                bot_response = get_live_rag_response(user_message, history)

        Conversation.objects.create(
            user_message=user_message,
            bot_response=bot_response,
            language='en'
        )
        return Response({'response': bot_response}, status=status.HTTP_200_OK)

