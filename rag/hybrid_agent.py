"""
Hybrid Agent — EDAN 2025
Routes between SQL and RAG paths with full observability tracing
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from dotenv import load_dotenv
from rag.router import route
from rag.retriever import retrieve, format_context
from rag.disambiguator import is_ambiguous
from agent.sql_agent import process_question as sql_process
from observability.tracer import RequestTracer

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def rag_answer(question: str, tracer: RequestTracer = None) -> dict:
    chunks = retrieve(question, top_k=8)

    if tracer:
        top_score = chunks[0]["score"] if chunks else 0.0
        tracer.set_rag(len(chunks), top_score)

    if not chunks:
        return {
            "intent": "rag", "answer": "Cette information n'est pas disponible dans le dataset électoral de la CEI.",
            "sources": [], "chart_type": "none", "df": None, "sql": None, "error": None,
        }

    context = format_context(chunks)
    prompt  = f"""Tu es un assistant expert en elections ivoiriennes.
Tu reponds UNIQUEMENT a partir des donnees officielles de la CEI.

Contexte:
{context}

Question: "{question}"

Regles:
- Reponds uniquement a partir du contexte fourni
- Si le contexte ne contient pas la reponse, dis clairement que l'information n'est pas disponible
- Utilise les vrais noms complets
- Reponse naturelle en francais, 2-4 phrases
- Pas de markdown, pas de liste
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )

    if tracer:
        usage = response.usage
        tracer.set_tokens(usage.prompt_tokens, usage.completion_tokens)

    answer  = response.choices[0].message.content.strip()
    sources = []
    seen    = set()
    for chunk in chunks[:3]:
        key = f"page {chunk.get('source_page','?')}, circ {chunk.get('circ_num','?')}"
        if key not in seen:
            seen.add(key)
            sources.append({
                "page":           chunk.get("source_page", "?"),
                "circ_num":       chunk.get("circ_num", "?"),
                "circonscription": chunk.get("circonscription", ""),
                "score":          round(chunk.get("score", 0), 3),
            })

    return {
        "intent": "rag", "answer": answer, "sources": sources,
        "chart_type": "none", "df": None, "sql": None, "error": None,
    }


def process_question(question: str, session_context: dict = None) -> dict:
    tracer = RequestTracer(question)

    try:
        if session_context and session_context.get("disambiguation"):
            question = session_context["refined_question"]

        # Disambiguation check
        ambiguity = is_ambiguous(question)
        tracer.set_ambiguous(ambiguity["ambiguous"])

        if ambiguity["ambiguous"]:
            tracer.set_routing("clarification")
            tracer.set_result(0, "none", ambiguity["clarification"])
            tracer.finish()
            return {
                "intent":              "clarification",
                "sql":                 None,
                "df":                  None,
                "chart_type":          "none",
                "answer":              ambiguity["clarification"],
                "needs_clarification": True,
                "matches":             ambiguity["matches"],
                "ambiguity_type":      ambiguity["type"],
                "error":               None,
            }

        # Route
        path = route(question)
        tracer.set_routing(path)

        if path == "rag":
            result = rag_answer(question, tracer)
            tracer.set_intent("rag")
            tracer.set_result(
                0,
                result.get("chart_type", "none"),
                result.get("answer", "")
            )
        else:
            result = sql_process(question)
            tracer.set_intent(result.get("intent", ""))
            tracer.set_sql(
                result.get("sql", ""),
                result.get("error") is None,
                result.get("error")
            )
            df = result.get("df")
            tracer.set_result(
                len(df) if df is not None else 0,
                result.get("chart_type", "none"),
                result.get("answer", "")
            )

        tracer.finish()
        return result

    except Exception as e:
        tracer.set_error(str(e))
        tracer.finish()
        return {
            "intent": "error", "sql": None, "df": None,
            "chart_type": "none",
            "answer": "Une erreur s'est produite. Veuillez reformuler votre question.",
            "error": str(e)
        }


if __name__ == "__main__":
    tests = [
        "Combien de sièges a gagné le RHDP ?",
        "Parle moi des résultats dans la région de Gbêkê",
        "Résultats pour Konan ?",
        "Top 5 candidats par voix",
        "Quel temps faisait-il ?",
    ]
    for q in tests:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        result = process_question(q)
        print(f"Path: {result['intent']}")
        print(f"Answer: {result['answer'][:100]}")

    from observability.tracer import get_stats
    print(f"\n{'='*60}")
    print("STATS:", get_stats())