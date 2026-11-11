import os
from src.embedding.embedding import EmbeddingModel
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

class PineconeVectorStore:

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        config,
        create_if_missing: bool = False,
    ):
        self.embedding_model = embedding_model
        self.index_name = config["index_name"]
        self.namespace = config["namespace"]
        self.dimension = config["dimension"]

        api_key = os.getenv("PINECONE_API_KEY")

        if not api_key:
            raise ValueError(
                "PINECONE_API_KEY environment variable is missing.")

        self.pc = Pinecone(api_key=api_key)

        existing_indexes = {
            item.name for item in self.pc.indexes.list()
        }

        if self.index_name not in existing_indexes:

            if not create_if_missing:
                raise ValueError(
                    f"Pinecone index '{self.index_name}' does not exist."
                )

            self._create_index(config["cloud"], config["region"])

        self.index = self.pc.index(self.index_name)

    def _create_index(self, cloud: str, region: str):
        """Create a schema-based Pinecone index."""

        self.pc.indexes.create(
            name=self.index_name,
            schema={
                "fields": {
                    "embedding": {
                        "type": "dense_vector",
                        "dimension": self.dimension,
                        "metric": "cosine",
                    }
                }
            },
            deployment={
                "deployment_type": "managed",
                "cloud": cloud,
                "region": region,
            },
        )

        print(f"Pinecone index '{self.index_name}' created.")

    def _embed_documents(self, texts):
        """Generate embeddings for multiple document chunks."""

        if hasattr(self.embedding_model, "embed_documents"):
            embeddings = self.embedding_model.embed_documents(texts)

        elif hasattr(self.embedding_model, "encode"):
            embeddings = self.embedding_model.encode(
                texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

        else:
            raise TypeError(
                "Embedding model must expose embed_documents() or encode()."
            )

        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()

        return embeddings

    def upsert_chunks(
        self,
        chunks,
        document_id: str,
        user_id: int,
        filename: str,
        batch_size: int = 50,
    ):
        """
        Generate embeddings and store document chunks in Pinecone.

        Args:
            chunks: List of LangChain Document objects.
            document_id: Unique ID for the uploaded document.
            filename: Original PDF filename.
            batch_size: Number of records per upsert request.
        """

        if not chunks:
            raise ValueError("No chunks provided for ingestion.")

        if not document_id:
            raise ValueError("document_id cannot be empty.")

        if not filename:
            raise ValueError("filename cannot be empty.")

        if batch_size < 1:
            raise ValueError("batch_size must be positive.")

        texts = [
            chunk.page_content.strip()
            for chunk in chunks
        ]

        if any(not text for text in texts):
            raise ValueError("Empty chunk encountered.")

        embeddings = self._embed_documents(texts)

        if len(embeddings) != len(chunks):
            raise ValueError("Number of embeddings does not match chunks.")

        records = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):

            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()

            embedding = [float(value) for value in embedding]

            if len(embedding) != self.dimension:
                raise ValueError(
                    f"Expected {self.dimension} dimensions, "
                    f"received {len(embedding)}."
                )

            metadata = chunk.metadata or {}

            record = {
                "_id": f"{document_id}-chunk-{i}",
                "embedding": embedding,
                "text": texts[i],
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,
                "user_id": user_id,
            }

            page = metadata.get("page")

            if page is not None:
                record["page_number"] = int(page) + 1

            records.append(record)

        total_upserted = 0

        for start in range(0, len(records), batch_size):

            batch = records[start:start + batch_size]

            response = self.index.documents.upsert(
                namespace=self.namespace,
                documents=batch,
            )

            total_upserted += response.upserted_count

        return {
            "document_id": document_id,
            "user_id": user_id,
            "filename": filename,
            "chunks_created": len(records),
            "chunks_upserted": total_upserted,
            "status": "completed",
        }
