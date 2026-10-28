"""Summarize the human annotations created by evaluate_answers.py."""
import argparse
import csv
import json
from pathlib import Path


def flag(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("review_csv", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with args.review_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    refusal_rows = [(flag(row.get("should_refuse", "")), flag(row.get("model_refused", ""))) for row in rows]
    refusal_rows = [(gold, pred) for gold, pred in refusal_rows if gold is not None and pred is not None]
    tp = sum(gold and pred for gold, pred in refusal_rows)
    fp = sum(not gold and pred for gold, pred in refusal_rows)
    fn = sum(gold and not pred for gold, pred in refusal_rows)
    def mean_score(column: str):
        values = [float(row[column]) for row in rows if row.get(column, "").strip() in {"0", "1", "2"}]
        return round(sum(values) / len(values), 4) if values else None
    report = {
        "status": "SCORED_HUMAN_ANNOTATIONS" if refusal_rows else "AWAITING_HUMAN_ANNOTATIONS",
        "reviewed_question_count": len(rows), "refusal_label_count": len(refusal_rows),
        "refusal_precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "refusal_recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "correctness_mean_0_2": mean_score("correctness_0_2"),
        "groundedness_mean_0_2": mean_score("grounded_0_2"),
        "citation_support_mean_0_2": mean_score("citation_supported_0_2"),
        "note": "Scores are human-entered; no model-as-judge labels are used.",
    }
    output = args.output or args.review_csv.with_suffix(".scores.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
