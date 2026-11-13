import json
import re
import logging

from typing import Sequence

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.generation.models import CreateModels, Provider
from src.generation.prompt import Prompt

logger = logging.getLogger(__name__)


class Generate:

    def __init__(self, model_factory: CreateModels):

        self.model_factory = model_factory
        self.prompt_generator = Prompt()

    def generate(
        self,
        query: str,
        retrieved_chunks: Sequence,
        provider: Provider
    ) -> tuple[str, list[str]]:

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        context, sources = self.prompt_generator.generate_prompt(
            query=query, retrieved_chunks=retrieved_chunks)

        if not context:
            return (
                "I couldn't find relevant information in the uploaded documents to answer your question.",
                [
                    "Can you rephrase your question?",
                    "Would you like to upload another document?"
                ],
            )

        try:
            llm = self.model_factory.get_model(provider)

            chain = self.prompt_generator.template | llm | StrOutputParser()

            raw_response = chain.invoke({
                "context": context,
                "question": query.strip()
            })

            answer, follow_ups = self._parse_response(raw_response)

            answer = self._append_sources(answer, sources)

            return answer, follow_ups

        except Exception:
            logger.exception(
                "Generation failed using provider %s",
                provider
            )
            raise

    @staticmethod
    def _parse_response(raw_response: str):

        try:
            cleaned = raw_response.strip()

            cleaned = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                cleaned,
                flags=re.IGNORECASE
            )

            # Extract JSON if the provider adds surrounding text.
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

            if not match:
                raise ValueError("No JSON object found.")

            data = json.loads(match.group())

            answer = str(data.get("answer", "")).strip()

            follow_ups = data.get("follow_ups", [])

            if not isinstance(follow_ups, list):
                follow_ups = []

            follow_ups = [
                str(item).strip()
                for item in follow_ups
                if isinstance(item, str) and item.strip()
            ][:3]

            if not answer:
                raise ValueError("Generated answer is empty.")

            return answer, follow_ups

        except (ValueError, json.JSONDecodeError, TypeError):
            logger.warning(
                "Could not parse structured LLM response. "
                "Returning raw response."
            )

            return raw_response.strip(), []

    @staticmethod
    def _append_sources(answer: str, sources: list[dict]) -> str:

        if not sources:
            return answer

        source_lines = ["\n\n**Sources:**"]

        for source in sources:
            filename = source["filename"]
            page = source["page_number"]

            if page is not None:
                source_lines.append(
                    f"- [{source['id']}] {filename}, page {page}"
                )
            else:
                source_lines.append(
                    f"- [{source['id']}] {filename}"
                )

        return answer + "\n".join(source_lines)
