import json
import random
import os

# Build the path to intents.json dynamically
intents_file_path = os.path.join(os.path.dirname(__file__), 'intents.json')

# Load the intents from the JSON file
with open(intents_file_path, 'r', encoding='utf-8') as file:
    intents_data = json.load(file)

# Default responses for when the bot doesn't understand
DEFAULT_RESPONSES = {
    'en': "I'm sorry, I don't understand. Could you please rephrase?",
    'hi': "मुझे क्षमा करें, मैं यह समझ नहीं पा रहा हूँ। क्या आप अपना प्रश्न फिर से पूछ सकते हैं?",
    'ml': "ക്ഷമിക്കണം, എനിക്കത് മനസ്സിലായില്ല. നിങ്ങളുടെ ചോദ്യം ഒന്നു മാറ്റി ചോദിക്കാമോ?"
}

def get_bot_response(user_message):
    """
    Analyzes the user's message and returns the best response from the intents.
    The language is determined by which pattern matches.
    """
    user_words = set(user_message.lower().split())

    best_match_score = 0
    best_match_tag = None
    detected_language = 'en' # Default to English

    # Iterate through each intent to find the best match
    for intent in intents_data['intents']:
        # Iterate through each language's patterns in the intent
        for lang, patterns in intent['patterns'].items():
            for pattern in patterns:
                pattern_words = set(pattern.lower().split())
                common_words = user_words.intersection(pattern_words)
                score = len(common_words)

                # Update best match if this pattern is better
                if score > best_match_score:
                    best_match_score = score
                    best_match_tag = intent['tag']
                    detected_language = lang # The language of the matched pattern!

    # If a good match is found, return a response in the detected language
    if best_match_score > 0:
        for intent in intents_data['intents']:
            if intent['tag'] == best_match_tag:
                # Get a random response for the detected language
                return random.choice(intent['responses'][detected_language])

    # If no match is found, return a default response (we can guess or just use English)
    # For simplicity, we'll just use the English default for now.
    return DEFAULT_RESPONSES['en']


# --- Example Usage (for testing) ---
if __name__ == '__main__':
    print("Bot is ready! (type 'quit' to exit)")
    while True:
        message = input("You: ")
        if message.lower() == 'quit':
            break
        response = get_bot_response(message)
        print(f"Bot: {response}")