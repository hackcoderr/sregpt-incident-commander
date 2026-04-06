from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
import requests
import json

app = FastAPI()

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Load model + index
model = SentenceTransformer('all-MiniLM-L6-v2')
index = faiss.read_index("data/index.faiss")
data = pickle.load(open("data/data.pkl", "rb"))

# 🔥 Normalize data
def normalize_record(record):
    return {
        "issue": record.get("issue") or record.get("Issue Subject") or "",
        "solution": record.get("solution") or record.get("Issue Solution") or "",
        "ticket": record.get("ticket") or record.get("Ticket ID") or "N/A"
    }

# 🔍 Search Top K
def search(query, k=50):
    q_emb = model.encode([query])
    D, I = index.search(np.array(q_emb), k)

    results = [normalize_record(data[i]) for i in I[0]]
    scores = D[0]

    return results, scores


def filter_results(results, scores, threshold=0.7):
    filtered = []

    for r, score in zip(results, scores):
        confidence = 1 / (1 + score)

        if confidence > threshold:
            filtered.append(r)

    return filtered

# 🧠 Build reasoning context
def build_context(results):
    context = []
    for r in results:
        context.append(
            f"Ticket: {r['ticket']} | Issue: {r['issue']} | Fix: {r['solution']}"
        )
    return "\n".join(context)

# 🤖 Reasoning LLM (CORE UPGRADE)
def stream_reasoning(query, context):
    prompt = f"""
You are a Senior SRE with strong reasoning ability.

User Issue:
{query}

Past Incidents:
{context}

Instructions:
- Analyze ALL incidents carefully
- Identify patterns
- Find the most likely root cause
- Do NOT just repeat solutions
- Think like a production SRE

Output format:

## 🔍 Root Cause
Explain WHY this is happening

## 🛠 Fix Steps
Step-by-step actionable fix

## 🎫 Related Tickets
List relevant tickets

## 📊 Confidence
Explain WHY you are confident (not percentage only)
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "deepseek-coder:6.7b",   # 🔥 change here if needed
            "prompt": prompt,
            "stream": True
        },
        stream=True
    )

    for line in response.iter_lines():
        if line:
            try:
                data = json.loads(line.decode("utf-8"))
                if "response" in data:
                    yield data["response"]
            except:
                continue

# 🚀 MAIN API
@app.get("/ask-stream")
def ask_stream(query: str):
    results, scores = search(query, k=50)
    filtered_results = filter_results(results, scores, threshold=0.6)
    filtered_results = filtered_results[:20]

    context = build_context(filtered_results)

    def final_stream():
        # 🔥 First show detected issue (quick UX)
        yield f"""
## 🔍 Issue Analysis Started

📌 Query: {query}

🤖 Found {len(filtered_results)} relevant incidents (from {len(results)} total matches)
"""

        # 🔥 Then stream reasoning output
        for chunk in stream_reasoning(query, context):
            yield chunk

    return StreamingResponse(final_stream(), media_type="text/plain")


@app.get("/")
def home():
    return {"message": "SREGPT Reasoning Mode 🚀"}
