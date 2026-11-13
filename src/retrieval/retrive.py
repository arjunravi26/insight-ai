import os
from typing import Optional

from pinecone import Pinecone, DenseVectorQuery
from src.embedding.embedding import EmbeddingModel


class Retriever:
    def __init__(self, config):
        self.embedding_model = EmbeddingModel()
        self.config = config
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError(
                "PINECONE_API_KEY environment variable is missing.")

        self.pc = Pinecone(api_key=api_key)
        self.index = self.pc.index(self.config["index_name"])

    def _embed_query(self, query: str):
        """Generate an embedding for a user query."""

        if hasattr(self.embedding_model, "embed_query"):
            embedding = self.embedding_model.embed_query(query)

        elif hasattr(self.embedding_model, "encode"):
            embedding = self.embedding_model.encode(
                query,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )

        else:
            raise TypeError(
                "Embedding model must expose embed_query() or encode()."
            )

        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()

        # Handle a single-item batch: [[...]].
        if embedding and isinstance(embedding[0], list):
            embedding = embedding[0]

        return [float(value) for value in embedding]

    def search_chunks(
        self,
        query: str,
        document_id: str,
        user_id: int,
        top_k: int = 5,
        filter: Optional[dict] = None,

    ):
        """
        Search Pinecone for relevant document chunks.

        Args:
            query: User's search query.
            top_k: Number of results to retrieve.
            document_id: ID of the document to search within.
            filter: Optional Pinecone metadata filter.
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        if top_k < 1:
            raise ValueError("top_k must be positive.")

        # Generate query embedding.
        query_embedding = self._embed_query(query)

        dimension = self.config.get("dimension")

        if len(query_embedding) != dimension:
            raise ValueError(
                f"Expected {dimension} query dimensions, "
                f"received {len(query_embedding)}."
            )

        # Search Pinecone.
        results = self.index.documents.search(
            namespace=self.config["namespace"],
            top_k=top_k,
            score_by=[
                DenseVectorQuery(
                    field="embedding",
                    values=query_embedding,
                )
            ],
            include_fields=[
                "text",
                "filename",
                "page_number",
                "document_id",
                "user_id",
                "chunk_index",
            ],
            filter={
                "$and": [
                    {"user_id": {"$eq": user_id}},
                    {"document_id": {"$eq": document_id}}
                ]
            },
        )

        retrieved_chunks = []

        for match in results.matches:

            retrieved_chunks.append({
                "id": match.id,
                "score": match.score,
                "text": getattr(match, "text", None),
                "filename": getattr(match, "filename", None),
                "page_number": getattr(match, "page_number", None),
                "document_id": getattr(match, "document_id", None),
                "chunk_index": getattr(match, "chunk_index", None),
            })

        return retrieved_chunks
