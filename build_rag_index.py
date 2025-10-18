import os
import pymupdf  # PyMuPDF
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import pickle

# --- CONFIGURATION ---
PDF_PATH = "PGInformationBrochureas202516PG.pdf"  # Make sure this PDF is in the same folder
INDEX_PATH = "rag_data/faiss_index.bin"
CHUNKS_PATH = "rag_data/text_chunks.pkl"
MODEL_NAME = 'all-MiniLM-L6-v2'

def chunk_text(text, chunk_size=500, overlap=50):
    """Splits text into smaller, overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks

def build_index():
    """Reads a PDF, chunks its text, creates vector embeddings, and saves them to a FAISS index."""
    print("--- Starting RAG Index Building Process ---")
    
    # 1. Check if PDF exists
    if not os.path.exists(PDF_PATH):
        print(f"❌ ERROR: PDF file not found at '{PDF_PATH}'. Please place it in the root project folder.")
        return

    # 2. Extract text from PDF
    print(f"1/4 - Reading and extracting text from '{PDF_PATH}'...")
    doc = pymupdf.open(PDF_PATH)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()
    print(f"   -> Extracted {len(full_text)} characters.")

    # 3. Split text into chunks
    print("2/4 - Splitting text into manageable chunks...")
    text_chunks = chunk_text(full_text)
    print(f"   -> Created {len(text_chunks)} text chunks.")

    # 4. Create vector embeddings
    print(f"3/4 - Loading Sentence Transformer model ('{MODEL_NAME}') and creating embeddings...")
    print("      (This may take a few minutes and download the model on the first run)...")
    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(text_chunks, show_progress_bar=True)
    print(f"   -> Created {len(embeddings)} vector embeddings.")

    # 5. Build and save the FAISS index
    print("4/4 - Building and saving the FAISS index and text chunks...")
    os.makedirs("rag_data", exist_ok=True)
    
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(np.array(embeddings, dtype=np.float32))
    faiss.write_index(index, INDEX_PATH)

    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(text_chunks, f)

    print("\n✅ --- RAG Index Building Complete! ---")
    print(f"   -> Index saved to: {INDEX_PATH}")
    print(f"   -> Chunks saved to: {CHUNKS_PATH}")

if __name__ == "__main__":
    build_index()