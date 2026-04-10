"""
RAG Indexer — EDAN 2025
Converts DB rows to text chunks + OpenAI embeddings + FAISS index
"""

import os
import json
import pickle
import numpy as np
import duckdb
import faiss
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client   = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_PATH  = "data/election.duckdb"
IDX_PATH = "data/rag_index.faiss"
META_PATH= "data/rag_metadata.pkl"

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE  = 100


def row_to_text(row: dict) -> str:
    """Convert a DB row to a natural language chunk."""
    parts = []
    if row.get("region"):
        parts.append(f"Région: {row['region']}")
    if row.get("circonscription"):
        parts.append(f"Circonscription: {row['circonscription']} (n°{row['circ_num']})")
    if row.get("parti"):
        parts.append(f"Parti: {row['parti']}")
    if row.get("candidat"):
        parts.append(f"Candidat: {row['candidat']}")
    if row.get("voix"):
        parts.append(f"Voix: {row['voix']}")
    if row.get("pourcentage"):
        parts.append(f"Pourcentage: {row['pourcentage']}%")
    if row.get("elu"):
        parts.append("Statut: ELU(E)")
    if row.get("inscrits"):
        parts.append(f"Inscrits: {row['inscrits']}")
    if row.get("votants"):
        parts.append(f"Votants: {row['votants']}")
    if row.get("taux_participation"):
        parts.append(f"Taux participation: {row['taux_participation']}%")
    return " | ".join(parts)


def get_embeddings(texts: list) -> np.ndarray:
    """Get embeddings from OpenAI in batches."""
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        response = client.embeddings.create(
            model=EMBED_MODEL,
            input=batch
        )
        batch_embeddings = [e.embedding for e in response.data]
        all_embeddings.extend(batch_embeddings)
        print(f"  Embedded {min(i+BATCH_SIZE, len(texts))}/{len(texts)}")
    return np.array(all_embeddings, dtype=np.float32)


def build_index():
    print("Loading data from DuckDB...")
    con = duckdb.connect(DB_PATH, read_only=True)
    df  = con.execute("SELECT * FROM vw_results_clean").df()
    
    # Add turnout data
    turnout = con.execute("SELECT * FROM vw_turnout").df()
    con.close()

    print(f"Building chunks from {len(df)} candidate rows + {len(turnout)} turnout rows...")

    chunks   = []
    metadata = []

    # Candidate rows
    for _, row in df.iterrows():
        text = row_to_text(row.to_dict())
        chunks.append(text)
        metadata.append({
            "type":          "candidate",
            "source_page":   int(row.get("source_page", 0)),
            "circ_num":      str(row.get("circ_num", "")),
            "circonscription": str(row.get("circonscription", "")),
            "region":        str(row.get("region", "")),
            "candidat":      str(row.get("candidat", "")),
            "parti":         str(row.get("parti", "")),
            "voix":          int(row.get("voix", 0)) if row.get("voix") else 0,
            "elu":           bool(row.get("elu", False)),
            "text":          text,
        })

    # Turnout rows
    for _, row in turnout.iterrows():
        text = (
            f"Région: {row.get('region', '')} | "
            f"Circonscription: {row.get('circonscription', '')} (n°{row.get('circ_num', '')}) | "
            f"Inscrits: {row.get('inscrits', '')} | "
            f"Votants: {row.get('votants', '')} | "
            f"Taux participation: {row.get('taux_participation', '')}% | "
            f"Blancs/Nuls: {row.get('blancs_nuls', '')}"
        )
        chunks.append(text)
        metadata.append({
            "type":          "turnout",
            "source_page":   0,
            "circ_num":      str(row.get("circ_num", "")),
            "circonscription": str(row.get("circonscription", "")),
            "region":        str(row.get("region", "")),
            "text":          text,
        })

    print(f"Total chunks: {len(chunks)}")
    print("Generating embeddings (this may take a minute)...")

    embeddings = get_embeddings(chunks)

    print("Building FAISS index...")
    dim   = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)

    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)
    index.add(embeddings)

    print(f"Saving index to {IDX_PATH}...")
    os.makedirs("data", exist_ok=True)
    faiss.write_index(index, IDX_PATH)

    with open(META_PATH, "wb") as f:
        pickle.dump({"chunks": chunks, "metadata": metadata}, f)

    print(f"✅ Index built: {index.ntotal} vectors, dim={dim}")
    return index, metadata


if __name__ == "__main__":
    build_index()