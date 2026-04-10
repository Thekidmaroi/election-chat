"""
RAG Retriever — EDAN 2025
Query -> Embeddings -> FAISS search -> Top-k chunks
"""

import os
import pickle
import numpy as np
import faiss
from openai import OpenAI
from unidecode import unidecode
from dotenv import load_dotenv

load_dotenv()

client    = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
IDX_PATH  = "data/rag_index.faiss"
META_PATH = "data/rag_metadata.pkl"
EMBED_MODEL = "text-embedding-3-small"

_index    = None
_metadata = None


def load_index():
    global _index, _metadata
    if _index is None:
        _index = faiss.read_index(IDX_PATH)
        with open(META_PATH, "rb") as f:
            data = pickle.load(f)
        _metadata = data["metadata"]
    return _index, _metadata


def get_query_embedding(query: str) -> np.ndarray:
    query_norm = unidecode(query)
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=[query_norm]
    )
    vec = np.array([response.data[0].embedding], dtype=np.float32)
    faiss.normalize_L2(vec)
    return vec


def retrieve(query: str, top_k: int = 5) -> list:
    """
    Retrieve top-k relevant chunks for a query.
    Returns list of dicts with text, score, metadata.
    """
    index, metadata = load_index()
    vec = get_query_embedding(query)
    scores, indices = index.search(vec, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        meta = metadata[idx].copy()
        meta["score"] = float(score)
        results.append(meta)

    return results


def format_context(chunks: list) -> str:
    """Format retrieved chunks as context for LLM."""
    lines = []
    for i, chunk in enumerate(chunks, 1):
        source = f"[Source: page {chunk.get('source_page', '?')}, circ {chunk.get('circ_num', '?')}]"
        lines.append(f"{i}. {chunk['text']} {source}")
    return "\n".join(lines)


if __name__ == "__main__":
    tests = [
        "Qui a gagné à Tiapoum ?",
        "Taux de participation à Abidjan",
        "Candidats RHDP élus",
    ]
    for q in tests:
        print(f"\nQ: {q}")
        results = retrieve(q, top_k=3)
        for r in results:
            print(f"  score={r['score']:.3f} | {r['text'][:100]}")