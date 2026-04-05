import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import pickle

model = SentenceTransformer('all-MiniLM-L6-v2')

def build_index():
    # ✅ FIXED HERE
    df = pd.read_csv("data/issues.csv")

    # 🔥 FORCE CORRECT MAPPING
    df = df.rename(columns={
        "Issue Subject": "issue",
        "Issue Solution": "solution",
        "Ticket ID": "ticket"
    })

    # Safety fallback
    df["issue"] = df["issue"].fillna("")
    df["solution"] = df["solution"].fillna("")
    df["ticket"] = df["ticket"].fillna("N/A")

    # Ensure correct structure
    records = df[["issue", "solution", "ticket"]].to_dict(orient="records")

    texts = [r["issue"] + " " + r["solution"] for r in records]

    embeddings = model.encode(texts)

    index = faiss.IndexFlatL2(len(embeddings[0]))
    index.add(np.array(embeddings))

    # Save
    faiss.write_index(index, "data/index.faiss")
    pickle.dump(records, open("data/data.pkl", "wb"))

    print("✅ Index rebuilt with correct schema")

if __name__ == "__main__":
    build_index()