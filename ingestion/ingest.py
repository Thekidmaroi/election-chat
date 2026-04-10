"""
Ingestion Pipeline — EDAN 2025 Election Results
PDF text -> structured DuckDB
"""

import os
import re
import requests
import pdfplumber
import pandas as pd
import duckdb
from unidecode import unidecode
from rapidfuzz import process, fuzz
from dotenv import load_dotenv

load_dotenv()

PDF_URL  = os.getenv("PDF_URL", "https://www.cei.ci/wp-content/uploads/2025/12/EDAN_2025_RESULTAT_NATIONAL_DETAILS.pdf")
PDF_PATH = "data/election_2025.pdf"
DB_PATH  = "data/election.duckdb"

KNOWN_REGIONS = [
    "AGNEBY-TIASSA", "BAFING", "BAGOUE", "BELIER", "BERE", "BOUNKANI",
    "CAVALLY", "DISTRICT AUTONOME D ABIDJAN", "DISTRICT AUTONOME DE YAMOUSSOUKRO",
    "FOLON", "GBEKE", "GBOKLE", "GOH", "GONTOUGO", "GRANDS PONTS",
    "GUEMON", "HAMBOL", "HAUT-SASSANDRA", "IFFOU", "INDENIE-DJUABLIN",
    "KABADOUGOU", "LA ME", "LOH-DJIBOUA", "MARAHOUE", "ME", "MORONOU",
    "NAWA", "N ZI", "PORO", "SAN-PEDRO", "SUD-COMOE", "TCHOLOGO",
    "TONKPI", "WORODOUGOU", "ZANZAN"
]

KNOWN_PARTIS = [
    "PDCI - FPI - ADCI", "PDCI-RDA", "INDEPENDANT", "RHDP", "FPI", "ADCI",
    "MGC", "CODE", "GP-PAIX", "UDCY", "CNJB-ADO", "GJPA-CI", "CNPCIN",
    "URCI", "EDS", "AIDE", "AIRD", "APR.CI", "FNDR", "MDR", "MERCI",
    "MLPCI", "MNRP", "P.B.J.V", "PIA/PRI/CODE", "PPSD", "PRO CI",
    "REEL.CI", "UNCI", "UFD", "UNPR", "LE BUFFLE", "CNDCI", "ICON"
]


def download_pdf():
    if os.path.exists(PDF_PATH) and os.path.getsize(PDF_PATH) > 10000:
        print("PDF already downloaded")
        return
    print("Downloading PDF...")
    os.makedirs("data", exist_ok=True)
    r = requests.get(PDF_URL, timeout=60)
    r.raise_for_status()
    with open(PDF_PATH, "wb") as f:
        f.write(r.content)
    print(f"PDF downloaded ({os.path.getsize(PDF_PATH)//1024} KB)")


def norm(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text.strip())


def norm_upper(text):
    return unidecode(norm(text)).upper()


def to_int(val):
    if val is None:
        return None
    try:
        return int(str(val).replace(" ", "").replace(",", "").replace("\xa0", ""))
    except:
        return None


def to_float(val):
    if val is None:
        return None
    try:
        return float(str(val).replace(",", ".").replace("%", "").replace("\xa0", "").strip())
    except:
        return None


