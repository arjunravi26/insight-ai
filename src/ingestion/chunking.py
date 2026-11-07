from transformers import AutoTokenizer
from langchain_text_splitters import RecursiveCharacterTextSplitter


class Chunking:

    def __init__(self, config):
        self.tokenizer = AutoTokenizer.from_pretrained(
            config["embedding_model"]
        )

        self.splitter = (
            RecursiveCharacterTextSplitter
            .from_huggingface_tokenizer(
                self.tokenizer,
                chunk_size=config["chunking_size"],
                chunk_overlap=config["overlap_size"],
                separators=[
                    "\n\n",
                    "\n",
                    ". ",
                    " ",
                    ""
                ],
                add_start_index=True,
            )
        )

    def split_documents(self, documents):
        return self.splitter.split_documents(documents)
