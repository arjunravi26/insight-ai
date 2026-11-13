from sentence_transformers import CrossEncoder
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class CrossEncoderReranker:

    def __init__(
        self,
        config: Dict
    ):
        self.config = config
        self.model = CrossEncoder(
            config["reranker_model_name"],
            device="cpu",
            max_length=config["embedding_model_limit"]
        )

        self.batch_size = config["reranker_batch_size"]

    def rerank(
        self,
        query: str,
        documents: list,
    ) -> list:

        if not documents:
            return []

        pairs = []

        for document in documents:

            text = document.get(
                "text",
                document.get("page_content", "")
            )

            pairs.append((query, text))

        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False
        )

        ranked_documents = sorted(
            zip(documents, scores),
            key=lambda item: float(item[1]),
            reverse=True
        )

        results = []

        for document, score in ranked_documents[:self.config["rerank_k"]]:

            result = dict(document)
            result["rerank_score"] = float(score)

            results.append(result)

        return results