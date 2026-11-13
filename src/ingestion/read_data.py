import re
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
import logging

logger = logging.getLogger(__name__)


class ExtractData:

    def extract(
        self,
        pdf_path: str,
        document_id: str | None = None,
        filename: str | None = None
    ) -> list[Document]:

        try:

            loader = PyPDFLoader(pdf_path)
            pdf_documents = loader.load()

            extracted_documents = []

            for page_index, doc in enumerate(pdf_documents):

                # Extract page text
                text = self._clean_text(doc.page_content)

                # Skip empty pages
                if not text:
                    continue

                # Preserve existing PDF metadata
                metadata = dict(doc.metadata or {})

                # Determine page number.
                # PyPDFLoader commonly provides a zero-based `page` value.
                original_page = metadata.get("page")

                if isinstance(original_page, int):
                    page_number = original_page + 1
                else:
                    page_number = page_index + 1

                # Determine filename
                source = metadata.get("source", "")

                if not filename and source:
                    filename = Path(str(source)).name

                # Attach consistent metadata
                metadata.update({
                    "document_id": document_id,
                    "filename": filename or "uploaded.pdf",
                    "page_number": page_number
                })

                # Create a clean LangChain Document
                extracted_documents.append(
                    Document(
                        page_content=text,
                        metadata=metadata
                    )
                )

            return extracted_documents
        except Exception as e:
            logger.exception(f"Exception at extract data. {e}")

    @staticmethod
    def _clean_text(text: str) -> str:

        if not text:
            return ""

        # Remove null characters
        text = text.replace("\x00", "")

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Remove excessive spaces and tabs
        text = re.sub(r"[ \t]+", " ", text)

        # Remove excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()
