import pdfplumber
from unidecode import unidecode
from rapidfuzz import process, fuzz

KNOWN_REGIONS = [
    "AGNEBY-TIASSA", "BAFING", "BAGOUE", "BELIER", "BERE", "BOUNKANI",
    "CAVALLY", "DISTRICT AUTONOME D ABIDJAN", "DISTRICT AUTONOME DE YAMOUSSOUKRO",
    "FOLON", "GBEKE", "GBOKLE", "GOH", "GONTOUGO", "GRANDS PONTS",
    "GUEMON", "HAMBOL", "HAUT-SASSANDRA", "IFFOU", "INDENIE-DJUABLIN",
    "KABADOUGOU", "LA ME", "LOH-DJIBOUA", "MARAHOUE", "ME", "MORONOU",
    "NAWA", "N ZI", "PORO", "SAN-PEDRO", "SUD-COMOE", "TCHOLOGO",
    "TONKPI", "WORODOUGOU", "ZANZAN"
]

def match_region(text, threshold=60):
    t = unidecode(text.upper().strip())
    if len(t) < 3:
        return None
    result = process.extractOne(t, KNOWN_REGIONS, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= threshold:
        return result[0]
    return None

def extract_regions_from_page(page):
    words = page.extract_words()
    region_col = [w for w in words
                  if w['x0'] < 45 and w['x1'] < 80
                  and w['text'] not in ['REGI', 'ON']]
    region_col = sorted(region_col, key=lambda x: x['top'])

    segments = []
    current_letters = []

    for w in region_col:
        text = w['text'].strip()
        if text.isdigit() and len(text) == 3:
            if current_letters:
                joined = "".join(reversed(current_letters))
                region = match_region(joined)
                segments.append({
                    "circ": text,
                    "joined": joined,
                    "matched": region,
                })
                current_letters = []
        else:
            current_letters.append(text)

    return segments

with pdfplumber.open('data/election_2025.pdf') as pdf:
    for page_num in range(len(pdf.pages)):
        page = pdf.pages[page_num]
        segments = extract_regions_from_page(page)
        if segments:
            print(f"\n=== PAGE {page_num+1} ===")
            for s in segments:
                print(f"  circ={s['circ']} joined='{s['joined']}' → {s['matched']}")
