import json
import random
import os
import torch
from thefuzz import fuzz
from transformers import BertTokenizer, BertForSequenceClassification

# --- CONFIGURATION ---
MODEL_PATH = './askpu-model'
CONFIDENCE_THRESHOLD = 0.60  # We lowered this before, let's keep it here for now

# --- Load ML Model and Tokenizer ---
try:
    tokenizer = BertTokenizer.from_pretrained(MODEL_PATH)
    model = BertForSequenceClassification.from_pretrained(MODEL_PATH)
    model.eval() # Set the model to evaluation mode
    print("✅ ML Model loaded successfully.")
except Exception as e:
    print(f"❌ Error loading ML model: {e}")
    model = None
    tokenizer = None

# --- Load Intents Data ---
intents_file_path = os.path.join(os.path.dirname(__file__), 'intents.json')
with open(intents_file_path, 'r', encoding='utf-8') as file:
    intents_data = json.load(file)

# --- Create a mapping from label index to tag name ---
label_to_tag = {i: intent['tag'] for i, intent in enumerate(intents_data['intents'])}

# --- Default Fallback Responses ---
DEFAULT_RESPONSES = {
    'en': "I'm sorry, I'm not sure how to respond to that. Could you please try rephrasing?",
    'hi': "मुझे क्षमा करें, मैं यह समझ नहीं पा रहा हूँ। क्या आप अपना प्रश्न फिर से पूछ सकते हैं?",
    'ml': "ക്ഷമിക്കണം, എനിക്കത് മനസ്സിലായില്ല. നിങ്ങളുടെ ചോദ്യം ഒന്നു മാറ്റി ചോദിക്കാമോ?"
}

def predict_intent(text):
    if not model or not tokenizer:
        return "error", 0.0
    inputs = tokenizer(text, return_tensors='pt', truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits
    probabilities = torch.softmax(logits, dim=1)
    confidence, predicted_class = torch.max(probabilities, dim=1)
    return label_to_tag[predicted_class.item()], confidence.item()

def get_fuzzy_response(user_message):
    """
    Finds the best response using fuzzy matching.
    NOW CORRECTLY RETURNS A TUPLE (response, tag).
    """
    best_match_score = 0
    best_match_tag = None
    detected_language = 'en'
    MATCH_THRESHOLD = 70

    for intent in intents_data['intents']:
        for lang, patterns in intent['patterns'].items():
            for pattern in patterns:
                score = fuzz.token_set_ratio(user_message.lower(), pattern.lower())
                if score > best_match_score:
                    best_match_score = score
                    best_match_tag = intent['tag']
                    detected_language = lang
    
    if best_match_score >= MATCH_THRESHOLD:
        for intent in intents_data['intents']:
            if intent['tag'] == best_match_tag:
                response = random.choice(intent['responses'][detected_language])
                return response, best_match_tag # Return tuple

    # If no good fuzzy match is found
    return DEFAULT_RESPONSES['en'], "unknown_fallback" # Return tuple

def get_bot_response(user_message):
    """
    Main function to get a response. First tries the ML model, then falls back to fuzzy matching.
    NOW ALWAYS RETURNS A TUPLE.
    """
    predicted_tag, confidence = predict_intent(user_message)

    print("\n--- AI DEBUG ---")
    print(f"User Message: '{user_message}'")
    print(f"ML Model Predicted Intent: '{predicted_tag}' with {confidence:.2f} confidence")

    if confidence >= CONFIDENCE_THRESHOLD:
        print("--> ML model confidence is high. Using ML response.")
        for intent in intents_data['intents']:
            if intent['tag'] == predicted_tag:
                # For simplicity, we'll just choose the English response for now.
                # This could be enhanced to detect language as a separate step.
                response = random.choice(intent['responses']['en'])
                print("--------------------")
                return response, predicted_tag # Return tuple
    
    print("--> ML confidence too low. Falling back to Fuzzy Matching.")
    response, tag = get_fuzzy_response(user_message)
    print(f"Fuzzy Match Best Intent: '{tag}' with score") # Corrected debug print
    print("--------------------")
    return response, tag # Return tuple

