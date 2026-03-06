"""
llm_client.py — Groq LLM client.
Model is configured via GROQ_MODEL in .env (default: llama-3.3-70b-versatile).
"""
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client() -> Groq:
    """Return a lazily-initialised Groq client."""
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    return _client


def get_model() -> str:
    """Return the configured Groq model name."""
    return os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
