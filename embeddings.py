from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
import requests

app = FastAPI()

# ✅ CORS (IMPORTANT for UI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load model + index
model = SentenceTransformer('all-MiniLM-L6-v2')
index = faiss.read_index("data/index.faiss")
data = pickle.load(open("data/data.pkl", "rb"))

# 🔍 Search function
def search(query, k=3):
    q_emb = model.encode([query])
    D, I = index.search(np.array(q_emb), k)

    results = [data[i] for i in I[0]]
    scores = D[0]

    return results, scores

# 🤖 Streaming LLM (Ollama)
def stream_llm(query, context):
    prompt = f"""
You are a Senior SRE.

User issue:
{query}

Internal knowledge:
{context}

Instructions:
- Prioritize internal solution
- Give step-by-step troubleshooting
- Include commands
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": True
        },
        stream=True
    )

    for line in response.iter_lines():
        if line:
            try:
                data = line.decode("utf-8")
                import json
                parsed = json.loads(data)
                yield parsed.get("response", "")
            except:
                continue

# 🚀 API endpoint
@app.get("/ask-stream")
def ask_stream(query: str):
    results, scores = search(query)
    context = "\n".join([r['solution'] for r in results])

    return StreamingResponse(
        stream_llm(query, context),
        media_type="text/plain"
    )

# Optional root
@app.get("/")
def home():
    return {"message": "SREGPT running 🚀"}