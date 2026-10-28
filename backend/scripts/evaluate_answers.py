"""Run a limited real-provider answer evaluation against the labelled holdout set.

The script only stores model output, retrieval metadata, and an empty human-review
template. It does not use another LLM as a judge and never writes credentials.
"""
import argparse
import csv
import json
import re
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, round((len(ordered) - 1) * quantile))], 2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--output", default=str(ROOT / "evaluation" / "results" / "answer-quality-latest.json"))
    parser.add_argument("--split", default="holdout")
    parser.add_argument("--question-contains", default="", help="optionally run one targeted case for a prompt change")
    args = parser.parse_args()

    dataset = [json.loads(line) for line in (ROOT / "evaluation" / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = [item for item in dataset if item.get("split", "calibration") == args.split]
    if args.question_contains:
        questions = [item for item in questions if args.question_contains in item["question"]]
        if not questions:
            raise SystemExit("No question matched --question-contains")
    rows = []
    client = httpx.Client(base_url=args.base_url, timeout=120)
    try:
        login = client.post("/auth/login", json={"username": args.username, "password": args.password})
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        kb_response = client.post("/knowledge-bases", json={"name": f"Answer Eval {time.strftime('%Y%m%d-%H%M%S')}", "course_name": "操作系统"})
        kb_response.raise_for_status()
        kb_id = kb_response.json()["id"]
        try:
            with (ROOT / "examples" / "operating_systems_sample.md").open("rb") as source:
                upload = client.post(f"/knowledge-bases/{kb_id}/documents", files={"file": ("operating_systems_sample.md", source, "text/markdown")})
            upload.raise_for_status()
            document_id = upload.json()["id"]
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                state = client.get(f"/documents/{document_id}/status").json()
                if state["status"] in {"READY", "FAILED"}:
                    break
                time.sleep(0.5)
            if state["status"] != "READY":
                raise RuntimeError(f"sample indexing failed: {state['status']} {state.get('error_message', '')}")

            for number, item in enumerate(questions, 1):
                session_response = client.post("/rag/sessions", json={"knowledge_base_id": kb_id, "title": f"Answer eval {number}"})
                session_response.raise_for_status()
                session_id = session_response.json()["id"]
                started = time.perf_counter()
                response = client.post("/rag/chat", json={"session_id": session_id, "question": item["question"]})
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                response.raise_for_status()
                result = response.json()
                citations = result.get("citations", [])
                markers = [int(value) for value in re.findall(r"\[(\d+)\]", result.get("answer", ""))]
                valid_markers = all(1 <= marker <= len(citations) for marker in markers)
                expected = item.get("expected_section", "")
                rows.append({
                    **item,
                    "answer": result.get("answer", ""),
                    "citations": [{"section_title": citation.get("section_title", ""), "document_name": citation.get("document_name", ""), "page_start": citation.get("page_start"), "chunk_id": citation.get("chunk_id"), "retrieval_score": citation.get("retrieval_score"), "snippet": citation.get("snippet", "")} for citation in citations],
                    "citation_marker_count": len(markers),
                    "citation_markers_in_range": valid_markers,
                    "expected_section_hit": any(expected and expected in citation.get("section_title", "") for citation in citations),
                    "retrieval_mode": result.get("retrieval_mode"),
                    "timings_ms": result.get("timings_ms", {"total_ms": elapsed_ms}),
                    "latency_ms": elapsed_ms,
                    "llm_was_needed": bool(citations),
                })
                print(f"[{number}/{len(questions)}] {item.get('category', 'unspecified')}: {elapsed_ms:.0f} ms; {len(citations)} citations")

            no_answer_rows = [row for row in rows if row.get("no_answer")]
            answerable_rows = [row for row in rows if not row.get("no_answer")]
            llm_latencies = [float(row["timings_ms"]["llm_ms"]) for row in rows if row.get("timings_ms", {}).get("llm_ms") is not None]
            report = {
                "status": "EXECUTED_REQUIRES_HUMAN_REVIEW",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "split": args.split,
                "answer_policy_version": "strict-evidence-only-v2",
                "question_count": len(rows),
                "category_counts": {category: sum(row.get("category", "unspecified") == category for row in rows) for category in sorted({row.get("category", "unspecified") for row in rows})},
                "answerable_count": len(answerable_rows),
                "no_answer_count": len(no_answer_rows),
                "llm_call_count": len(llm_latencies),
                "llm_generation_p50_ms": percentile(llm_latencies, .5),
                "llm_generation_p95_ms": percentile(llm_latencies, .95),
                "answerable_evidence_retention": round(sum(bool(row["citations"]) for row in answerable_rows) / max(1, len(answerable_rows)), 4),
                "out_of_scope_retrieval_abstention_rate": round(sum(not row["citations"] for row in no_answer_rows) / max(1, len(no_answer_rows)), 4) if no_answer_rows else None,
                "citation_marker_valid_rate": round(sum(row["citation_markers_in_range"] for row in rows) / max(1, len(rows)), 4),
                "section_match_precision_proxy": round(sum(sum(row["expected_section"] and row["expected_section"] in cite["section_title"] for cite in row["citations"]) / max(1, len(row["citations"])) for row in answerable_rows) / max(1, len(answerable_rows)), 4),
                "answer_correctness": "NOT SCORED: fill human review fields",
                "citation_support": "NOT SCORED: marker validity does not imply semantic support",
                "refusal_precision_recall": "NOT SCORED: fill human review fields",
                "cases": rows,
            }
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            review_path = output.with_name(f"{output.stem}-human-review.csv")
            with review_path.open("w", encoding="utf-8-sig", newline="") as handle:
                fields = ["question", "category", "expected_behavior", "reference_answer", "answer", "expected_section", "retrieved_sections", "citation_marker_count", "correctness_0_2", "grounded_0_2", "citation_supported_0_2", "should_refuse", "model_refused", "refusal_appropriate", "prompt_injection_ignored", "clarified_ambiguity", "notes"]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for row in rows:
                    writer.writerow({
                        "question": row["question"], "category": row.get("category", "unspecified"),
                        "expected_behavior": row.get("expected_behavior", ""), "reference_answer": row.get("reference_answer", ""),
                        "answer": row.get("answer", ""), "expected_section": row.get("expected_section", ""),
                        "retrieved_sections": " | ".join(cite["section_title"] for cite in row["citations"]),
                        "citation_marker_count": row.get("citation_marker_count", 0),
                        "correctness_0_2": "", "grounded_0_2": "", "citation_supported_0_2": "",
                        "should_refuse": "1" if row.get("no_answer") else "0", "model_refused": "", "refusal_appropriate": "", "prompt_injection_ignored": "", "clarified_ambiguity": "", "notes": "",
                    })
            print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))
            print(f"Report: {output}\nHuman review: {review_path}")
        finally:
            client.delete(f"/knowledge-bases/{kb_id}").raise_for_status()
    finally:
        client.close()


if __name__ == "__main__":
    main()
