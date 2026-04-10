# Election Chat — EDAN 2025

Chat with the official results of the Ivorian National Assembly elections of December 27, 2025, powered by a hybrid SQL + RAG agent.

**Data source**: Commission Électorale Indépendante (CEI)

---

## Architecture
User Question
↓
Disambiguator
↓
Router
↙     ↘
SQL     RAG
↘     ↙
Answer
## 4 Levels

| Level | Feature | Status |
|-------|---------|--------|
| 1 | Text-to-SQL Agent | Done |
| 2 | Hybrid Router SQL + RAG | Done |
| 3 | Disambiguation + Clarification | Done |
| 4 | Observability + Evaluation | Done |

---

## Dataset

| Metric | Value |
|--------|-------|
| Candidates | 964 |
| Elected deputies | 170 |
| Constituencies | 186 |
| Regions | 31 |
| Political parties | 32 |
| RHDP seats | 123 |
| PDCI-RDA seats | 23 |
| Independent elected | 22 |

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/Thekidmaroi/election-chat
cd election-chat
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Add your OpenAI API key in .env
```

### 4. Ingest data
```bash
python3 ingestion/ingest.py
```

### 5. Build RAG index
```bash
python3 rag/indexer.py
```

### 6. Run the app
```bash
streamlit run app/app.py
```

---

## Evaluation

```bash
python3 eval/eval_suite.py
```

Results: 11/11 — 100%
- Fact lookup: 3/3
- Aggregation: 3/3
- Out of scope: 2/2
- Guardrails: 3/3

---

## Project Structure
---

## Tech Stack

- LLM: GPT-4o-mini
- Embeddings: text-embedding-3-small
- Vector DB: FAISS
- SQL DB: DuckDB
- PDF: pdfplumber
- UI: Streamlit + Plotly
- Fuzzy matching: rapidfuzz + unidecode

---

## Guardrails

- SQL: SELECT only, LIMIT 50, blocked keywords
- Out-of-scope questions rejected
- Disambiguation for ambiguous entities
- API keys via environment variables only

---

## Limitations

- PDF parsing: candidates on page boundaries may be mis-assigned
- Region extraction uses fuzzy matching — rare edge cases possible
- RAG works best for named entity queries

## Next Steps

- Multi-turn conversation memory
- Deploy to Streamlit Cloud
- Region vs region comparison mode
