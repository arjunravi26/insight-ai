from src.generation.models import CreateModels, Provider
from src.generation.generate import Generate
from src.retrieval.retrive import Retriever
from src.retrieval.reranker import CrossEncoderReranker
import logging

logger = logging.getLogger(__name__)


class GenerationService:

    def __init__(self, config):
        self.model_factory = CreateModels()
        self.retriever = Retriever(config=config)
        self.reranker = CrossEncoderReranker(config=config)
        self.rag_generator = Generate(self.model_factory)

    def generate_response(self, provider: Provider, query: str, document_id: str, user_id: int) -> dict:
        try:
            retrieved_chunks = self.retriever.search_chunks(
                query=query, document_id=document_id, user_id=user_id)
            logger.info(f"Retrieved chunks: {len(retrieved_chunks)}")
            reranked_chunk = self.reranker.rerank(
                documents=retrieved_chunks, query=query)
            logger.info(f"Re ranked chunks: {len(reranked_chunk)}")
            logger.info(f"Re Ranked chunks are: {retrieved_chunks}")
            answer, follow_ups = self.rag_generator.generate(
                query=query, retrieved_chunks=reranked_chunk, provider=provider)
            return answer, follow_ups
        except Exception as e:
            logger.exception(f"Failed to generate response. {e}")
            raise
