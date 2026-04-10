# Write-up — Election Chat EDAN 2025

## What I built

A conversational agent that lets anyone query the official results of the
Ivorian National Assembly elections of December 27, 2025 (EDAN 2025) in
natural language. The data comes from the official CEI (Commission Electorale
Independante) PDF — 35 pages, 964 candidates, 186 constituencies, 31 regions.

The app answers questions like:
- "How many seats did the RHDP win?"
- "Who won in constituency 015?"
- "What was the voter turnout in the Gbeke region?"
- "Tell me about the results in Abidjan"

---

## Schema design decisions

The PDF has a complex structure — results are laid out as a wide table with
regions written vertically on the left margin, constituency data on one line,
and candidate rows below. Key decisions:

**Region extraction**: Rather than a hardcoded mapping, I implemented spatial
extraction using pdfplumber word coordinates. Words with x0 < 45px belong to
the region column. Since regions are written vertically letter by letter, I
collect the fragments, reverse them, and fuzzy-match against known region names
using rapidfuzz. A forward-fill pass assigns regions to constituencies that
appear before their region label in the PDF.

**Inline candidates**: Some lines contain both constituency data and a candidate
result on the same line (e.g. constituencies with only one candidate). I built
a dedicated parser for this format that runs before the regular parsers.

**DuckDB views**: Three views simplify queries — vw_winners (elected only),
vw_turnout (participation stats per constituency), vw_results_clean (all
candidates with clean columns).

---

## Hybrid routing

Questions split into two paths:

**SQL path** — analytics, aggregations, rankings. The LLM generates a SELECT
query with guardrails (SELECT only, LIMIT 50, blocked keywords). Accent
normalization via unidecode ensures "Gbêkê" matches "GBEKE" in the DB.

**RAG path** — narrative, fuzzy, open-ended questions. 1151 chunks embedded
with text-embedding-3-small and indexed in FAISS. Top-8 chunks retrieved and
synthesized by GPT-4o-mini with source attribution.

The router uses keyword matching — explicit analytics keywords route to SQL,
narrative keywords route to RAG, short factual queries default to SQL.

---

## Disambiguation

Before routing, an entity detector scans the question for ambiguous terms.
If a word matches multiple candidates, constituencies, or regions in the DB,
the agent returns a clarification question listing the options instead of
guessing. A stop-word list prevents common French words from triggering false
positives.

---

## Evaluation

11/11 tests passing (100%):
- Fact lookup: named entity retrieval from the DB
- Aggregation: seat counts per party
- Out-of-scope: questions outside the electoral dataset
- Guardrails: SQL injection, prompt injection, API key extraction attempts

---

## Limitations

**Page boundary parsing**: When a candidate's row appears on a different page
than their constituency header, they may be assigned to the wrong constituency.
This affects a small number of records (estimated < 5%).

**Region fuzzy matching**: The vertical text extraction produces garbled
fragments. Fuzzy matching handles most cases well but rare regions with short
names (e.g. "ME", "GOH") risk false matches.

**Router precision**: The keyword-based router occasionally misclassifies
borderline questions. A learned classifier trained on labeled examples would
improve this.

**Single-turn only**: The app has no cross-turn memory. Pronouns and references
("the same region", "and what about them") are not resolved.

---

## Next steps

- Fix page-boundary candidate assignment with a two-pass parser
- Replace keyword router with a fine-tuned classifier
- Add multi-turn memory using a conversation buffer
- Deploy to Streamlit Cloud with a read-only DB snapshot
- Add a region vs region comparison mode
- Expose traces in a live observability dashboard