def match_region(text, threshold=60):
    t = unidecode(text.upper().strip())
    if len(t) < 3:
        return None
    result = process.extractOne(t, KNOWN_REGIONS, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= threshold:
        return result[0]
    return None


def build_region_map():
    print("Building region map from spatial extraction...")
    region_map = {}
    last_matched_region = ""

    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            region_col = [w for w in words
                          if w['x0'] < 45 and w['x1'] < 80
                          and w['text'] not in ['REGI', 'ON']]
            region_col = sorted(region_col, key=lambda x: x['top'])

            current_letters = []
            for w in region_col:
                text = w['text'].strip()
                if text.isdigit() and len(text) == 3:
                    if current_letters:
                        joined = "".join(reversed(current_letters))
                        matched = match_region(joined)
                        if matched:
                            last_matched_region = matched
                        current_letters = []
                    if last_matched_region:
                        region_map[text] = last_matched_region
                else:
                    current_letters.append(text)

    # ── Fill gaps ──────────────────────────────────────────
    # Get all circ nums that should exist (001 to max)
    if region_map:
        all_nums = sorted([int(k) for k in region_map.keys()])
        max_num  = all_nums[-1]

        # Forward fill: circ without region gets region of next known circ
        for i in range(1, max_num + 1):
            circ_str = str(i).zfill(3)
            if circ_str not in region_map:
                # Find next known region
                for j in range(i + 1, max_num + 2):
                    next_str = str(j).zfill(3)
                    if next_str in region_map:
                        region_map[circ_str] = region_map[next_str]
                        break

    print(f"Region map built: {len(region_map)} circumscriptions mapped")
    return region_map


def extract_text_pages():
    pages = []
    with pdfplumber.open(PDF_PATH) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                pages.append((i, text))
    print(f"Extracted text from {len(pages)} pages")
    return pages


def is_candidate_line(line):
    up = line.upper()
    return any(up.startswith(p) for p in KNOWN_PARTIS)


def parse_candidate_line(line):
    parti = ""
    rest = line
    for p in sorted(KNOWN_PARTIS, key=len, reverse=True):
        if line.upper().startswith(p):
            parti = p
            rest = line[len(p):].strip()
            break
    if not parti:
        return None
    m = re.match(
        r"^(.+?)\s+([\d][\d\s]{0,8})\s+([\d]+[,\.][\d]+)\s*%?\s*(ELU\(E\))?$",
        rest
    )
    if not m:
        return None
    voix = to_int(m.group(2))
    pct  = to_float(m.group(3))
    elu  = bool(m.group(4))
    if not voix or voix <= 0:
        return None
    return {
        "parti":       parti,
        "candidat":    norm_upper(m.group(1).strip()),
        "voix":        voix,
        "pourcentage": pct,
        "elu":         elu,
    }


def parse_circ_line(line):
    # Format 1: with name
    m = re.match(
        r"^(\d{3})\s+(.+?)\s+(\d{1,4})\s+([\d ]{4,12})\s+([\d ]{3,8})\s+([\d,\.]+)\s*%\s+(\d{1,6})\s+([\d ]{3,10})\s+(\d+)\s+([\d,\.]+)\s*%?",
        line
    )
    if m:
        return {
            "circ_num":           m.group(1).strip(),
            "circ_name":          norm_upper(m.group(2)),
            "nb_bv":              to_int(m.group(3)),
            "inscrits":           to_int(m.group(4)),
            "votants":            to_int(m.group(5)),
            "taux_participation": to_float(m.group(6)),
            "blancs_nuls":        to_int(m.group(7)),
            "exprimes":           to_int(m.group(8)),
        }

    # Format 2: without name
    m2 = re.match(
        r"^(\d{3})\s+(\d{1,4})\s+([\d ]{4,12})\s+([\d ]{3,8})\s+([\d,\.]+)\s*%\s+(\d{1,6})\s+([\d ]{3,10})\s+(\d+)\s+([\d,\.]+)\s*%?",
        line
    )
    if m2:
        return {
            "circ_num":           m2.group(1).strip(),
            "circ_name":          None,
            "nb_bv":              to_int(m2.group(2)),
            "inscrits":           to_int(m2.group(3)),
            "votants":            to_int(m2.group(4)),
            "taux_participation": to_float(m2.group(5)),
            "blancs_nuls":        to_int(m2.group(6)),
            "exprimes":           to_int(m2.group(7)),
        }

    return None


SKIP = [
    "ELECTION DES DEPUTES", "SCRUTIN DU", "RESULTATS DES SCRUTINS",
    "GROUPEMENTS / PARTIS", "CANDIDATS / LISTES", "NB BV", "NOMBRE %",
    "BULL.", "TAUX DE", "REGI ON", "CIRCONSCRIPTION NB",
    "ON PART.", "TOTAL 25"
]


def is_skip(line):
    up = line.upper()
    if re.match(r"^Page \d+ de \d+", line, re.IGNORECASE):
        return True
    return any(kw in up for kw in SKIP)


def parse_pages(pages, region_map):
    records = []
    current_circ_num  = ""
    current_circ_name = ""
    current_inscrits  = None
    current_votants   = None
    current_taux      = None
    current_blancs    = None
    current_exprimes  = None

    for page_num, text in pages:
        for raw_line in text.split("\n"):
            line = norm(raw_line)
            if not line or len(line) < 4:
                continue
            if is_skip(line):
                continue

            circ = parse_circ_line(line)
            if circ:
                current_circ_num = circ["circ_num"]
                if circ["circ_name"]:
                    current_circ_name = circ["circ_name"]
                current_inscrits  = circ["inscrits"]
                current_votants   = circ["votants"]
                current_taux      = circ["taux_participation"]
                current_blancs    = circ["blancs_nuls"]
                current_exprimes  = circ["exprimes"]
                continue

            if is_candidate_line(line):
                cand = parse_candidate_line(line)
                if cand:
                    region = region_map.get(current_circ_num, "")
                    records.append({
                        "source_page":        page_num,
                        "region":             region,
                        "circ_num":           current_circ_num,
                        "circonscription":    current_circ_name,
                        "inscrits":           current_inscrits,
                        "votants":            current_votants,
                        "taux_participation": current_taux,
                        "blancs_nuls":        current_blancs,
                        "exprimes":           current_exprimes,
                        "parti":              cand["parti"],
                        "candidat":           cand["candidat"],
                        "voix":               cand["voix"],
                        "pourcentage":        cand["pourcentage"],
                        "elu":                cand["elu"],
                    })

    print(f"Parsed {len(records)} candidate records")
    return records


def load_to_duckdb(df):
    if df.empty:
        print("ERROR: DataFrame is empty")
        return
    print("Loading into DuckDB...")
    os.makedirs("data", exist_ok=True)
    con = duckdb.connect(DB_PATH)
    con.execute("DROP TABLE IF EXISTS results")
    con.execute("""
        CREATE TABLE results (
            id INTEGER, source_page INTEGER,
            region VARCHAR, circ_num VARCHAR, circonscription VARCHAR,
            inscrits INTEGER, votants INTEGER, taux_participation DOUBLE,
            blancs_nuls INTEGER, exprimes INTEGER,
            parti VARCHAR, candidat VARCHAR,
            voix INTEGER, pourcentage DOUBLE, elu BOOLEAN
        )
    """)
    df = df.reset_index(drop=True)
    df.insert(0, "id", df.index + 1)
    con.execute("INSERT INTO results SELECT * FROM df")

    con.execute("DROP VIEW IF EXISTS vw_winners")
    con.execute("""
        CREATE VIEW vw_winners AS
        SELECT region, circ_num, circonscription,
               parti, candidat, voix, pourcentage, source_page
        FROM results WHERE elu = TRUE
        ORDER BY region, circ_num
    """)
    con.execute("DROP VIEW IF EXISTS vw_turnout")
    con.execute("""
        CREATE VIEW vw_turnout AS
        SELECT region, circ_num, circonscription,
               MAX(inscrits) AS inscrits,
               MAX(votants)  AS votants,
               MAX(exprimes) AS exprimes,
               MAX(blancs_nuls) AS blancs_nuls,
               MAX(taux_participation) AS taux_participation
        FROM results
        GROUP BY region, circ_num, circonscription
        ORDER BY region, circ_num
    """)
    con.execute("DROP VIEW IF EXISTS vw_results_clean")
    con.execute("""
        CREATE VIEW vw_results_clean AS
        SELECT id, source_page, region, circ_num, circonscription,
               parti, candidat, voix, pourcentage, elu
        FROM results
        WHERE candidat IS NOT NULL AND voix IS NOT NULL
        ORDER BY circ_num, voix DESC
    """)

    count   = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    winners = con.execute("SELECT COUNT(*) FROM vw_winners").fetchone()[0]
    regions = con.execute("SELECT COUNT(DISTINCT region) FROM results WHERE region != ''").fetchone()[0]
    circs   = con.execute("SELECT COUNT(DISTINCT circ_num) FROM results WHERE circ_num != ''").fetchone()[0]
    partis  = con.execute("SELECT COUNT(DISTINCT parti) FROM results").fetchone()[0]
    print(f"DuckDB loaded: {count} rows | {winners} elus | {regions} regions | {circs} circs | {partis} partis")
    print("\nRegions detected:")
    print(con.execute("SELECT region, COUNT(DISTINCT circ_num) as circs FROM results WHERE region != '' GROUP BY region ORDER BY region").df().to_string())
    con.close()


def run():
    download_pdf()
    region_map = build_region_map()
    pages = extract_text_pages()
    records = parse_pages(pages, region_map)
    if not records:
        print("ERROR: No records parsed!")
        return
    df = pd.DataFrame(records)
    df.to_csv("data/election_2025.csv", index=False)
    print("CSV saved")
    load_to_duckdb(df)
    print("\nIngestion complete!")


if __name__ == "__main__":
    run()