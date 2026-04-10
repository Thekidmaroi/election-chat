"""
Disambiguator — EDAN 2025
Detects ambiguous entities and generates clarification questions
"""

import re
import duckdb
from unidecode import unidecode

DB_PATH = "data/election.duckdb"


def normalize(text: str) -> str:
    return unidecode(text.upper().strip())


def find_matching_circonscriptions(query: str) -> list:
    """Find all circonscriptions matching a query string using fuzzy search."""
    q = normalize(query)
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        # Try exact ILIKE first
        df = con.execute("""
            SELECT DISTINCT circ_num, circonscription, region
            FROM results
            WHERE circonscription ILIKE ?
               OR circonscription ILIKE ?
               OR region ILIKE ?
            ORDER BY circ_num
            LIMIT 10
        """, [f"%{q}%", f"%{query.upper()}%", f"%{q}%"]).df()

        # If no results, try word by word
        if df.empty:
            words = [w for w in q.split() if len(w) > 3]
            for word in words:
                df = con.execute("""
                    SELECT DISTINCT circ_num, circonscription, region
                    FROM results
                    WHERE circonscription ILIKE ?
                    ORDER BY circ_num
                    LIMIT 10
                """, [f"%{word}%"]).df()
                if not df.empty:
                    break

        con.close()
        return df.to_dict("records")
    except:
        return []
    """Find all circonscriptions matching a query string."""
    q = normalize(query)
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        df = con.execute("""
            SELECT DISTINCT circ_num, circonscription, region
            FROM results
            WHERE circonscription ILIKE ?
               OR circonscription ILIKE ?
            ORDER BY circ_num
            LIMIT 10
        """, [f"%{q}%", f"%{query}%"]).df()
        con.close()
        return df.to_dict("records")
    except:
        return []


def find_matching_candidates(query: str) -> list:
    """Find all candidates matching a query string."""
    q = normalize(query)
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        df = con.execute("""
            SELECT DISTINCT candidat, parti, circ_num, circonscription, region, voix, elu
            FROM results
            WHERE candidat ILIKE ?
            ORDER BY voix DESC
            LIMIT 10
        """, [f"%{q}%"]).df()
        con.close()
        return df.to_dict("records")
    except:
        return []


def find_matching_regions(query: str) -> list:
    """Find all regions matching a query string."""
    q = normalize(query)
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        df = con.execute("""
            SELECT DISTINCT region, COUNT(DISTINCT circ_num) as nb_circs
            FROM results
            WHERE region ILIKE ?
            GROUP BY region
            ORDER BY region
            LIMIT 10
        """, [f"%{q}%"]).df()
        con.close()
        return df.to_dict("records")
    except:
        return []


