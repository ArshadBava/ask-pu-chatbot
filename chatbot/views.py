# In chatbot/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .nlp_engine import get_bot_response
from .models import Conversation

class ChatbotAPIView(APIView):
    """
    API View to handle chatbot conversations.
    """
    def post(self, request, *args, **kwargs):
        # 1. Get the user's message from the incoming request data
        user_message = request.data.get('message', '')

        if not user_message:
            return Response(
                {'error': 'Message cannot be empty.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Get the bot's response from our NLP engine
        bot_response = get_bot_response(user_message)

        # 3. (Optional but good practice) Save the conversation to the database
        # We can determine the language from the response for logging purposes
        # This is a simple heuristic; a more robust method could be added later
        lang = 'en' # default
        if any(c in 'नमस्ते' for c in bot_response):
            lang = 'hi'
        elif any(c in 'നമസ്കാരം' for c in bot_response):
            lang = 'ml'

        Conversation.objects.create(
            user_message=user_message,
            bot_response=bot_response,
            language=lang
        )

        # 4. Return the bot's response in a JSON format
        return Response(
            {'response': bot_response},
            status=status.HTTP_200_OK
        )