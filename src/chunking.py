import spacy
from transformers import AutoTokenizer


class Chunking:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    def dynamic_chunking(self,text, max_token=256):
        chunks = []
        current_chunk = []
        token_length = 0
        self.doc = self.nlp(text)
        for sent in self.doc.sents:
            curr_length = len(self.tokenizer.tokenize(sent.text))
            if curr_length + token_length <= max_token:
                current_chunk.append(sent.text)
                token_length += curr_length
            else:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sent.text]
                token_length = curr_length

        if current_chunk:
            chunks.append(' '.join(current_chunk))
        return chunks