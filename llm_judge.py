#!/usr/bin/env python3
"""
LLM-as-Judge Evaluation Script

Evaluates image pairs from comparisons.csv using multiple LLM judges.
Each judge independently chooses which image better matches the prompt.

Usage:
    uv run llm_judge.py
    uv run llm_judge.py --comparisons comparisons.csv --output judge_results.csv
"""

from __future__ import annotations

import csv
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

import yaml

from models import get_judge_response

ROOT = Path(__file__).resolve().parent
JUDGES_CONFIG_PATH = ROOT / "judges_config.yaml"
BATCH_OUTPUTS_DIR = ROOT / "batch_outputs"
DEFAULT_COMPARISONS_CSV = ROOT / "comparisons.csv"
DEFAULT_OUTPUT_CSV = ROOT / "judge_results.csv"


def load_judges_config() -> Dict[str, Any]:
    """Load the judges YAML config."""
    if not JUDGES_CONFIG_PATH.exists():
        print(f"❌ Judges config file not found: {JUDGES_CONFIG_PATH}")
        sys.exit(1)

    with JUDGES_CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def sanitize_model_name(model: str) -> str:
    """Convert provider/model notation into filesystem-friendly name."""
    name = model.split("/", 1)[-1] if "/" in model else model
    safe = "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in name)
    return safe.strip("-") or "model"


def load_comparisons(csv_path: Path) -> List[Dict[str, str]]:
    """Load comparisons from CSV and return unique triplets."""
    if not csv_path.exists():
        print(f"❌ Comparisons CSV not found: {csv_path}")
        sys.exit(1)

    comparisons = []
    seen = set()

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder_path = row.get("folder_path", "")
            model_a = row.get("model_a", "")
            model_b = row.get("model_b", "")
            winner = row.get("winner", "")

            if not all([folder_path, model_a, model_b]):
                continue

            # Create unique key for deduplication
            key = (folder_path, model_a, model_b)
            if key in seen:
                continue
            seen.add(key)

            comparisons.append({
                "folder_path": folder_path,
                "model_a": model_a,
                "model_b": model_b,
                "human_winner": winner,
            })

    return comparisons


def load_existing_results(csv_path: Path) -> set:
    """Load existing results and return set of (folder_path, model_a, model_b) keys."""
    if not csv_path.exists():
        return set()

    existing = set()
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (
                row.get("folder_path", ""),
                row.get("model_a", ""),
                row.get("model_b", ""),
            )
            existing.add(key)

    return existing


def append_result_to_csv(csv_path: Path, result: Dict[str, str], fieldnames: List[str]) -> None:
    """Append a single result to the CSV file, creating with header if needed."""
    file_exists = csv_path.exists()

    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(result)


def get_prompt_text(folder_path: str) -> str:
    """Read the prompt text from a folder."""
    prompt_file = BATCH_OUTPUTS_DIR / folder_path / "prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text().strip()
    return ""


def get_image_paths(folder_path: str, model_a: str, model_b: str) -> tuple[Path, Path]:
    """Get the PNG file paths for both models."""
    folder = BATCH_OUTPUTS_DIR / folder_path
    image_a = folder / f"{model_a}.png"
    image_b = folder / f"{model_b}.png"
    return image_a, image_b


def evaluate_single_judge(
    judge_model: str,
    prompt: str,
    image_a_path: Path,
    image_b_path: Path,
) -> tuple[str, str]:
    """Run a single judge evaluation and return (judge_name, winner)."""
    try:
        winner = get_judge_response(judge_model, prompt, image_a_path, image_b_path)
        return (sanitize_model_name(judge_model), winner)
    except Exception as exc:
        print(f"    ⚠️  {judge_model} failed: {exc}")
        return (sanitize_model_name(judge_model), "error")


