import json
import os
import requests # Import the requests library to make API calls
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .ml_engine import get_bot_response # This is our fact-finding brain
from .models import Conversation

# --- NEW: Function to humanize the response using Gemini ---
def humanize_response(factual_answer, user_message):
    """
    Takes a factual answer and a user's message, and uses the Gemini API
    to generate a more conversational, human-like response.
    """
    # IMPORTANT: In a real project, keep your API key secret.
    # For this project, we'll use a placeholder.
    API_KEY = "AIzaSyAlcdLhah3wihuNOtaQyXKtS6H8WhidwiQ" # You will need to get a key from Google AI Studio
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"

    # The prompt is the instruction we give to the AI
    prompt = f"""
    You are a friendly and helpful university assistant chatbot named Ask PU.
    Your user asked: "{user_message}"
    You have found the following factual information to answer them: "{factual_answer}"

    Please rewrite this factual information into a single, warm, conversational, and natural-sounding response.
    Do not add any new information that wasn't in the original fact.
    Keep the response concise and helpful.
    """

    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }

    try:
        # Make the API call to the Gemini model
        response = requests.post(API_URL, json=payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status() # Raises an error for bad responses (4xx or 5xx)

        # Extract the generated text from the response
        data = response.json()
        generated_text = data['candidates'][0]['content']['parts'][0]['text']
        return generated_text.strip()

    except requests.exceptions.RequestException as e:
        print(f"Error calling Gemini API: {e}")
        # If the API call fails for any reason, just return the original factual answer
        return factual_answer
    except (KeyError, IndexError) as e:
        print(f"Error parsing Gemini API response: {e}")
        return factual_answer


class ChatbotAPIView(APIView):
    """
    API View to handle chatbot conversations.
    """
    def post(self, request, *args, **kwargs):
        user_message = request.data.get('message', '')

        if not user_message:
            return Response(
                {'error': 'Message cannot be empty.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Get the factual response from our trained ML engine
        factual_response = get_bot_response(user_message)

        # 2. NEW: Humanize the factual response
        humanized_bot_response = humanize_response(factual_response, user_message)

        # 3. Save the conversation to the database
        Conversation.objects.create(
            user_message=user_message,
            bot_response=humanized_bot_response, # Save the new human-like response
            language='en' # Simplified for now
        )

        # 4. Return the human-like response
        return Response(
            {'response': humanized_bot_response},
            status=status.HTTP_200_OK
        )
