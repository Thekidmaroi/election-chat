"""
SQL Agent — EDAN 2025
"""

import os
import re
import json
import duckdb
import pandas as pd
from unidecode import unidecode
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_PATH = "data/election.duckdb"

SCHEMA = """
TABLE: results
  id INTEGER, source_page INTEGER,
  region VARCHAR, circ_num VARCHAR, circonscription VARCHAR,
  inscrits INTEGER, votants INTEGER, taux_participation DOUBLE,
  blancs_nuls INTEGER, exprimes INTEGER,
  parti VARCHAR, candidat VARCHAR, voix INTEGER, pourcentage DOUBLE, elu BOOLEAN

VIEW: vw_winners
  region, circ_num, circonscription, parti, candidat, voix, pourcentage, source_page

VIEW: vw_turnout
  region, circ_num, circonscription, inscrits, votants, exprimes, blancs_nuls, taux_participation

VIEW: vw_results_clean
  id, source_page, region, circ_num, circonscription, parti, candidat, voix, pourcentage, elu
"""

SYSTEM_PROMPT = f"""Tu es un agent SQL expert en analyse de donnees electorales ivoiriennes.
Tu analyses les resultats de l'Election des Deputes a l'Assemblee Nationale du 27 Decembre 2025 en Cote d'Ivoire.

SCHEMA:
{SCHEMA}

EXEMPLES DE REQUETES CORRECTES:
- "RHDP combien" ou "combien RHDP" → SELECT COUNT(*) as sieges_gagnes FROM vw_winners WHERE parti ILIKE '%RHDP%'
- "combien de sieges PDCI" → SELECT COUNT(*) as sieges_gagnes FROM vw_winners WHERE parti ILIKE '%PDCI%'
- "combien independants elus" → SELECT COUNT(*) as sieges_gagnes FROM vw_winners WHERE parti ILIKE '%INDEPENDANT%'
- "top candidats" → SELECT candidat, SUM(voix) as total_voix FROM results WHERE LENGTH(candidat) < 35 AND candidat NOT ILIKE '%ENSEMBLE%' AND candidat NOT ILIKE '%POUR%' AND candidat NOT ILIKE '%IVOIRE%' GROUP BY candidat ORDER BY total_voix DESC LIMIT 10
- "qui a gagne dans 001" → SELECT candidat, parti, voix, pourcentage FROM vw_winners WHERE circ_num = '001'
- "qui a gagne dans 002" → SELECT candidat, parti, voix, pourcentage FROM vw_winners WHERE circ_num = '002'
- "quel candidat elu dans 015" → SELECT candidat, parti, voix, pourcentage FROM vw_winners WHERE circ_num = '015'
- "participation la plus basse" → SELECT circonscription, taux_participation FROM vw_turnout ORDER BY taux_participation ASC LIMIT 5
- "circonscription avec le plus de voix" → SELECT circonscription, circ_num, SUM(voix) as total_voix FROM results GROUP BY circonscription, circ_num ORDER BY total_voix DESC LIMIT 5
- "region Gbeke" → WHERE region ILIKE '%GBEKE%'
- "region Haut-Sassandra" → WHERE region ILIKE '%HAUT%SASSANDRA%'

REGLES STRICTES:
1. SELECT uniquement — jamais INSERT, UPDATE, DELETE, DROP, ALTER
2. LIMIT 50 maximum sauf aggregation globale
3. Utilise UNIQUEMENT les tables/vues du schema
4. Pour les noms avec accents ou variantes: utilise ILIKE avec wildcards. Les noms dans la DB sont sans accents en majuscules. Ex: Gbêkê → ILIKE '%GBEKE%'
5. vw_winners ne contient PAS la colonne elu
6. Pour le top candidats: WHERE LENGTH(candidat) < 35 AND candidat NOT ILIKE '%ENSEMBLE%' AND candidat NOT ILIKE '%POUR%' AND candidat NOT ILIKE '%IVOIRE%' AND candidat NOT ILIKE '%COTE%' AND candidat NOT ILIKE '%UNE%' AND candidat NOT ILIKE '%TOUS%'
7. Si hors dataset: intent = out_of_scope
8. JSON valide uniquement, sans markdown, sans backticks
9. Pour toute question sur un parti seul (RHDP, PDCI, FPI...) → compter les sieges dans vw_winners
10. Toujours inclure le nom complet de la circonscription dans les SELECT

REGLE chart_type:
- "none" par defaut
- "bar" si: graphique, barre, visualise, montre, affiche
- "pie" si: camembert, pie, repartition en cercle
- "histogram" si: histogramme

Format JSON:
{{"intent": "aggregation|ranking|chart|factual|out_of_scope", "sql": "SELECT ...", "chart_type": "bar|pie|histogram|none", "explanation": "..."}}

Si out_of_scope:
{{"intent": "out_of_scope", "sql": null, "chart_type": "none", "explanation": "..."}}
"""

