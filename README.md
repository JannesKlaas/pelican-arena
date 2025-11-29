# LLM SVG to PNG Generator

A simple Python script that uses LiteLLM to generate SVG code from a text prompt and converts it to a PNG image.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python genimg.py <model> <output_path> <prompt>
```

### Examples

```bash
# Using OpenAI GPT-4
python genimg.py openai/gpt-4 outputs/pelican.png "generate an image of a pelican"

# Using Claude
python genimg.py anthropic/claude-3-haiku-20240307 outputs/bird.png "draw a colorful bird"

# Using local models via Ollama
python genimg.py ollama/llama2 outputs/cat.png "create a simple cat illustration"
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
3. The SVG is converted to PNG using cairosvg
4. The PNG is saved to the specified output path
