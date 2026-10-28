"""Measure retrieval against the hand-labelled local course-material set.

Answer correctness and faithfulness are deliberately left for human annotation.
"""
import argparse
import csv
import json
import time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return round(values[min(len(values) - 1, max(0, round((len(values) - 1) * p)))], 4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--knowledge-base", default="StudyPath OS Evaluation")
    parser.add_argument("--output", default=str(ROOT / "evaluation" / "results" / "latest.json"))
    parser.add_argument("--relevance-review-output", default=str(ROOT / "evaluation" / "results" / "retrieval-relevance-review.csv"))
    args = parser.parse_args()
    questions = [json.loads(line) for line in (ROOT / "evaluation" / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows, latencies, reciprocal_ranks, recall_hits, evidence_precision = [], [], [], [], []
    relevance_review_rows = []
    no_answer_evidence = []
    no_answer_abstentions = []
    answerable_retained = []
    scored_labels: list[tuple[float, bool, str]] = []
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        login = client.post("/auth/login", json={"username": args.username, "password": args.password})
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        kb = client.post("/knowledge-bases", json={"name": args.knowledge_base, "course_name": "操作系统"})
        kb.raise_for_status()
        kb_id = kb.json()["id"]
        try:
            with (ROOT / "examples" / "operating_systems_sample.md").open("rb") as file:
                upload = client.post(f"/knowledge-bases/{kb_id}/documents", files={"file": ("operating_systems_sample.md", file, "text/markdown")})
            upload.raise_for_status()
            document_id = upload.json()["id"]
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                state_response = client.get(f"/documents/{document_id}/status")
                state_response.raise_for_status()
                state = state_response.json()
                if state["status"] in ("READY", "FAILED"):
                    break
                time.sleep(1)
            if state["status"] != "READY":
                raise RuntimeError(f"sample document indexing did not finish: {state['status']} {state['error_message']}")
            session = client.post("/rag/sessions", json={"knowledge_base_id": kb_id, "title": "Evaluation"})
            session.raise_for_status()
            session_id = session.json()["id"]
            for item in questions:
                start = time.perf_counter()
                response = client.post("/rag/retrieve?include_candidates=true", json={"session_id": session_id, "question": item["question"]})
                elapsed = time.perf_counter() - start
                response.raise_for_status()
                result = response.json()
                citations = result["citations"]
                for rank, citation in enumerate(result.get("candidates", citations), 1):
                    relevance_review_rows.append({"question": item["question"], "rank": rank,
                        "document_name": citation["document_name"], "section_title": citation["section_title"],
                        "snippet": citation["snippet"], "score": citation["retrieval_score"], "relevant": "", "review_notes": ""})
                split = item.get("split", "calibration")
                scored_labels.append((float(citations[0]["retrieval_score"]) if citations else 0.0, bool(item["no_answer"]), split))
                expected = item["expected_section"]
                ranks = [i for i, cite in enumerate(citations, 1) if expected and expected in cite["section_title"]]
                supported = not item["no_answer"]
                if supported:
                    answerable_retained.append(bool(citations))
                    reciprocal_ranks.append(1 / ranks[0] if ranks else 0)
                    recall_hits.append(bool(ranks))
                    evidence_precision.append(sum(1 for cite in citations if expected in cite["section_title"]) / max(1, len(citations)))
                else:
                    no_answer_evidence.append(bool(citations))
                    no_answer_abstentions.append(not citations)
                latencies.append(elapsed)
                rows.append({"question": item["question"], "expected_section": expected, "no_answer": item["no_answer"], "split": split, "retrieval_mode": result["retrieval_mode"], "retrieved_sections": [cite["section_title"] for cite in citations], "retrieval_scores": [round(cite["retrieval_score"], 4) for cite in citations], "expected_hit": bool(ranks), "latency_seconds": round(elapsed, 4)})
            health = client.get("/health")
            health.raise_for_status()
            split_metrics = {}
            for split in sorted({row["split"] for row in rows}):
                split_rows = [row for row in rows if row["split"] == split]
                answerable_rows = [row for row in split_rows if not row["no_answer"]]
                no_answer_rows = [row for row in split_rows if row["no_answer"]]
                split_metrics[split] = {
                    "question_count": len(split_rows),
                    "answerable_question_count": len(answerable_rows),
                    "answerable_evidence_retention": round(sum(bool(row["retrieved_sections"]) for row in answerable_rows) / max(1, len(answerable_rows)), 4) if answerable_rows else None,
                    "no_answer_question_count": len(no_answer_rows),
                    "no_answer_abstention_rate": round(sum(not row["retrieved_sections"] for row in no_answer_rows) / max(1, len(no_answer_rows)), 4) if no_answer_rows else None,
                }
            report = {
                "status": "EXECUTED", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "dataset": str(ROOT / "evaluation" / "questions.jsonl"), "question_count": len(rows),
                "answerable_question_count": len(recall_hits), "no_answer_question_count": len(no_answer_evidence),
                "embedding_model": health.json()["embedding_model"], "retrieval_modes": sorted({row["retrieval_mode"] for row in rows}),
                "reranker_configured": health.json().get("reranker_configured", False),
                "reranker_gate_enabled": health.json().get("reranker_gate_enabled", False),
                "reranker_min_score": health.json().get("reranker_min_score"),
                "metrics_by_split": split_metrics,
                "retrieval_recall_at_5": round(sum(recall_hits) / max(1, len(recall_hits)), 4),
                "mrr_at_5": round(sum(reciprocal_ranks) / max(1, len(reciprocal_ranks)), 4),
                "evidence_precision_at_5": round(sum(evidence_precision) / max(1, len(evidence_precision)), 4),
                "no_answer_retrieval_evidence_rate": round(sum(no_answer_evidence) / max(1, len(no_answer_evidence)), 4),
                "no_answer_abstention_rate": round(sum(no_answer_abstentions) / max(1, len(no_answer_abstentions)), 4),
                "answerable_evidence_retention": round(sum(answerable_retained) / max(1, len(answerable_retained)), 4),
                "p50_seconds": percentile(latencies, .5), "p95_seconds": percentile(latencies, .95),
                "answer_faithfulness": "NOT MEASURED: requires human annotation",
                "answer_correctness": "NOT MEASURED: requires human annotation",
                "no_answer_accuracy": "NOT MEASURED: requires generated-answer review", "cases": rows,
            }
            if "rerank" in " ".join(report["retrieval_modes"]) and not health.json().get("reranker_gate_enabled"):
                calibration = [(score, unsupported) for score, unsupported, split in scored_labels if split == "calibration"]
                holdout_no_answer = [score for score, unsupported, split in scored_labels if split == "holdout" and unsupported]
                thresholds = sorted({0.0, *(score for score, _ in calibration), *(score + 1e-6 for score, _ in calibration)})
                sweep = []
                for threshold in thresholds:
                    retained = [score >= threshold for score, unsupported in calibration if not unsupported]
                    abstained = [score < threshold for score, unsupported in calibration if unsupported]
                    if retained and abstained:
                        sweep.append({"threshold": round(threshold, 6), "answerable_retention": round(sum(retained) / len(retained), 4), "no_answer_abstention": round(sum(abstained) / len(abstained), 4)})
                eligible = [item for item in sweep if item["answerable_retention"] >= 0.9]
                recommendation = max(eligible, key=lambda item: (item["no_answer_abstention"], item["answerable_retention"])) if eligible else None
                report["reranker_threshold_sweep_calibration"] = sweep
                report["recommended_threshold_calibration"] = recommendation
                if recommendation is not None and holdout_no_answer:
                    report["holdout_no_answer_abstention_rate_at_recommended_threshold"] = round(sum(score < recommendation["threshold"] for score in holdout_no_answer) / len(holdout_no_answer), 4)
            output = Path(args.output)
            if output.exists():
                output = output.with_name(f"{output.stem}-{time.strftime('%Y%m%d-%H%M%S')}{output.suffix}")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            review_path = Path(args.relevance_review_output)
            review_path.parent.mkdir(parents=True, exist_ok=True)
            with review_path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["question", "rank", "document_name", "section_title", "snippet", "score", "relevant", "review_notes"])
                writer.writeheader()
                writer.writerows(relevance_review_rows)
            print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))
            print(f"Manual retrieval relevance labels: {review_path}")
        finally:
            client.delete(f"/knowledge-bases/{kb_id}").raise_for_status()


if __name__ == "__main__":
    main()
