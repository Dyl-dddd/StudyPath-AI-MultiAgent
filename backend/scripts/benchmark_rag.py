"""Record retrieval phase timings and a small concurrent-request baseline."""
import argparse
import concurrent.futures
import json
import statistics
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
    parser.add_argument("--requests-per-level", type=int, default=12)
    parser.add_argument("--after-process-restart", action="store_true", help="mark that the API process was restarted just before this run")
    parser.add_argument("--output", default=str(ROOT / "evaluation" / "results" / "performance-latest.json"))
    args = parser.parse_args()
    questions = [json.loads(line)["question"] for line in (ROOT / "evaluation" / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = questions[:min(len(questions), args.requests_per_level)]
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        login = client.post("/auth/login", json={"username": args.username, "password": args.password})
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        kb_response = client.post("/knowledge-bases", json={"name": f"Performance Eval {time.strftime('%Y%m%d-%H%M%S')}", "course_name": "操作系统"})
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
            session_response = client.post("/rag/sessions", json={"knowledge_base_id": kb_id, "title": "Performance baseline"})
            session_response.raise_for_status()
            session_id = session_response.json()["id"]

            # First call captures first-use retrieval after indexing. With a fresh
            # API process, this also includes lazy reranker initialization.
            cold_start = time.perf_counter()
            cold_response = client.post("/rag/retrieve", json={"session_id": session_id, "question": questions[0]})
            cold_response.raise_for_status()
            cold_wall_ms = round((time.perf_counter() - cold_start) * 1000, 2)
            cold_timings = cold_response.json().get("timings_ms", {})

            levels = {}
            for concurrency in (1, 4, 8):
                results = []
                def request(index: int):
                    question = questions[index % len(questions)]
                    started = time.perf_counter()
                    response = client.post("/rag/retrieve", json={"session_id": session_id, "question": question})
                    elapsed = (time.perf_counter() - started) * 1000
                    response.raise_for_status()
                    return elapsed, response.json().get("timings_ms", {})
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                    futures = [pool.submit(request, index) for index in range(args.requests_per_level)]
                    for future in concurrent.futures.as_completed(futures):
                        results.append(future.result())
                totals = [entry[0] for entry in results]
                phase_names = sorted({key for _, timing in results for key in timing if key.endswith("_ms")})
                levels[str(concurrency)] = {
                    "request_count": len(results), "wall_p50_ms": percentile(totals, .5), "wall_p95_ms": percentile(totals, .95),
                    "wall_mean_ms": round(statistics.mean(totals), 2),
                    "phase_mean_ms": {name: round(statistics.mean([timing[name] for _, timing in results if name in timing]), 2) for name in phase_names},
                    "error_count": 0,
                }
            health = client.get("/health")
            health.raise_for_status()
            report = {
                "status": "EXECUTED_RETRIEVAL_ONLY",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model_generation_included": False,
                "warmup_count": 0,
                "first_request_after_indexing": {"wall_ms": cold_wall_ms, "phases_ms": cold_timings},
                "api_restarted_before_run": args.after_process_restart,
                "concurrency_levels": levels,
                "host_context": {"embedding_model": health.json().get("embedding_model"), "reranker_configured": health.json().get("reranker_configured"), "reranker_gate_enabled": health.json().get("reranker_gate_enabled"), "reranker_min_score": health.json().get("reranker_min_score")},
                "limitations": ["本机小样本，不代表生产硬件", "HTTP 请求并发压测，不包含模型生成", "未测多进程/多实例部署"],
            }
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print(f"Report: {output}")
        finally:
            client.delete(f"/knowledge-bases/{kb_id}").raise_for_status()


if __name__ == "__main__":
    main()
