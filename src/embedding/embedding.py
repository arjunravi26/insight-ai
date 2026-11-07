from sentence_transformers import SentenceTransformer


class EmbeddingModel:

    def __init__(self):
        self.model = SentenceTransformer(
            "sentence-transformers/all-mpnet-base-v2"
        )

    def embed_documents(self, texts):
        return self.model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True
        )

    def embed_query(self, query):
        return self.model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True
        )
