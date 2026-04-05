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

# 🔥 FIX: Normalize data keys (IMPORTANT)
def normalize_record(record):
    return {
        "issue": record.get("issue") or record.get("Issue Subject") or "",
        "solution": record.get("solution") or record.get("Issue Solution") or "",
        "ticket": record.get("ticket") or record.get("Ticket ID") or "N/A"
    }

# 🔍 SEARCH
def search(query, k=5):
    q_emb = model.encode([query])
    D, I = index.search(np.array(q_emb), k)

    raw_results = [data[i] for i in I[0]]
    results = [normalize_record(r) for r in raw_results]

    scores = D[0]
    return results, scores

# 🧠 RESPONSE BUILDER
def build_response(query, results, scores):
    best_score = scores[0]

    confidence = round(100 * (1 / (1 + best_score)), 2)

    best = results[0]

    # Related tickets (clean + no duplicates)
    related = []
    for r in results[1:5]:
        t = r.get("ticket", "N/A")
        if t != "N/A" and t not in related:
            related.append(t)

    if not related:
        related = ["N/A"]

    if confidence > 60:
        return f"""
## 🔍 Issue Identified (Confidence: {confidence}%)

📌 **Issue:** {best['issue']}  
🛠 **Fix:** {best['solution']}  
🎫 **Ticket:** {best['ticket']}

## 📎 Related Tickets
{chr(10).join([f"- {t}" for t in related])}

## 🤖 AI Insights
"""
    else:
        related_list = "\n".join([f"- {r['ticket']}" for r in results[:3]])

        return f"""
## 🤖 AI Generated Solution (Low Confidence: {confidence}%)

Possible issue related to: **{query}**

### Steps:
1. Check logs
2. Validate configs
3. Restart services

## 📎 Closest Past Tickets
{related_list}

## 🤖 Suggested Debugging
"""

# 🤖 STREAM LLM
def stream_llm(query, context):
    prompt = f"""
You are a Senior SRE.

User issue:
{query}

Internal knowledge:
{context}

Give response in clean markdown:
- Root cause
- Step-by-step fix
- Commands (use ```bash)
- Prevention tips
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
                data = json.loads(line.decode("utf-8"))
                if "response" in data:
                    yield data["response"]
            except:
                continue

# 🚀 MAIN API
@app.get("/ask-stream")
def ask_stream(query: str):
    results, scores = search(query)

    base_response = build_response(query, results, scores)

    def final_stream():
        yield base_response

        context = "\n".join([
            f"Issue: {r['issue']} | Solution: {r['solution']}"
            for r in results
        ])

        for chunk in stream_llm(query, context):
            yield chunk

    return StreamingResponse(final_stream(), media_type="text/plain")


@app.get("/")
def home():
    return {"message": "SREGPT running 🚀"}