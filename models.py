import base64
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
import openai
import anthropic
from google import genai
from google.genai.types import HttpOptions
from google.oauth2.credentials import Credentials

load_dotenv() 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") 
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_BASE_URL = os.getenv("GOOGLE_BASE_URL") 
# Assert all keys are set
assert OPENAI_API_KEY, "OPENAI_API_KEY is not set"
assert OPENAI_BASE_URL, "OPENAI_BASE_URL is not set"
assert ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY is not set"
assert ANTHROPIC_BASE_URL, "ANTHROPIC_BASE_URL is not set"
assert GOOGLE_API_KEY, "GOOGLE_API_KEY is not set"
assert GOOGLE_BASE_URL, "GOOGLE_BASE_URL is not set"

def openai_response(model: str, prompt: str) -> str:
    client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.responses.create(model=model, input=prompt)
    return response.output_text

def anthropic_response(model: str, prompt: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)
    response = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096
    )
    return response.content[0].text

def google_response(model: str, prompt: str) -> str:
    credentials = Credentials(GOOGLE_API_KEY)

    client = genai.Client(
        http_options=HttpOptions(
            api_version="v1",
            base_url=GOOGLE_BASE_URL,
        ),
        vertexai=True,
        project="aigateway",
        location="global",
        credentials=credentials,
    )

    response = client.models.generate_content(model=model, contents=prompt)
    return response.text


def get_response(model: str, prompt: str) -> str:
    if model.startswith("openai/"):
        return openai_response(model.replace("openai/", ""), prompt)
    elif model.startswith("anthropic/"):
        return anthropic_response(model.replace("anthropic/", ""), prompt)
    elif model.startswith("google/"):
        return google_response(model.replace("google/", ""), prompt)
    else:
        raise ValueError(f"Unsupported model: {model}")


# --- Vision Judge Functions ---

JUDGE_SYSTEM_PROMPT = """You are an expert image quality judge. You will be shown two images (Image A and Image B) that were generated from the same text prompt.

Your task is to evaluate which image better matches the prompt and has higher overall quality. Consider:
1. Fidelity to the prompt - how well does the image match what was requested?
2. Visual quality - is the image clear, well-composed, and aesthetically pleasing?
3. Completeness - does the image include all requested elements?

You must choose either "a" or "b" as the winner. No ties allowed."""


def _load_image_as_base64(image_path: Path) -> str:
    """Load an image file and return its base64 encoding."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_judge_prompt(prompt: str) -> str:
    """Build the user prompt for judging."""
    return f"""The original prompt was: "{prompt}"

Image A is shown first, Image B is shown second.

Which image better matches the prompt and has higher quality? Respond with only "a" or "b"."""


def openai_vision_judge(
    model: str, prompt: str, image_a_path: Path, image_b_path: Path
) -> Literal["a", "b"]:
    """Use OpenAI vision API to judge which image is better."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    
    image_a_b64 = _load_image_as_base64(image_a_path)
    image_b_b64 = _load_image_as_base64(image_b_path)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_judge_prompt(prompt)},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_a_b64}"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b_b64}"},
                    },
                ],
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "judge_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "winner": {"type": "string", "enum": ["a", "b"]}
                    },
                    "required": ["winner"],
                    "additionalProperties": False,
                },
            },
        },
        max_completion_tokens=50,
    )
    
    import json
    result = json.loads(response.choices[0].message.content)
    return result["winner"]


def anthropic_vision_judge(
    model: str, prompt: str, image_a_path: Path, image_b_path: Path
) -> Literal["a", "b"]:
    """Use Anthropic vision API to judge which image is better."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)
    
    image_a_b64 = _load_image_as_base64(image_a_path)
    image_b_b64 = _load_image_as_base64(image_b_path)
    
    # Use tool_choice to force structured output
    response = client.messages.create(
        model=model,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_judge_prompt(prompt)},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_a_b64,
                        },
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b_b64,
                        },
                    },
                ],
            },
        ],
        tools=[
            {
                "name": "submit_judgment",
                "description": "Submit your judgment of which image is better",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "winner": {
                            "type": "string",
                            "enum": ["a", "b"],
                            "description": "The winning image: 'a' or 'b'",
                        }
                    },
                    "required": ["winner"],
                },
            }
        ],
        tool_choice={"type": "tool", "name": "submit_judgment"},
        max_tokens=256,
    )
    
    # Extract the tool use result
    for block in response.content:
        if block.type == "tool_use":
            return block.input["winner"]
    
    raise ValueError("No tool use response from Anthropic model")


def google_vision_judge(
    model: str, prompt: str, image_a_path: Path, image_b_path: Path
) -> Literal["a", "b"]:
    """Use Google vision API to judge which image is better."""
    from google.genai.types import Part, Content
    
    credentials = Credentials(GOOGLE_API_KEY)
    client = genai.Client(
        http_options=HttpOptions(
            api_version="v1",
            base_url=GOOGLE_BASE_URL,
        ),
        vertexai=True,
        project="aigateway",
        location="global",
        credentials=credentials,
    )
    
    image_a_bytes = Path(image_a_path).read_bytes()
    image_b_bytes = Path(image_b_path).read_bytes()
    
    contents = [
        Content(
            role="user",
            parts=[
                Part.from_text(text=JUDGE_SYSTEM_PROMPT + "\n\n" + _build_judge_prompt(prompt)),
                Part.from_bytes(data=image_a_bytes, mime_type="image/png"),
                Part.from_bytes(data=image_b_bytes, mime_type="image/png"),
            ],
        )
    ]
    
    # Use response schema for structured output
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "object",
                "properties": {
                    "winner": {"type": "string", "enum": ["a", "b"]}
                },
                "required": ["winner"],
            },
        },
    )
    
    import json
    result = json.loads(response.text)
    return result["winner"]


def get_judge_response(
    model: str, prompt: str, image_a_path: Path, image_b_path: Path
) -> Literal["a", "b"]:
    """Route to the appropriate vision judge based on model prefix."""
    if model.startswith("openai/"):
        return openai_vision_judge(
            model.replace("openai/", ""), prompt, image_a_path, image_b_path
        )
    elif model.startswith("anthropic/"):
        return anthropic_vision_judge(
            model.replace("anthropic/", ""), prompt, image_a_path, image_b_path
        )
    elif model.startswith("google/"):
        return google_vision_judge(
            model.replace("google/", ""), prompt, image_a_path, image_b_path
        )
    else:
        raise ValueError(f"Unsupported model: {model}")