def is_ambiguous(question: str) -> dict:
    """
    Analyze a question for ambiguity.
    """
    q_norm = normalize(question)

    stop_words = {
        "QUI", "A", "GAGNE", "DANS", "LA", "LE", "LES", "DE", "DU", "AU",
        "EN", "POUR", "PAR", "SUR", "ET", "OU", "EST", "SONT", "AVEC",
        "REGION", "CIRCONSCRIPTION", "COMMUNE", "VILLE", "SOUS", "PREFECTURE",
        "COMBIEN", "QUEL", "QUELLE", "QUELS", "QUELLES", "MONTRE", "AFFICHE",
        "TOP", "LISTE", "TOUS", "TOUTES", "TAUX", "PARTICIPATION", "SIEGES",
        "CANDIDATS", "ELUS", "PARTI", "PARTIS", "VOIX", "SCORE", "RESULTAT",
        "RESULTATS", "SITUATION", "ELECTORALE", "PARLE", "MOI", "DES"
    }

    words = [w for w in q_norm.split() if w not in stop_words and len(w) > 3]

    for word in words:
        # Check circonscriptions
        circs = find_matching_circonscriptions(word)
        if len(circs) > 1:
            clarification = f"Plusieurs circonscriptions correspondent à **{word}** :\n"
            for c in circs[:5]:
                clarification += f"• **{c['circ_num']}** — {c['circonscription']} ({c['region']})\n"
            clarification += "\nPouvez-vous préciser la circonscription ?"
            return {
                "ambiguous": True,
                "type": "circonscription",
                "matches": circs,
                "query_word": word,
                "clarification": clarification
            }

        # Check regions
        regions = find_matching_regions(word)
        if len(regions) > 1:
            clarification = f"Plusieurs régions correspondent à **{word}** :\n"
            for r in regions[:5]:
                clarification += f"• **{r['region']}** ({r['nb_circs']} circonscriptions)\n"
            clarification += "\nPouvez-vous préciser la région ?"
            return {
                "ambiguous": True,
                "type": "region",
                "matches": regions,
                "query_word": word,
                "clarification": clarification
            }

        # Check candidates
        candidates = find_matching_candidates(word)
        if len(candidates) > 1:
            clarification = f"Plusieurs candidats correspondent à **{word}** :\n"
            for c in candidates[:5]:
                status = "✅ Élu" if c['elu'] else "❌ Non élu"
                clarification += f"• **{c['candidat']}** ({c['parti']}) — {c['circonscription']} — {status}\n"
            clarification += "\nPouvez-vous préciser ?"
            return {
                "ambiguous": True,
                "type": "candidat",
                "matches": candidates,
                "query_word": word,
                "clarification": clarification
            }

    return {
        "ambiguous": False,
        "type": "none",
        "matches": [],
        "clarification": None
    }
    """
    Analyze a question for ambiguity.
    Returns: {
        "ambiguous": bool,
        "type": "circonscription|candidat|region|none",
        "matches": list,
        "clarification": str
    }
    """
    q_norm = normalize(question)

    # Extract potential entity names from question
    # Remove common words
    stop_words = {
        "QUI", "A", "GAGNE", "DANS", "LA", "LE", "LES", "DE", "DU", "AU",
        "EN", "POUR", "PAR", "SUR", "ET", "OU", "EST", "SONT", "AVEC",
        "REGION", "CIRCONSCRIPTION", "COMMUNE", "VILLE", "SOUS", "PREFECTURE",
        "COMBIEN", "QUEL", "QUELLE", "QUELS", "QUELLES", "MONTRE", "AFFICHE",
        "TOP", "LISTE", "TOUS", "TOUTES", "TAUX", "PARTICIPATION", "SIEGES",
        "CANDIDATS", "ELUS", "PARTI", "PARTIS", "VOIX", "SCORE"
    }

    words = [w for w in q_norm.split() if w not in stop_words and len(w) > 3]

    for word in words:
        # Check circonscriptions
        circs = find_matching_circonscriptions(word)
        if len(circs) > 1:
            clarification = f"Plusieurs circonscriptions correspondent à '{word}' :\n"
            for c in circs[:5]:
                clarification += f"• {c['circ_num']} — {c['circonscription']} ({c['region']})\n"
            clarification += "\nPouvez-vous préciser la circonscription ?"
            return {
                "ambiguous": True,
                "type": "circonscription",
                "matches": circs,
                "query_word": word,
                "clarification": clarification
            }

        # Check candidates
        candidates = find_matching_candidates(word)
        if len(candidates) > 1:
            clarification = f"Plusieurs candidats correspondent à '{word}' :\n"
            for c in candidates[:5]:
                status = "✅ Élu" if c['elu'] else "❌ Non élu"
                clarification += f"• {c['candidat']} ({c['parti']}) — {c['circonscription']} — {status}\n"
            clarification += "\nPouvez-vous préciser ?"
            return {
                "ambiguous": True,
                "type": "candidat",
                "matches": candidates,
                "query_word": word,
                "clarification": clarification
            }

    return {
        "ambiguous": False,
        "type": "none",
        "matches": [],
        "clarification": None
    }


if __name__ == "__main__":
    tests = [
        "Qui a gagné à Tiapoum ?",
        "Qui a gagné à Abidjan ?",
        "Résultats pour Konan ?",
        "Combien de sièges a gagné le RHDP ?",
        "Qui a gagné dans la circonscription 001 ?",
    ]
    for q in tests:
        print(f"\nQ: {q}")
        result = is_ambiguous(q)
        print(f"  Ambiguous: {result['ambiguous']}")
        if result['ambiguous']:
            print(f"  Type: {result['type']}")
            print(f"  Clarification: {result['clarification']}")