from src.generation.models import CreateModels, Provider
from src.generation.generate import Generate
from src.retrieval.retrive import Retriever
import logging

logger = logging.getLogger(__name__)


class GenerationService:

    def __init__(self, config):
        self.model_factory = CreateModels()
        self.retriever = Retriever(config=config)
        self.rag_generator = Generate(self.model_factory)

    def generate_response(self, provider: Provider, query: str, document_id: str, user_id: int) -> dict:
        try:
            retrieved_chunks = self.retriever.search_chunks(
                query=query, document_id=document_id, user_id=user_id)
            answer, follow_ups = self.rag_generator.generate(
                query=query, retrieved_chunks=retrieved_chunks, provider=provider)
            return answer, follow_ups
        except Exception as e:
            logger.exception(f"Failed to generate response. {e}")
            raise
