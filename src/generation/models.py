import os
from threading import RLock
from typing import Literal

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from langchain_groq import ChatGroq


Provider = Literal["Gemini", "Mistral", "Groq"]


class CreateModels:

    def __init__(self):
        load_dotenv()

        # Cache initialized clients instead of recreating them per request.
        self._models = {}
        self._lock = RLock()

    @staticmethod
    def _get_api_key(env_name: str) -> str:
        api_key = os.getenv(env_name)

        if not api_key:
            raise ValueError(
                f"{env_name} is missing from environment variables."
            )

        return api_key

    def get_model(self, provider: Provider):

        with self._lock:

            if provider in self._models:
                return self._models[provider]

            if provider == "Gemini":

                api_key = self._get_api_key("GOOGLE_API_KEY")

                model = ChatGoogleGenerativeAI(
                    model=os.getenv(
                        "GEMINI_MODEL",
                        "gemini-3.8-flash"
                    ),
                    api_key=api_key,
                    temperature=0.2,
                    max_output_tokens=2048,
                    timeout=60,
                    max_retries=2
                )

            elif provider == "Mistral":

                api_key = self._get_api_key("MISTRAL_API_KEY")

                model = ChatMistralAI(
                    model=os.getenv(
                        "MISTRAL_MODEL",
                        "mistral-small-latest"
                    ),
                    api_key=api_key,
                    temperature=0.2,
                    max_tokens=2048,
                    timeout=60,
                    max_retries=2
                )

            elif provider == "Groq":

                model = ChatGroq(
                api_key=self._get_api_key("GROQ_API_KEY"),
                model="openai/gpt-oss-120b",
                temperature=0.2,
                max_tokens=2048,
                timeout=60,
                max_retries=2
            )

            else:
                raise ValueError(f"Unsupported model provider: {provider}")

            self._models[provider] = model

            return model