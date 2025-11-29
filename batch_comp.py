#!/usr/bin/env python3
"""
Run image generation comparison for all prompts in a CSV file.

Usage:
    uv run batch_comp.py prompts.csv
    uv run batch_comp.py prompts.csv --output-dir batch_outputs
"""

from __future__ import annotations

import csv
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import cairosvg
import yaml

from genimg import extract_svg
from models import get_response

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "models_config.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "batch_outputs"


def load_config() -> Dict[str, Any]:
    """Load the YAML config."""
    if not CONFIG_PATH.exists():
        print(f"❌ Config file not found: {CONFIG_PATH}")
        sys.exit(1)

    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def sanitize_model_name(model: str) -> str:
    """Convert provider/model notation into filesystem-friendly name."""
    name = model.split("/", 1)[-1] if "/" in model else model
    safe = "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in name)
    return safe.strip("-") or "model"


def sanitize_prompt_name(prompt: str, max_len: int = 50) -> str:
    """Create a filesystem-friendly name from a prompt."""
    # Take first N chars and sanitize
    short = prompt[:max_len].strip()
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in short)
    safe = safe.strip().replace(" ", "_")
    return safe[:max_len] or "prompt"


def build_svg_prompt(prompt: str) -> str:
    """Return the canonical SVG generation instructions."""
    return f"""Generate SVG code for: {prompt}

Requirements:
- Return only valid SVG code
- Use a viewBox of "0 0 500 500"
- Keep it simple and clean
- Include colors

Return ONLY the SVG code, nothing else."""


def ensure_svg_wrapper(svg_code: str) -> str:
    """Wrap non-SVG snippets in a minimal SVG root element."""
    snippet = svg_code.strip()
    if snippet.lower().startswith("<svg"):
        return snippet

    return (
        '<svg viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">\n'
        f"{snippet}\n"
        "</svg>"
    )


def generate_image(model: str, prompt: str, output_dir: Path) -> Dict[str, Any]:
    """Generate SVG + PNG for a single model."""
    model_slug = sanitize_model_name(model)
    svg_path = output_dir / f"{model_slug}.svg"
    png_path = output_dir / f"{model_slug}.png"

    try:
        response = get_response(model, build_svg_prompt(prompt))
        svg_code = extract_svg(response)
        svg_code = ensure_svg_wrapper(svg_code)

        svg_path.write_text(svg_code, encoding="utf-8")
        cairosvg.svg2png(bytestring=svg_code.encode("utf-8"), write_to=str(png_path))

        return {
            "model": model,
            "status": "success",
            "files": {"svg": svg_path.name, "png": png_path.name},
        }
    except Exception as exc:
        return {"model": model, "status": "error", "error": str(exc)}


