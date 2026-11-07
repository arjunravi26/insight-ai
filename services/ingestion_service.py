from src.ingestion.chunking import Chunking
from src.ingestion.ingestion import PineconeVectorStore
from src.ingestion.read_data import ExtractData


class IngestionService:

    def __init__(self, config, embedding_model):
        self.extractor = ExtractData()
        self.chunker = Chunking(config)
        self.vector_store = PineconeVectorStore(
            embedding_model=embedding_model,
            config=config,
            create_if_missing=True
        )

    def ingest_pdf(self, pdf_path: str, document_id: str | None = None, filename: str | None = None):

        extracted_documents = self.extractor.extract(
            pdf_path=pdf_path,
            document_id=document_id,
            filename=filename
        )

        chunked_documents = self.chunker.split_documents(extracted_documents)
        return self.vector_store.upsert_chunks(chunks=chunked_documents, document_id=document_id, filename=filename)
