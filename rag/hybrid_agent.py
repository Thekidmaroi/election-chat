"""
Hybrid Agent — EDAN 2025
Routes between SQL and RAG paths
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from dotenv import load_dotenv
from rag.router import route
from rag.retriever import retrieve, format_context
from agent.sql_agent import process_question as sql_process

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def rag_answer(question: str) -> dict:
    """RAG path: retrieve relevant chunks + LLM answer."""
    chunks = retrieve(question, top_k=8)

    if not chunks:
        return {
            "intent":     "rag",
            "answer":     "Cette information n'est pas disponible dans le dataset électoral de la CEI.",
            "sources":    [],
            "chart_type": "none",
            "df":         None,
            "sql":        None,
            "error":      None,
        }

    context = format_context(chunks)

    prompt = f"""Tu es un assistant expert en elections ivoiriennes.
Tu reponds UNIQUEMENT a partir des donnees officielles de la CEI (Commission Electorale Independante).

Contexte extrait du dataset officiel:
{context}

Question: "{question}"

Regles:
- Reponds uniquement a partir du contexte fourni
- Si le contexte ne contient pas la reponse, dis clairement que l'information n'est pas disponible
- Utilise les vrais noms complets — jamais les IDs
- Reponse naturelle en francais, 2-4 phrases
- Pas de markdown, pas de liste
- Cite la source si pertinent (ex: "selon les donnees de la circonscription X")
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )

    answer = response.choices[0].message.content.strip()

    # Extract unique sources
    sources = []
    seen = set()
    for chunk in chunks[:3]:
        key = f"page {chunk.get('source_page', '?')}, circ {chunk.get('circ_num', '?')}"
        if key not in seen:
            seen.add(key)
            sources.append({
                "page":           chunk.get("source_page", "?"),
                "circ_num":       chunk.get("circ_num", "?"),
                "circonscription": chunk.get("circonscription", ""),
                "score":          round(chunk.get("score", 0), 3),
            })

    return {
        "intent":     "rag",
        "answer":     answer,
        "sources":    sources,
        "chart_type": "none",
        "df":         None,
        "sql":        None,
        "error":      None,
    }


def process_question(question: str) -> dict:
    """Main hybrid agent: route to SQL or RAG."""
    path = route(question)

    if path == "rag":
        return rag_answer(question)
    else:
        return sql_process(question)


if __name__ == "__main__":
    tests = [
        "Combien de sièges a gagné le RHDP ?",
        "Parle moi des résultats dans la région de Gbêkê",
        "Qui est Dimba N'Gou Pierre ?",
        "Quelle est la situation électorale à Abidjan ?",
        "Top 5 candidats par voix",
    ]
    for q in tests:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        result = process_question(q)
        print(f"Path: {result['intent']}")
        print(f"Answer: {result['answer']}")
        if result.get("sources"):
            print(f"Sources: {result['sources']}")