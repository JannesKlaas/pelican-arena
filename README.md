# LLM SVG to PNG Generator

A simple Python script that uses LiteLLM to generate SVG code from a text prompt and converts it to a PNG image.

## Installation

Install uv if you haven't already:

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

Then sync the project dependencies:

```bash
uv sync
```

Create an outputs directory (optional):

```bash
mkdir -p outputs
```

## Usage

### Single-model preview

```bash
uv run python genimg.py <model> <output_path> <prompt>
```

Examples:

```bash
uv run python genimg.py openai/gpt-4 outputs/pelican.png "generate an image of a pelican"
uv run python genimg.py anthropic/claude-3-haiku-20240307 outputs/bird.png "draw a colorful bird"
uv run python genimg.py ollama/llama2 outputs/cat.png "create a simple cat illustration"
```

### Multi-model comparison

1. Edit `models_config.yaml` and list every model you want to test.
2. Tweak optional settings such as `max_workers` (parallelism) and `save_html`.
3. Run a single prompt against every configured model:

```bash
uv run comp.py "a pelican riding a bicycle"
```

Each run gets its own folder under `outputs/<uuid>/` containing:
- `prompt.txt`
- `summary.json`
- `<model>.svg` and `<model>.png` pairs
- `index.html` gallery (when enabled)

## Quick Start

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup the project
uv sync

# Configure the models you want to compare
$EDITOR models_config.yaml

# Set your API key(s)
export OPENAI_API_KEY="your-key-here"

# Generate your first comparison run
uv run comp.py "a colorful pelican by the beach"
```

## Environment Variables

Make sure to set your API keys:

```bash
# For OpenAI
export OPENAI_API_KEY="your-key-here"

# For Anthropic
export ANTHROPIC_API_KEY="your-key-here"

# For other providers, check LiteLLM documentation
```

## How it Works

1. Takes a text prompt and sends it to the specified LLM
2. The LLM generates SVG code based on the prompt
3. **Robust SVG extraction** that handles:
   - SVG in code blocks (with or without language tags)
   - Raw SVG mixed with explanatory text
   - Partial SVG elements without wrapper tags
   - Text before/after the actual SVG code
4. The SVG is converted to PNG using cairosvg
5. The PNG is saved to the specified output path for single runs, or automatically
   organized under `outputs/<run_uuid>/` for comparison runs

## Advanced Features

### Debug Mode
Save both PNG and SVG files for debugging:
```bash
uv run python genimg.py openai/gpt-4 output.png "your prompt" --save-svg
```

### Robust SVG Extraction
The script can handle various LLM response formats:
- ✅ SVG wrapped in \`\`\`svg\`\`\` code blocks
- ✅ Raw SVG with explanatory text before/after
- ✅ Partial SVG elements (automatically wraps them)
- ✅ Mixed content with multiple formats
- ✅ Automatic cleanup of malformed responses