def evaluate_comparison(
    comparison: Dict[str, str],
    judges: List[str],
    max_workers: int,
) -> Dict[str, str]:
    """Evaluate a single comparison with all judges in parallel."""
    folder_path = comparison["folder_path"]
    model_a = comparison["model_a"]
    model_b = comparison["model_b"]

    prompt = get_prompt_text(folder_path)
    if not prompt:
        print(f"  ⚠️  No prompt found for {folder_path}")
        return None

    image_a_path, image_b_path = get_image_paths(folder_path, model_a, model_b)

    if not image_a_path.exists():
        print(f"  ⚠️  Image not found: {image_a_path}")
        return None
    if not image_b_path.exists():
        print(f"  ⚠️  Image not found: {image_b_path}")
        return None

    # Run all judges in parallel
    result = {
        "folder_path": folder_path,
        "model_a": model_a,
        "model_b": model_b,
        "human_winner": comparison["human_winner"],
    }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                evaluate_single_judge, judge, prompt, image_a_path, image_b_path
            ): judge
            for judge in judges
        }

        for future in as_completed(futures):
            judge_name, winner = future.result()
            result[judge_name] = winner

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="LLM-as-Judge Evaluation")
    parser.add_argument(
        "--comparisons",
        type=Path,
        default=DEFAULT_COMPARISONS_CSV,
        help="Path to comparisons CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help="Path to output CSV",
    )
    args = parser.parse_args()

    # Load config
    config = load_judges_config()
    judges: List[str] = config.get("judges", []) or []
    settings = config.get("settings", {}) or {}
    max_workers = max(1, int(settings.get("max_workers", 4)))

    if not judges:
        print("❌ No judges configured in judges_config.yaml")
        sys.exit(1)

    # Load comparisons
    comparisons = load_comparisons(args.comparisons)
    if not comparisons:
        print("❌ No valid comparisons found in CSV")
        sys.exit(1)

    # Load existing results to skip already-judged comparisons
    existing_results = load_existing_results(args.output)

    # Prepare CSV headers
    judge_columns = [sanitize_model_name(j) for j in judges]
    fieldnames = ["folder_path", "model_a", "model_b", "human_winner"] + judge_columns

    # Filter out already-judged comparisons
    pending_comparisons = [
        c for c in comparisons
        if (c["folder_path"], c["model_a"], c["model_b"]) not in existing_results
    ]

    print(f"📋 Loaded {len(comparisons)} unique comparisons")
    print(f"✅ Already judged: {len(existing_results)}")
    print(f"⏳ Pending: {len(pending_comparisons)}")
    print(f"🧑‍⚖️ Using {len(judges)} judges: {', '.join(judges)}")
    print(f"📁 Output: {args.output}")
    print(f"🚀 Starting evaluation...\n")

    if not pending_comparisons:
        print("Nothing to do - all comparisons already judged!")
        return

    evaluated_count = 0
    total = len(pending_comparisons)

    for idx, comparison in enumerate(pending_comparisons, 1):
        folder_short = comparison["folder_path"].split("/")[-1][:40]
        print(f"[{idx}/{total}] {folder_short}...")
        print(f"    {comparison['model_a']} vs {comparison['model_b']}")

        result = evaluate_comparison(comparison, judges, max_workers)
        if result:
            # Write result immediately to CSV
            append_result_to_csv(args.output, result, fieldnames)
            evaluated_count += 1

            # Show judge decisions
            decisions = []
            for jc in judge_columns:
                winner = result.get(jc, "?")
                decisions.append(f"{jc[:20]}={winner}")
            print(f"    → {', '.join(decisions)}\n")
        else:
            print(f"    → Skipped\n")

    print("\n" + "=" * 60)
    print("📊 EVALUATION COMPLETE")
    print("=" * 60)
    print(f"  Comparisons evaluated: {evaluated_count}/{total}")
    print(f"  Total in results file: {len(existing_results) + evaluated_count}")
    print(f"  Judges used: {len(judges)}")
    print(f"  📁 Results saved to: {args.output}")


if __name__ == "__main__":
    main()

