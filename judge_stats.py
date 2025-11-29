#!/usr/bin/env python3
"""
Judge Statistics Script

Computes ELO rankings and agreement statistics from judge_results.csv.

Usage:
    uv run judge_stats.py
    uv run judge_stats.py --input judge_results.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_CSV = ROOT / "judge_results.csv"

# ELO parameters
INITIAL_ELO = 1500
K_FACTOR = 32


def load_results(csv_path: Path) -> List[Dict[str, str]]:
    """Load judge results from CSV."""
    if not csv_path.exists():
        print(f"❌ Results CSV not found: {csv_path}")
        return []

    results = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)

    return results


def get_judge_columns(results: List[Dict[str, str]]) -> List[str]:
    """Extract judge model column names from results."""
    if not results:
        return []

    # All columns except the known non-judge columns
    non_judge_cols = {"folder_path", "model_a", "model_b", "human_winner"}
    return [col for col in results[0].keys() if col not in non_judge_cols]


def compute_elo_rankings(
    results: List[Dict[str, str]], winner_column: str
) -> Dict[str, float]:
    """
    Compute ELO rankings for SVG generation models based on pairwise comparisons.
    
    Args:
        results: List of comparison results
        winner_column: Column name containing the winner ('a' or 'b')
    
    Returns:
        Dictionary mapping model names to ELO scores
    """
    elo_scores: Dict[str, float] = defaultdict(lambda: INITIAL_ELO)

    for row in results:
        model_a = row["model_a"]
        model_b = row["model_b"]
        winner = row.get(winner_column, "")

        if winner not in ("a", "b"):
            continue

        # Get current ratings
        rating_a = elo_scores[model_a]
        rating_b = elo_scores[model_b]

        # Calculate expected scores
        expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
        expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))

        # Actual scores
        if winner == "a":
            actual_a, actual_b = 1.0, 0.0
        else:
            actual_a, actual_b = 0.0, 1.0

        # Update ratings
        elo_scores[model_a] = rating_a + K_FACTOR * (actual_a - expected_a)
        elo_scores[model_b] = rating_b + K_FACTOR * (actual_b - expected_b)

    return dict(elo_scores)


def get_consensus_winner(row: Dict[str, str], judge_columns: List[str]) -> str:
    """
    Determine consensus winner from judge votes using majority voting.
    
    Returns 'a', 'b', or '' if no clear consensus.
    """
    votes_a = 0
    votes_b = 0

    for judge in judge_columns:
        vote = row.get(judge, "")
        if vote == "a":
            votes_a += 1
        elif vote == "b":
            votes_b += 1

    if votes_a > votes_b:
        return "a"
    elif votes_b > votes_a:
        return "b"
    else:
        return ""  # Tie


def compute_consensus_elo(
    results: List[Dict[str, str]], judge_columns: List[str]
) -> Dict[str, float]:
    """Compute ELO rankings based on consensus of judge models."""
    elo_scores: Dict[str, float] = defaultdict(lambda: INITIAL_ELO)

    for row in results:
        model_a = row["model_a"]
        model_b = row["model_b"]
        winner = get_consensus_winner(row, judge_columns)

        if winner not in ("a", "b"):
            continue

        # Get current ratings
        rating_a = elo_scores[model_a]
        rating_b = elo_scores[model_b]

        # Calculate expected scores
        expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
        expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))

        # Actual scores
        if winner == "a":
            actual_a, actual_b = 1.0, 0.0
        else:
            actual_a, actual_b = 0.0, 1.0

        # Update ratings
        elo_scores[model_a] = rating_a + K_FACTOR * (actual_a - expected_a)
        elo_scores[model_b] = rating_b + K_FACTOR * (actual_b - expected_b)

    return dict(elo_scores)


def compute_agreement_stats(
    results: List[Dict[str, str]], judge_columns: List[str]
) -> Dict[str, Tuple[int, int, float]]:
    """
    Compute agreement statistics between each judge and human judgment.
    
    Returns:
        Dictionary mapping judge name to (agreements, total, percentage)
    """
    stats: Dict[str, Tuple[int, int, float]] = {}

    for judge in judge_columns:
        agreements = 0
        total = 0

        for row in results:
            human_winner = row.get("human_winner", "")
            judge_winner = row.get(judge, "")

            # Only count valid comparisons
            if human_winner in ("a", "b") and judge_winner in ("a", "b"):
                total += 1
                if human_winner == judge_winner:
                    agreements += 1

        percentage = (agreements / total * 100) if total > 0 else 0.0
        stats[judge] = (agreements, total, percentage)

    return stats


def compute_inter_judge_agreement(
    results: List[Dict[str, str]], judge_columns: List[str]
) -> Dict[Tuple[str, str], Tuple[int, int, float]]:
    """
    Compute pairwise agreement between all judge models.
    
    Returns:
        Dictionary mapping (judge_a, judge_b) to (agreements, total, percentage)
    """
    stats: Dict[Tuple[str, str], Tuple[int, int, float]] = {}

    for i, judge_a in enumerate(judge_columns):
        for judge_b in judge_columns[i:]:  # Include self-comparison for diagonal
            agreements = 0
            total = 0

            for row in results:
                vote_a = row.get(judge_a, "")
                vote_b = row.get(judge_b, "")

                # Only count valid comparisons
                if vote_a in ("a", "b") and vote_b in ("a", "b"):
                    total += 1
                    if vote_a == vote_b:
                        agreements += 1

            percentage = (agreements / total * 100) if total > 0 else 0.0
            stats[(judge_a, judge_b)] = (agreements, total, percentage)
            if judge_a != judge_b:
                stats[(judge_b, judge_a)] = (agreements, total, percentage)

    return stats


def print_elo_ranking(title: str, elo_scores: Dict[str, float]) -> None:
    """Print ELO ranking table."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)

    if not elo_scores:
        print("  No data available")
        return

    # Sort by ELO score descending
    sorted_models = sorted(elo_scores.items(), key=lambda x: x[1], reverse=True)

    print(f"  {'Rank':<6} {'Model':<40} {'ELO':>8}")
    print(f"  {'-' * 6} {'-' * 40} {'-' * 8}")

    for rank, (model, elo) in enumerate(sorted_models, 1):
        print(f"  {rank:<6} {model:<40} {elo:>8.1f}")


