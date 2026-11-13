from src.ingestion.chunking import Chunking
from src.ingestion.ingestion import PineconeVectorStore
from src.ingestion.read_data import ExtractData
import logging

logger = logging.getLogger(__name__)

class IngestionService:

    def __init__(self, config, embedding_model):
        self.extractor = ExtractData()
        self.chunker = Chunking(config)
        self.vector_store = PineconeVectorStore(
            embedding_model=embedding_model,
            config=config,
            create_if_missing=True
        )

    def ingest_pdf(self, pdf_path: str, document_id: str, user_id: int, filename: str):

        extracted_documents = self.extractor.extract(
            pdf_path=pdf_path,
            document_id=document_id,
            filename=filename
        )

        chunked_documents = self.chunker.split_documents(extracted_documents)
        return self.vector_store.upsert_chunks(chunks=chunked_documents, user_id=user_id, document_id=document_id, filename=filename)