def generate_html_viewer(
    output_dir: Path, results: List[Dict[str, Any]], prompt: str, difficulty: str
) -> None:
    """Create an HTML file that shows all model outputs."""
    rows = []
    for result in sorted(results, key=lambda item: item["model"]):
        model_name = result["model"]
        model_slug = sanitize_model_name(model_name)
        if result["status"] == "success":
            rows.append(
                f"""
        <div class="model">
            <h3>{model_name}</h3>
            <img src="{model_slug}.png" alt="{model_name}">
            <div class="download-links">
                <a href="{model_slug}.png" download>PNG</a>
                <a href="{model_slug}.svg" download>SVG</a>
            </div>
        </div>"""
            )
        else:
            rows.append(
                f"""
        <div class="model error">
            <h3>{model_name}</h3>
            <p>Error: {result.get("error", "Unknown")[:100]}</p>
        </div>"""
            )

    difficulty_colors = {
        "easy": "#4CAF50",
        "medium": "#FF9800",
        "hard": "#f44336",
    }
    accent = difficulty_colors.get(difficulty.lower(), "#4CAF50")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{difficulty.upper()}: {prompt[:60]}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 20px;
            background: #1a1a1a;
            color: #eee;
        }}
        h1 {{
            color: #fff;
            border-bottom: 3px solid {accent};
            padding-bottom: 10px;
        }}
        .difficulty {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            background: {accent};
            color: white;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 12px;
            margin-bottom: 10px;
        }}
        .metadata {{
            background: #2a2a2a;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #333;
        }}
        .prompt-text {{
            font-style: italic;
            color: #bbb;
            margin: 10px 0;
            line-height: 1.5;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        .model {{
            background: #2a2a2a;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 8px;
        }}
        .model h3 {{
            margin: 0 0 10px 0;
            color: #aaa;
            font-size: 12px;
            font-family: monospace;
        }}
        .model img {{
            width: 100%;
            height: auto;
            border: 1px solid #444;
            border-radius: 4px;
            background: white;
        }}
        .error {{
            background: #3a2020;
            border-color: #5a3030;
        }}
        .error p {{
            color: #f88;
            font-size: 12px;
        }}
        .download-links {{
            margin-top: 10px;
            font-size: 11px;
        }}
        .download-links a {{
            margin-right: 10px;
            color: {accent};
            text-decoration: none;
        }}
        .download-links a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <span class="difficulty">{difficulty}</span>
    <h1>Model Comparison</h1>
    <div class="metadata">
        <div class="prompt-text">{prompt}</div>
    </div>
    <div class="grid">
        {''.join(rows)}
    </div>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def run_comparison(
    prompt: str,
    difficulty: str,
    prompt_idx: int,
    models: List[str],
    max_workers: int,
    output_base: Path,
) -> Dict[str, Any]:
    """Run comparison for a single prompt."""
    # Create folder name: idx_difficulty_prompt-snippet
    folder_name = f"{prompt_idx:03d}_{difficulty}_{sanitize_prompt_name(prompt, 40)}"
    output_dir = output_base / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save prompt
    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    # Generate images in parallel
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(generate_image, model, prompt, output_dir): model
            for model in models
        }
        for future in as_completed(future_map):
            results.append(future.result())

    # Save summary
    summary = {
        "prompt_idx": prompt_idx,
        "difficulty": difficulty,
        "prompt": prompt,
        "timestamp": datetime.now().isoformat(),
        "models": results,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # Generate HTML viewer
    generate_html_viewer(output_dir, results, prompt, difficulty)

    successes = sum(1 for r in results if r["status"] == "success")
    return {
        "prompt_idx": prompt_idx,
        "difficulty": difficulty,
        "folder": folder_name,
        "successes": successes,
        "failures": len(results) - successes,
    }


def generate_index_html(output_base: Path, all_results: List[Dict], prompts_data: List[Dict]) -> None:
    """Generate a master index.html linking to all prompt comparisons."""
    
    # Group by difficulty
    by_difficulty = {"easy": [], "medium": [], "hard": []}
    for result, prompt_data in zip(all_results, prompts_data):
        diff = result["difficulty"].lower()
        if diff in by_difficulty:
            by_difficulty[diff].append((result, prompt_data))
    
    sections = []
    for difficulty in ["easy", "medium", "hard"]:
        items = by_difficulty.get(difficulty, [])
        if not items:
            continue
            
        colors = {"easy": "#4CAF50", "medium": "#FF9800", "hard": "#f44336"}
        color = colors[difficulty]
        
        cards = []
        for result, prompt_data in items:
            status = "✅" if result["failures"] == 0 else f"⚠️ {result['failures']} failed"
            cards.append(f"""
            <a href="{result['folder']}/index.html" class="card">
                <div class="card-header">{result['prompt_idx']:03d}</div>
                <div class="card-prompt">{prompt_data['prompt'][:80]}{'...' if len(prompt_data['prompt']) > 80 else ''}</div>
                <div class="card-status">{status}</div>
            </a>""")
        
        sections.append(f"""
        <div class="section">
            <h2 style="border-color: {color};">{difficulty.upper()} ({len(items)})</h2>
            <div class="cards">
                {''.join(cards)}
            </div>
        </div>""")
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Batch Comparison Results</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 20px;
            background: #1a1a1a;
            color: #eee;
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            color: #fff;
            border-bottom: 3px solid #666;
            padding-bottom: 15px;
        }}
        h2 {{
            color: #fff;
            border-left: 4px solid;
            padding-left: 12px;
            margin-top: 30px;
        }}
        .stats {{
            background: #2a2a2a;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            gap: 30px;
        }}
        .stat {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: bold;
        }}
        .stat-label {{
            font-size: 12px;
            color: #888;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
        }}
        .card {{
            background: #2a2a2a;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 8px;
            text-decoration: none;
            color: inherit;
            transition: border-color 0.2s, transform 0.2s;
        }}
        .card:hover {{
            border-color: #555;
            transform: translateY(-2px);
        }}
        .card-header {{
            font-family: monospace;
            color: #666;
            font-size: 12px;
            margin-bottom: 8px;
        }}
        .card-prompt {{
            font-size: 14px;
            line-height: 1.4;
            color: #ccc;
            margin-bottom: 10px;
        }}
        .card-status {{
            font-size: 12px;
            color: #888;
        }}
    </style>
