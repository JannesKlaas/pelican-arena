import os
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
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def anthropic_response(model: str, prompt: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)
    response = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096*4
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