BLOCKED_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "exec"]
CHART_KEYWORDS   = ["graphique", "graph", "barre", "visualise", "montre", "affiche",
                    "histogramme", "histogram", "camembert", "pie", "chart", "visualisation"]


def wants_chart(question: str) -> bool:
    return any(kw in question.lower() for kw in CHART_KEYWORDS)


def normalize_question(question: str) -> str:
    return unidecode(question)


def validate_sql(sql: str):
    if not sql:
        return False, "SQL vide"
    sql_lower = sql.lower().strip()
    if not sql_lower.startswith("select"):
        return False, "SELECT uniquement"
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_lower):
            return False, f"Mot-cle interdit: {kw}"
    if "limit" not in sql_lower:
        sql = sql.rstrip(";") + " LIMIT 50"
    return True, sql


def execute_sql(sql: str):
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        df  = con.execute(sql).df()
        con.close()
        return df, None
    except Exception as e:
        return None, str(e)


def ask_llm(question: str) -> dict:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": question}
            ],
            temperature=0.1,
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json\n?", "", raw)
        raw = re.sub(r"```\n?", "", raw)
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(m.group() if m else raw)
    except Exception as e:
        return {"intent": "error", "sql": None, "chart_type": "none", "explanation": str(e)}


def formulate_answer(question: str, df: pd.DataFrame) -> str:
    try:
        data_str = df.head(20).to_string(index=False)
        prompt = f"""Tu es un assistant electoral ivoirien.
Question: "{question}"

Donnees CEI:
{data_str}

Reponds en francais naturel et fluide.
- Reponds directement, sans introduction ni commentaire inutile
- Utilise les vrais noms complets — jamais les IDs ou codes numeriques
- Chiffres precis issus des donnees
- 2-3 phrases maximum
- Pas de markdown, pas de liste, pas de tableau
- Si la donnee parle de sieges/elus: dis "sieges" pas "voix"
- Seulement un commentaire pertinent si vraiment utile
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=250,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return f"{len(df)} résultat(s) trouvé(s)."


def process_question(question: str) -> dict:
    q_lower = question.lower()
    for kw in BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", q_lower):
            return {
                "intent": "blocked", "sql": None, "df": None,
                "chart_type": "none",
                "answer": "Cette opération n'est pas autorisée.",
                "error": "blocked"
            }

    question_normalized = normalize_question(question)
    llm_response = ask_llm(question_normalized)
    intent      = llm_response.get("intent", "error")
    sql         = llm_response.get("sql")
    chart_type  = llm_response.get("chart_type", "none")

    if not wants_chart(question):
        chart_type = "none"

    if intent == "out_of_scope" or (intent == "error" and sql is None):
        return {
            "intent": intent, "sql": None, "df": None,
            "chart_type": "none",
            "answer": "Cette information n'est pas disponible dans le dataset électoral de la CEI.",
            "error": None
        }

    valid, result = validate_sql(sql)
    if not valid:
        return {
            "intent": "blocked", "sql": sql, "df": None,
            "chart_type": "none",
            "answer": "Requête non autorisée.",
            "error": result
        }
    sql = result

    df, error = execute_sql(sql)
    if error:
        return {
            "intent": intent, "sql": sql, "df": None,
            "chart_type": "none",
            "answer": "Une erreur s'est produite. Veuillez reformuler votre question.",
            "error": error
        }

    answer = "Aucun résultat trouvé dans le dataset électoral." if (df is None or df.empty) else formulate_answer(question, df)

    return {
        "intent": intent, "sql": sql, "df": df,
        "chart_type": chart_type, "answer": answer, "error": None
    }