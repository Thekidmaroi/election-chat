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
from dotenv import load_dotenv

load_dotenv()

PDF_URL  = os.getenv("PDF_URL", "https://www.cei.ci/wp-content/uploads/2025/12/EDAN_2025_RESULTAT_NATIONAL_DETAILS.pdf")
PDF_PATH = "data/election_2025.pdf"
DB_PATH  = "data/election.duckdb"

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
    m = re.match(
        r"^(\d{3})\s+(.+?)\s+([\d][\d\s]{1,5})\s+([\d][\d\s]{2,8})\s+([\d][\d\s]{2,8})\s+([\d,\.]+)\s*%\s+([\d][\d\s]{0,8})\s+([\d][\d\s]{2,8})\s+([\d]+)\s+([\d,\.]+)\s*%?",
        line
    )
    if m:
        return {
            "circ_num":           m.group(1).strip(),
            "circ_name":          norm_upper(m.group(2)),
            "inscrits":           to_int(m.group(4)),
            "votants":            to_int(m.group(5)),
            "taux_participation": to_float(m.group(6)),
            "blancs_nuls":        to_int(m.group(7)),
            "exprimes":           to_int(m.group(8)),
        }
    return None

REGIONS = [
    "AGNEBY", "BAFING", "BAGOUE", "BELIER", "BERE", "BOUNKANI", "CAVALLY",
    "DISTRICT", "FOLON", "GBEKE", "GBOKLE", "GOH", "GONTOUGO", "GRANDS PONTS",
    "GUEMON", "HAMBOL", "HAUT", "IFFOU", "INDENIE", "KABADOUGOU", "LA ME",
    "LOH", "MARAHOUE", "MORONOU", "NAWA", "N ZI", "PORO", "SAN",
    "SASSANDRA", "SUD", "TCHOLOGO", "TONKPI", "WORODOUGOU", "ZANZAN"
]

def is_region(line):
    up = norm_upper(line)
    return any(up == r or up.startswith(r + " ") or up.startswith(r + "-") for r in REGIONS)

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

def parse_pages(pages):
    records = []
    current_region    = ""
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
            if is_region(line):
                current_region = norm_upper(line)
                continue
            circ = parse_circ_line(line)
            if circ:
                current_circ_num  = circ["circ_num"]
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
                    records.append({
                        "source_page":        page_num,
                        "region":             current_region,
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
    print(f"DuckDB loaded:")
    print(f"  {count} candidate rows")
    print(f"  {winners} elus")
    print(f"  {regions} regions")
    print(f"  {circs} circonscriptions")
    print(f"  {partis} partis")
    print("\nSample winners:")
    print(con.execute("SELECT circ_num, circonscription, candidat, parti, voix FROM vw_winners LIMIT 5").df().to_string())
    con.close()

def run():
    download_pdf()
    pages = extract_text_pages()
    records = parse_pages(pages)
    if not records:
        print("ERROR: No records parsed!")
        return
    df = pd.DataFrame(records)
    print(df.head(3).to_string())
    df.to_csv("data/election_2025.csv", index=False)
    print("CSV saved")
    load_to_duckdb(df)
    print("\nIngestion complete!")

if __name__ == "__main__":
    run()