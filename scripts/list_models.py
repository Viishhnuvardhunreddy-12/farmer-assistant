"""List the Gemini models your GEMINI_API_KEY can use, to pick GEMINI_MODEL."""

import _bootstrap  # noqa: F401
from google import genai

from app.config import get_settings


def main() -> None:
    s = get_settings()
    client = genai.Client(api_key=s.gemini_api_key or None)
    for model in client.models.list():
        if "generateContent" in (model.supported_actions or []):
            marker = "  <- current GEMINI_MODEL" if model.name == f"models/{s.gemini_model}" else ""
            print(f"{model.name.removeprefix('models/')}{marker}")


if __name__ == "__main__":
    main()