</head>
<body>
    <h1>Batch Comparison Results</h1>
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(all_results)}</div>
            <div class="stat-label">Total Prompts</div>
        </div>
        <div class="stat">
            <div class="stat-value">{len(by_difficulty.get('easy', []))}</div>
            <div class="stat-label">Easy</div>
        </div>
        <div class="stat">
            <div class="stat-value">{len(by_difficulty.get('medium', []))}</div>
            <div class="stat-label">Medium</div>
        </div>
        <div class="stat">
            <div class="stat-value">{len(by_difficulty.get('hard', []))}</div>
            <div class="stat-label">Hard</div>
        </div>
    </div>
    {''.join(sections)}
</body>
</html>
"""
    (output_base / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run batch_comp.py prompts.csv [--output-dir DIR]")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        sys.exit(1)

    # Parse optional output dir
    output_base = DEFAULT_OUTPUT_DIR
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            output_base = Path(sys.argv[idx + 1])

    # Load config
    config = load_config()
    models: List[str] = config.get("models", []) or []
    settings = config.get("settings", {}) or {}
    max_workers = max(1, int(settings.get("max_workers", 4)))

    if not models:
        print("❌ No models configured in models_config.yaml")
        sys.exit(1)

    # Load prompts from CSV
    prompts_data: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "prompt" in row:
                prompts_data.append({
                    "prompt": row["prompt"],
                    "difficulty": row.get("difficulty", "unknown"),
                })

    if not prompts_data:
        print("❌ No prompts found in CSV")
        sys.exit(1)

    # Create output directory with timestamp
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = output_base / run_id
    output_base.mkdir(parents=True, exist_ok=True)

    print(f"📋 Loaded {len(prompts_data)} prompts from {csv_path}")
    print(f"🤖 Using {len(models)} models: {', '.join(models)}")
    print(f"📁 Output directory: {output_base}")
    print(f"🚀 Starting batch generation...\n")

    all_results = []
    total = len(prompts_data)

    for idx, prompt_data in enumerate(prompts_data, 1):
        prompt = prompt_data["prompt"]
        difficulty = prompt_data["difficulty"]
        
        print(f"[{idx}/{total}] {difficulty.upper()}: {prompt[:60]}...")
        
        result = run_comparison(
            prompt=prompt,
            difficulty=difficulty,
            prompt_idx=idx,
            models=models,
            max_workers=max_workers,
            output_base=output_base,
        )
        all_results.append(result)
        
        status = "✅" if result["failures"] == 0 else f"⚠️ {result['failures']} failed"
        print(f"    {status} → {result['folder']}\n")

    # Generate master index
    generate_index_html(output_base, all_results, prompts_data)

    # Summary
    total_successes = sum(r["successes"] for r in all_results)
    total_failures = sum(r["failures"] for r in all_results)
    
    print("\n" + "=" * 60)
    print("📊 BATCH COMPLETE")
    print("=" * 60)
    print(f"  Prompts processed: {len(all_results)}")
    print(f"  Total images: {total_successes + total_failures}")
    print(f"  ✅ Successful: {total_successes}")
    if total_failures:
        print(f"  ❌ Failed: {total_failures}")
    print(f"\n  📁 Output: {output_base}")
    print(f"  🌐 Index: {output_base / 'index.html'}")


if __name__ == "__main__":
    main()

