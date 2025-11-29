#!/usr/bin/env python3
"""
Generate SVG + PNG images for every model defined in models_config.yaml.

Usage:
    uv run comp.py "A pelican riding a bicycle"
"""

from __future__ import annotations

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
OUTPUTS_DIR = ROOT / "outputs"

DEFAULT_CONFIG = {
    "models": [
        "openai/gpt-4o",
        "openai/gpt-4.1-mini",
        "openai/o4-mini",
        "anthropic/claude-3-5-sonnet-20241022",
        "anthropic/claude-3-5-haiku-20241022",
        "anthropic/claude-3-opus-20240229",
        "google/gemini-1.5-pro",
        "google/gemini-1.5-flash",
    ],
    "settings": {
        "max_workers": 4,
        "save_html": True,
    },
}


def load_config() -> Dict[str, Any]:
    """Load the YAML config, creating a default one if missing."""
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False), encoding="utf-8"
        )
        print(f"📝 Created default config at {CONFIG_PATH}. Edit it to add/remove models.")

    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    return config


def sanitize_model_name(model: str) -> str:
    """Convert provider/model notation into filesystem-friendly name."""
    name = model.split("/", 1)[-1] if "/" in model else model
    safe = "".join(ch if ch.isalnum() or ch in "-._" else "-" for ch in name)
    return safe.strip("-") or "model"


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
    model_display = model
    model_slug = sanitize_model_name(model)
    svg_path = output_dir / f"{model_slug}.svg"
    png_path = output_dir / f"{model_slug}.png"

    try:
        print(f"🤖 Generating with {model_display}...")
        response = get_response(model, build_svg_prompt(prompt))
        svg_code = extract_svg(response)
        svg_code = ensure_svg_wrapper(svg_code)

        svg_path.write_text(svg_code, encoding="utf-8")
        cairosvg.svg2png(bytestring=svg_code.encode("utf-8"), write_to=str(png_path))

        print(f"✅ {model_display} completed")
        return {
            "model": model_display,
            "status": "success",
            "files": {"svg": svg_path.name, "png": png_path.name},
        }
    except Exception as exc:  # pylint: disable=broad-except
        print(f"❌ {model_display} failed: {exc}")
        return {"model": model_display, "status": "error", "error": str(exc)}


def generate_html_viewer(
    output_dir: Path, results: List[Dict[str, Any]], prompt: str, run_id: str
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
                <a href="{model_slug}.png" download>Download PNG</a>
                <a href="{model_slug}.svg" download>Download SVG</a>
            </div>
        </div>
        """
            )
        else:
            rows.append(
                f"""
        <div class="model error">
            <h3>{model_name}</h3>
            <p>Error: {result.get("error", "Unknown error")}</p>
        </div>
        """
            )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Model Comparison: {prompt[:80]}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .metadata {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }}
        .model {{
            background: white;
            border: 1px solid #ddd;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .model h3 {{
            margin: 0 0 10px 0;
            color: #555;
            font-size: 14px;
            font-family: monospace;
        }}
        .model img {{
            width: 100%;
            height: auto;
            border: 1px solid #eee;
            border-radius: 4px;
        }}
        .error {{
            background: #fee;
            border-color: #fcc;
        }}
        .error p {{
            color: #c00;
            font-size: 14px;
        }}
        .download-links {{
            margin-top: 10px;
            font-size: 12px;
        }}
        .download-links a {{
            margin-right: 10px;
            color: #4CAF50;
            text-decoration: none;
        }}
        .download-links a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <h1>Image Generation Comparison</h1>
    <div class="metadata">
        <strong>Prompt:</strong> {prompt}<br>
        <strong>Run ID:</strong> <code>{run_id}</code><br>
        <strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </div>
    <div class="grid">
        {''.join(rows)}
    </div>
</body>
</html>
"""

    (output_dir / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        print('Usage: uv run comp.py "your prompt"')
        sys.exit(1)

    prompt = sys.argv[1]
    config = load_config()
    models: List[str] = config.get("models", []) or []
    settings = config.get("settings", {}) or {}
    configured_workers = int(settings.get("max_workers", max(1, len(models))))
    max_workers = max(1, configured_workers)
    save_html = bool(settings.get("save_html", True))

    if not models:
        print("❌ No models configured in models_config.yaml")
        sys.exit(1)

    run_id = str(uuid.uuid4())
    output_dir = OUTPUTS_DIR / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    print(f"📋 Loaded {len(models)} models from config")
    print(f"🚀 Starting generation with up to {max_workers} parallel workers...")

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(generate_image, model, prompt, output_dir): model
            for model in models
        }
        for future in as_completed(future_map):
            results.append(future.result())

    summary = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "models": results,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    if save_html:
        generate_html_viewer(output_dir, results, prompt, run_id)

    successes = sum(1 for item in results if item["status"] == "success")
    failures = len(results) - successes

    print("\n📊 Results:")
    print(f"  ✅ Successful: {successes}/{len(results)}")
    if failures:
        print(f"  ❌ Failed: {failures}")
        for result in results:
            if result["status"] == "error":
                print(f"     - {result['model']}: {result.get('error', 'Unknown error')}")
    print(f"  📁 Output: {output_dir}")
    if save_html:
        print(f"  🌐 Viewer: {output_dir / 'index.html'}")


if __name__ == "__main__":
    main()

