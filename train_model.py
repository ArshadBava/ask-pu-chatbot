import json
import torch
from transformers import BertTokenizer, BertForSequenceClassification
from torch.optim import AdamW  # <-- CORRECTED IMPORT
from torch.utils.data import DataLoader, TensorDataset, random_split
from sklearn.preprocessing import LabelEncoder
import numpy as np

# --- 1. Configuration ---
MODEL_NAME = 'bert-base-multilingual-cased'
INTENTS_FILE_PATH = 'chatbot/intents.json' # Path relative to the root folder
MODEL_SAVE_PATH = './askpu-model'
NUM_EPOCHS = 10 # Number of times to train on the data
BATCH_SIZE = 8
MAX_LENGTH = 128 # Max length of a sentence

# --- 2. Load and Prepare Data ---
print("Loading and preparing data...")

with open(INTENTS_FILE_PATH, 'r', encoding='utf-8') as f:
    intents_data = json.load(f)

texts = []
labels = []
for intent in intents_data['intents']:
    for lang, patterns in intent['patterns'].items():
        for pattern in patterns:
            texts.append(pattern)
            labels.append(intent['tag'])

# Encode the string labels into numbers
label_encoder = LabelEncoder()
encoded_labels = label_encoder.fit_transform(labels)
num_labels = len(np.unique(encoded_labels))

print(f"Found {len(texts)} patterns and {num_labels} unique intents.")

# --- 3. Tokenization ---
print(f"Loading tokenizer: {MODEL_NAME}")
tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)

print("Tokenizing texts...")
inputs = tokenizer(texts, padding=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt")

# --- 4. Create PyTorch Dataset ---
dataset = TensorDataset(inputs['input_ids'], inputs['attention_mask'], torch.tensor(encoded_labels))

# Split into training and validation sets (90% train, 10% validation)
train_size = int(0.9 * len(dataset))
val_size = len(dataset) - train_size
train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

print(f"Training set size: {len(train_dataset)}")
print(f"Validation set size: {len(val_dataset)}")

# --- 5. Load and Configure the Model ---
print(f"Loading model: {MODEL_NAME}")
model = BertForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=num_labels)

# Use GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
print(f"Using device: {device}")

# --- 6. Training ---
optimizer = AdamW(model.parameters(), lr=2e-5)

print("Starting training...")
for epoch in range(NUM_EPOCHS):
    model.train()
    total_train_loss = 0
    for batch in train_loader:
        batch = [t.to(device) for t in batch]
        input_ids, attention_mask, labels = batch

        model.zero_grad()
        outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
        loss = outputs.loss
        total_train_loss += loss.item()
        loss.backward()
        optimizer.step()

    avg_train_loss = total_train_loss / len(train_loader)
    print(f"Epoch {epoch + 1}/{NUM_EPOCHS} | Training Loss: {avg_train_loss:.4f}")

    # --- 7. Validation ---
    model.eval()
    total_eval_accuracy = 0
    with torch.no_grad():
        for batch in val_loader:
            batch = [t.to(device) for t in batch]
            input_ids, attention_mask, labels = batch

            outputs = model(input_ids, attention_mask=attention_mask, labels=labels)
            logits = outputs.logits
            preds = torch.argmax(logits, dim=1).flatten()
            accuracy = (preds == labels).cpu().numpy().mean()
            total_eval_accuracy += accuracy

    avg_val_accuracy = total_eval_accuracy / len(val_loader)
    print(f"Epoch {epoch + 1}/{NUM_EPOCHS} | Validation Accuracy: {avg_val_accuracy:.4f}")

print("Training complete!")

# --- 8. Save the Model and Tokenizer ---
print(f"Saving model to {MODEL_SAVE_PATH}...")
model.save_pretrained(MODEL_SAVE_PATH)
tokenizer.save_pretrained(MODEL_SAVE_PATH)

# Save the label encoder as well, which is crucial for decoding predictions
import pickle
with open(f'{MODEL_SAVE_PATH}/label_encoder.pkl', 'wb') as f:
    pickle.dump(label_encoder, f)

print("Model, tokenizer, and label encoder saved successfully!")

