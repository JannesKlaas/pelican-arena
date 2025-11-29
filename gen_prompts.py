#!/usr/bin/env python3
"""
Generate image prompts using an LLM at three difficulty levels.

Usage:
    uv run gen_prompts.py
    uv run gen_prompts.py --output prompts.csv
"""

import csv
import json
import re
import sys
from pathlib import Path

from models import get_response

MODEL = "openai/gpt-5-2025-08-07"
DEFAULT_OUTPUT = "prompts.csv"

SYSTEM_PROMPTS = {
    "easy": """Generate exactly 10 EASY image prompts for SVG generation.

Easy prompts should be simple, fun, whimsical concepts that are straightforward to draw.
Examples:
- "a pelican riding a bicycle"
- "a cat wearing a top hat"
- "a smiling sun with sunglasses"
- "a penguin holding an umbrella"

Requirements:
- Each prompt should be a single, clear concept
- Keep them short (under 15 words)
- Make them playful and fun
- No complex details or technical requirements

Return ONLY a JSON array of 10 strings, nothing else. Example format:
["prompt 1", "prompt 2", "prompt 3", ...]""",

    "medium": """Generate exactly 10 MEDIUM difficulty image prompts for SVG generation.

Medium prompts should be detailed and specific, requiring attention to multiple elements.
Example:
"Generate an SVG of a California brown pelican riding a bicycle. The bicycle must have spokes and a correctly shaped bicycle frame. The pelican must have its characteristic large pouch, and there should be a clear indication of feathers. The pelican must be clearly pedaling the bicycle. The image should show the full breeding plumage of the California brown pelican."

Requirements:
- Each prompt should specify multiple visual details
- Include specific characteristics that must be present
- Require understanding of the subject matter
- Should be 40-80 words each
- Include requirements for anatomy, positioning, or technical accuracy

Return ONLY a JSON array of 10 strings, nothing else. Example format:
["prompt 1", "prompt 2", "prompt 3", ...]""",

    "hard": """Generate exactly 10 HARD difficulty image prompts for SVG generation.

Hard prompts should be extremely challenging, requiring:
- Deep understanding of realism and accurate proportions
- Complex compositions with multiple interacting elements
- Technical precision in depicting machinery, architecture, or anatomy
- Artistic insight and creative problem-solving
- Understanding of lighting, perspective, and depth
- Cultural or historical accuracy where applicable

Examples of hard concepts:
A sprawling, impossibly detailed waiting room where beings from across the multiverse have gathered to renew their existence permits.
In the foreground, a sentient filing cabinet wearing a tiny necktie is explaining to a visibly frustrated cloud of bees (wearing a single collective trench coat) that form 27-B/stroke/6 must be completed in triplicate across three separate timelines.
Behind them, the queue includes: a very formal skeleton in a powdered wig reading a newspaper called "The Eternal Times," a stack of increasingly smaller wizard hats (each with its own tiny impatient face), a photorealistic horse but only from the neck up emerging from a business suit, and a grandmother who is clearly three raccoons standing on each other's shoulders but everyone is too polite to mention it.
The clerk windows are manned by: an enormous eye with reading glasses, a potted fern that communicates through passive-aggressive sticky notes, and an empty chair with a "Back in 5 Minutes" sign that has clearly been there since the Cretaceous period (evidenced by the fossilized coffee cup).
On the walls: motivational posters featuring a thumbs-up but the thumb has a tiny screaming face, a clock where all the numbers have been replaced with the word "EVENTUALLY," and a fire exit sign pointing into a swirling void.
The floor tiles alternate between existential dread beige and bureaucratic purgatory gray, with one mysteriously wet spot that everyone is carefully stepping around.

Requirements:
- Each prompt should be 80-150 words
- Specify exact details about proportions, materials, and techniques
- Include requirements that test understanding of the subject
- Push the limits of what SVG can represent
- Require wit and insight to interpret correctly

Return ONLY a JSON array of 10 strings, nothing else. Example format:
["prompt 1", "prompt 2", "prompt 3", ...]""",
}


def extract_json_array(text: str) -> list:
    """Extract a JSON array from LLM response, handling various formats."""
    # Try to find JSON array in the text
    # First, try direct parse
    text = text.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    
    # Try to find array in code blocks
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Try to find array anywhere in text
    array_match = re.search(r'\[.*\]', text, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Could not extract JSON array from response: {text[:200]}...")


def generate_prompts(difficulty: str) -> list:
    """Generate prompts for a given difficulty level."""
    print(f"🤖 Generating {difficulty.upper()} prompts...")
    
    response = get_response(MODEL, SYSTEM_PROMPTS[difficulty])
    prompts = extract_json_array(response)
    
    if len(prompts) != 10:
        print(f"⚠️  Warning: Expected 10 prompts, got {len(prompts)}")
    
    print(f"✅ Generated {len(prompts)} {difficulty} prompts")
    return prompts


def main():
    output_file = DEFAULT_OUTPUT
    
    # Simple arg parsing
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        output_file = sys.argv[1]
    
    print(f"📝 Generating prompts using {MODEL}")
    print(f"📁 Output file: {output_file}\n")
    
    all_prompts = []
    
    for difficulty in ["easy", "medium", "hard"]:
        try:
            prompts = generate_prompts(difficulty)
            for prompt in prompts:
                all_prompts.append({"prompt": prompt, "difficulty": difficulty})
        except Exception as e:
            print(f"❌ Failed to generate {difficulty} prompts: {e}")
            continue
    
    # Write to CSV
    output_path = Path(output_file)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["prompt", "difficulty"])
        writer.writeheader()
        writer.writerows(all_prompts)
    
    print(f"\n📊 Summary:")
    print(f"  Total prompts: {len(all_prompts)}")
    for diff in ["easy", "medium", "hard"]:
        count = sum(1 for p in all_prompts if p["difficulty"] == diff)
        print(f"  {diff.capitalize()}: {count}")
    print(f"\n✅ Saved to {output_path}")


if __name__ == "__main__":
    main()

