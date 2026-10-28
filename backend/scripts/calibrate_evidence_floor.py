"""Suggest a per-evidence floor from manually judged retrieved candidates.

Input CSV must contain score and relevant columns, where relevant is 0/1.
The tool selects the lowest threshold meeting the requested precision target
while retaining the most judged relevant items. It never edits .env.
"""
import argparse
import csv
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--precision", type=float, default=0.9)
    parser.add_argument("--minimum-items", type=int, default=30)
    args = parser.parse_args()
    rows = []
    with args.csv.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            try:
                score = float(row["score"])
                relevant = int(row["relevant"])
            except (KeyError, TypeError, ValueError):
                continue
            if relevant in (0, 1):
                rows.append((score, relevant))
    if len(rows) < args.minimum_items or len({label for _, label in rows}) < 2:
        raise SystemExit(f"Need at least {args.minimum_items} judgments and both relevant=0/1; got {len(rows)}")
    candidates = sorted({score for score, _ in rows})
    eligible = []
    for threshold in candidates:
        kept = [(score, label) for score, label in rows if score >= threshold]
        precision = sum(label for _, label in kept) / len(kept)
        recall = sum(label for _, label in kept) / sum(label for _, label in rows)
        if precision >= args.precision:
            eligible.append((recall, threshold, precision, len(kept)))
    if not eligible:
        raise SystemExit("No threshold reached target precision; collect more labels or review the retrieval model.")
    recall, threshold, precision, retained = max(eligible)
    print(json.dumps({"suggested_min_evidence_score": threshold, "precision": round(precision, 4), "recall": round(recall, 4), "retained": retained, "judged": len(rows), "target_precision": args.precision}, ensure_ascii=False, indent=2))
    print("Review this threshold on a separate holdout set before setting MIN_EVIDENCE_SCORE.")

if __name__ == "__main__":
    main()