def print_agreement_stats(
    stats: Dict[str, Tuple[int, int, float]]
) -> None:
    """Print agreement statistics table."""
    print(f"\n{'=' * 60}")
    print("  Judge Agreement with Human Judgments")
    print("=" * 60)

    if not stats:
        print("  No data available")
        return

    # Sort by agreement percentage descending
    sorted_judges = sorted(stats.items(), key=lambda x: x[1][2], reverse=True)

    print(f"  {'Judge Model':<35} {'Agree':>8} {'Total':>8} {'%':>8}")
    print(f"  {'-' * 35} {'-' * 8} {'-' * 8} {'-' * 8}")

    for judge, (agreements, total, percentage) in sorted_judges:
        print(f"  {judge:<35} {agreements:>8} {total:>8} {percentage:>7.1f}%")


def print_inter_judge_agreement(
    stats: Dict[Tuple[str, str], Tuple[int, int, float]],
    judge_columns: List[str],
) -> None:
    """Print inter-judge agreement matrix."""
    print(f"\n{'=' * 80}")
    print("  Inter-Judge Agreement Matrix (%)")
    print("=" * 80)

    if not stats or not judge_columns:
        print("  No data available")
        return

    # Shorten judge names for display
    short_names = []
    for j in judge_columns:
        # Take first 12 chars
        short = j[:12]
        short_names.append(short)

    # Print header row
    col_width = 13
    header = "  " + " " * 14
    for short in short_names:
        header += f"{short:>{col_width}}"
    print(header)

    print("  " + "-" * (14 + col_width * len(judge_columns)))

    # Print each row
    for i, judge_a in enumerate(judge_columns):
        row = f"  {short_names[i]:<14}"
        for judge_b in judge_columns:
            _, _, percentage = stats.get((judge_a, judge_b), (0, 0, 0.0))
            row += f"{percentage:>{col_width}.1f}"
        print(row)

    print()

    # Also print as a simple list for clarity
    print("  Pairwise Agreement Details:")
    print(f"  {'-' * 50}")
    
    printed = set()
    for i, judge_a in enumerate(judge_columns):
        for j, judge_b in enumerate(judge_columns):
            if i < j:  # Only print each pair once
                key = (judge_a, judge_b)
                if key not in printed:
                    agreements, total, percentage = stats.get(key, (0, 0, 0.0))
                    print(f"  {judge_a[:20]} <-> {judge_b[:20]}: {percentage:.1f}% ({agreements}/{total})")
                    printed.add(key)


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge Statistics")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help="Path to judge results CSV",
    )
    args = parser.parse_args()

    # Load results
    results = load_results(args.input)
    if not results:
        print("❌ No results to analyze")
        return

    judge_columns = get_judge_columns(results)

    print(f"📊 Analyzing {len(results)} comparisons")
    print(f"🧑‍⚖️ Judge models: {', '.join(judge_columns)}")

    # 1. Human ELO rankings
    human_elo = compute_elo_rankings(results, "human_winner")
    print_elo_ranking("SVG Model Rankings by Human ELO", human_elo)

    # 2. Consensus ELO rankings
    consensus_elo = compute_consensus_elo(results, judge_columns)
    print_elo_ranking("SVG Model Rankings by Judge Consensus ELO", consensus_elo)

    # 3. Agreement statistics with human
    agreement_stats = compute_agreement_stats(results, judge_columns)
    print_agreement_stats(agreement_stats)

    # 4. Inter-judge agreement
    inter_judge_stats = compute_inter_judge_agreement(results, judge_columns)
    print_inter_judge_agreement(inter_judge_stats, judge_columns)

    print()


if __name__ == "__main__":
    main()

