import json
import json
import random
import os
import torch
import pickle
from transformers import BertTokenizer, BertForSequenceClassification
from thefuzz import fuzz

# --- 1. Load All Necessary Components ---

# Define paths
MODEL_PATH = './askpu-model'
INTENTS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'intents.json')

# Load the trained model and tokenizer
print("Loading fine-tuned model and tokenizer...")
model = BertForSequenceClassification.from_pretrained(MODEL_PATH)
tokenizer = BertTokenizer.from_pretrained(MODEL_PATH)
print("Model and tokenizer loaded successfully.")

# Load the label encoder
print("Loading label encoder...")
with open(os.path.join(MODEL_PATH, 'label_encoder.pkl'), 'rb') as f:
    label_encoder = pickle.load(f)
print("Label encoder loaded successfully.")

# Load the intents data for responses
with open(INTENTS_FILE_PATH, 'r', encoding='utf-8') as file:
    intents_data = json.load(file)

# Use GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval() # Set the model to evaluation mode

# --- 2. The Main Prediction and Response Function ---

def get_bot_response(user_message):
    """
    Analyzes the user's message using a hybrid approach:
    1. Try the ML model for a high-confidence prediction.
    2. If confidence is low, fall back to robust fuzzy string matching.
    """
    # --- Step A: Predict the Intent using the ML Model ---
    CONFIDENCE_THRESHOLD = 0.75 # Keep this high for the primary model

    inputs = tokenizer(user_message, return_tensors="pt", padding=True, truncation=True, max_length=128)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits

    probabilities = torch.nn.functional.softmax(logits, dim=-1)[0]
    predicted_index = torch.argmax(probabilities).item()
    predicted_confidence = probabilities[predicted_index].item()
    predicted_tag = label_encoder.inverse_transform([predicted_index])[0]

    # --- Debugging print statement ---
    print(f"--- AI DEBUG ---")
    print(f"User Message: '{user_message}'")
    print(f"ML Model Predicted Intent: '{predicted_tag}' with {predicted_confidence:.2f} confidence")

    # If ML model is highly confident, use its prediction
    if predicted_confidence >= CONFIDENCE_THRESHOLD:
        print("--> Using ML Model Prediction")
        print(f"--------------------")
        for intent in intents_data['intents']:
            if intent['tag'] == predicted_tag:
                # Determine language and respond
                best_lang_score = 0
                detected_language = 'en'
                for lang, patterns in intent['patterns'].items():
                    for pattern in patterns:
                        score = fuzz.ratio(user_message.lower(), pattern.lower())
                        if score > best_lang_score:
                            best_lang_score = score
                            detected_language = lang
                return random.choice(intent['responses'][detected_language])

    # --- Step B: Fallback to Fuzzy String Matching if ML confidence is low ---
    print("--> ML confidence too low. Falling back to Fuzzy Matching.")
    FUZZY_MATCH_THRESHOLD = 70 # Threshold for fuzzy matching
    best_fuzzy_score = 0
    best_fuzzy_tag = None
    detected_fuzzy_language = 'en'

    for intent in intents_data['intents']:
        for lang, patterns in intent['patterns'].items():
            for pattern in patterns:
                score = fuzz.token_set_ratio(user_message.lower(), pattern.lower())
                if score > best_fuzzy_score:
                    best_fuzzy_score = score
                    best_fuzzy_tag = intent['tag']
                    detected_fuzzy_language = lang

    print(f"Fuzzy Match Best Intent: '{best_fuzzy_tag}' with {best_fuzzy_score} score")
    print(f"--------------------")
    
    if best_fuzzy_score >= FUZZY_MATCH_THRESHOLD:
        for intent in intents_data['intents']:
            if intent['tag'] == best_fuzzy_tag:
                return random.choice(intent['responses'][detected_fuzzy_language])

    # If both methods fail, return a default response
    return "I'm sorry, I'm not sure how to respond to that. Could you please try rephrasing?"
