"""
Tracer — EDAN 2025
End-to-end request tracing for observability
"""

import time
import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

TRACE_LOG = "data/traces.jsonl"


@dataclass
class Trace:
    trace_id:        str
    timestamp:       str
    question:        str
    question_norm:   str = ""
    routing:         str = ""          # sql | rag | clarification | blocked
    intent:          str = ""          # aggregation | ranking | factual | out_of_scope
    ambiguous:       bool = False
    sql_generated:   Optional[str] = None
    sql_valid:       bool = True
    sql_error:       Optional[str] = None
    rag_chunks:      int = 0
    rag_top_score:   float = 0.0
    rows_returned:   int = 0
    chart_type:      str = "none"
    answer_length:   int = 0
    latency_ms:      float = 0.0
    tokens_input:    int = 0
    tokens_output:   int = 0
    error:           Optional[str] = None


class RequestTracer:
    def __init__(self, question: str):
        self.trace = Trace(
            trace_id  = datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
            timestamp = datetime.now().isoformat(),
            question  = question,
        )
        self._start = time.time()

    def set_routing(self, routing: str):
        self.trace.routing = routing

    def set_intent(self, intent: str):
        self.trace.intent = intent

    def set_ambiguous(self, ambiguous: bool):
        self.trace.ambiguous = ambiguous

    def set_sql(self, sql: str, valid: bool, error: str = None):
        self.trace.sql_generated = sql
        self.trace.sql_valid     = valid
        self.trace.sql_error     = error

    def set_rag(self, chunks: int, top_score: float):
        self.trace.rag_chunks    = chunks
        self.trace.rag_top_score = top_score

    def set_result(self, rows: int, chart_type: str, answer: str):
        self.trace.rows_returned  = rows
        self.trace.chart_type     = chart_type
        self.trace.answer_length  = len(answer)

    def set_tokens(self, input_tokens: int, output_tokens: int):
        self.trace.tokens_input  = input_tokens
        self.trace.tokens_output = output_tokens

    def set_error(self, error: str):
        self.trace.error = error

    def set_question_norm(self, q: str):
        self.trace.question_norm = q

    def finish(self) -> Trace:
        self.trace.latency_ms = round((time.time() - self._start) * 1000, 2)
        self._save()
        return self.trace

    def _save(self):
        os.makedirs("data", exist_ok=True)
        with open(TRACE_LOG, "a") as f:
            f.write(json.dumps(asdict(self.trace)) + "\n")


def load_traces() -> list:
    """Load all traces from log file."""
    if not os.path.exists(TRACE_LOG):
        return []
    traces = []
    with open(TRACE_LOG) as f:
        for line in f:
            try:
                traces.append(json.loads(line.strip()))
            except:
                pass
    return traces


def get_stats() -> dict:
    """Compute aggregate stats from traces."""
    traces = load_traces()
    if not traces:
        return {}

    total      = len(traces)
    sql_count  = sum(1 for t in traces if t.get("routing") == "sql")
    rag_count  = sum(1 for t in traces if t.get("routing") == "rag")
    blocked    = sum(1 for t in traces if t.get("routing") == "blocked")
    errors     = sum(1 for t in traces if t.get("error"))
    avg_latency= sum(t.get("latency_ms", 0) for t in traces) / total
    avg_tokens = sum(t.get("tokens_input", 0) + t.get("tokens_output", 0) for t in traces) / total

    return {
        "total_requests": total,
        "sql_requests":   sql_count,
        "rag_requests":   rag_count,
        "blocked":        blocked,
        "errors":         errors,
        "avg_latency_ms": round(avg_latency, 2),
        "avg_tokens":     round(avg_tokens, 2),
        "success_rate":   round((total - errors) / total * 100, 1),
    }


if __name__ == "__main__":
    # Test tracer
    tracer = RequestTracer("Combien de sièges a gagné le RHDP ?")
    tracer.set_routing("sql")
    tracer.set_intent("aggregation")
    tracer.set_sql("SELECT COUNT(*) FROM vw_winners WHERE parti ILIKE '%RHDP%'", True)
    tracer.set_result(1, "none", "Le RHDP a gagné 100 sièges.")
    tracer.set_tokens(150, 50)
    trace = tracer.finish()
    print(f"Trace saved: {trace.trace_id}")
    print(f"Latency: {trace.latency_ms}ms")
    print(f"Stats: {get_stats()}")