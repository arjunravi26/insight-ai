import time
import os
import tqdm
import uuid
from pinecone import Pinecone, ServerlessSpec
from src.chunking import Chunking


class VectorDB:
    def __init__(self, embedding_model, batch_size=100):
        self.embedding_model = embedding_model
        self.index_name = "ai-chatbot"
        self.pc_index = None
        self.upsert_data = []
        self.chunking = Chunking()

    def create_vectordb(self):
        pc = Pinecone(os.getenv('PINECONE_API'))
        # pc.delete_index(self.index_name)
        index_list = [idx['name'] for idx in pc.list_indexes()]
        if self.index_name not in index_list:
            pc.create_index(name=self.index_name, spec=ServerlessSpec(
                cloud='aws', region='us-east-1'), dimension=768)
        timeout = 60
        start_time = time.time()
        while not pc.describe_index(self.index_name).status['ready']:
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout")
            time.sleep(1)
        self.pc_index = pc.Index(self.index_name)

    def create_upsert_data(self, data):
        batch_size = 16
        self.upsert_data = []
        for chapter in tqdm.tqdm(data, desc="Processing chapters"):
            chunks = self.chunking.dynamic_chunking(chapter['content'])
            for i in range(0, len(chunks), batch_size):
                end_i = min(len(chunks), i+batch_size)
                batch = chunks[i:i + end_i]
                batch_embeddings = self.embedding_model.embed_documents(batch)
                for text, embedding in zip(batch, batch_embeddings):
                    chunk_id = str(uuid.uuid4())
                    self.upsert_data.append({'id':chunk_id, 'values':embedding,
                            'metadata': {'title':chapter['title'],'chapter_page_no':chapter['chapter_page_no'],'content': text}})
    def insert_data(self):
        batch_size = 100
        status = self.pc_index.describe_index_stats()
        if status['total_vector_count'] == 0:
            # Adjust this value based on your dataset and limits
            # Upsert in batches
            for i in range(0, len(self.upsert_data), batch_size):
                batch = self.upsert_data[i:i+batch_size]
                self.pc_index.upsert(vectors=batch)
                print(f"Upserted batch {i // batch_size + 1}")

        else:
            print('Already Inserted data')
