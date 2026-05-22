"""
Quick Azure OpenAI GPT-4o connectivity test.
Reads config from .env in project root.
"""
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

if not all([endpoint, api_key, deployment]):
    raise RuntimeError("Missing one or more required Azure OpenAI env vars.")

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version=api_version,
)

try:
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Say hello and tell me the current year."},
        ],
        temperature=0.1,
        max_tokens=32,
    )
    print("SUCCESS! GPT-4o responded:")
    print(response.choices[0].message.content)
except Exception as e:
    print("FAILED to call Azure OpenAI:")
    print(e)
