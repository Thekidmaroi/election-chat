"""
Router — EDAN 2025
Decides SQL vs RAG path based on user intent
"""

import re
from unidecode import unidecode

# Keywords indicating analytical/aggregation intent → SQL
SQL_KEYWORDS = [
    "combien", "nombre", "count", "total", "somme", "moyenne",
    "top", "classement", "ranking", "liste", "palmares",
    "plus haut", "plus bas", "maximum", "minimum",
    "taux", "participation", "pourcentage",
    "gagne", "remporte", "elu", "elus", "siege", "sieges",
    "histogramme", "graphique", "camembert", "visualise",
    "montre", "affiche", "barre", "pie", "chart",
    "par region", "par circonscription", "par parti",
]

# Keywords indicating fuzzy/narrative intent → RAG
RAG_KEYWORDS = [
    "qui est", "parle moi", "explique", "raconte",
    "contexte", "detail", "narrative", "histoire",
    "comment", "pourquoi", "quelle est la situation",
]

# Patterns indicating typos or fuzzy entity lookup → RAG
FUZZY_PATTERNS = [
    r"\b\w{4,}\b",  # any word (will check against known entities)
]


def classify_intent(question: str) -> str:
    """
    Returns 'sql' or 'rag' based on question analysis.
    """
    q = unidecode(question.lower().strip())

    # Check explicit RAG keywords
    for kw in RAG_KEYWORDS:
        if kw in q:
            return "rag"

    # Check explicit SQL keywords
    for kw in SQL_KEYWORDS:
        if kw in q:
            return "sql"

    # Default: questions with numbers or circonscription codes → SQL
    if re.search(r"\b\d{3}\b", q):
        return "sql"

    # Short factual questions → SQL
    if len(q.split()) <= 6:
        return "sql"

    # Longer narrative questions → RAG
    if len(q.split()) > 10:
        return "rag"

    return "sql"


def route(question: str) -> str:
    intent = classify_intent(question)
    return intent


if __name__ == "__main__":
    tests = [
        "Combien de sièges a gagné le RHDP ?",
        "Top 10 candidats par nombre de voix",
        "Qui a gagné dans la circonscription 001 ?",
        "Taux de participation par région",
        "Parle moi des résultats dans la région de Gbêkê",
        "Qui est Dimba N'Gou Pierre ?",
        "Montre un histogramme des élus par parti",
        "Quelle est la situation électorale à Abidjan ?",
        "Quel temps faisait-il ?",
        "RHDP combien ?",
    ]
    for q in tests:
        intent = route(q)
        print(f"[{intent.upper():3}] {q}")