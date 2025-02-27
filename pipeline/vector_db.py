from src.vector_db import VectorDB
from pinecone import Pinecone
import os


class CreateVectorDBPipeline:
    def __init__(self, embedding_model, book, arvix, batch_size=100):
        self.embedding_model = embedding_model
        self.book = book
        self.arvix = arvix
        self.pc_index = None
        self.batch_size = batch_size


    def start_vectordb(self):
        vector_db = VectorDB(self.embedding_model, batch_size=self.batch_size)
        vector_db.create_vectordb()
        vector_db.insert_book(self.book)
        vector_db.insert_arvix(self.arvix)
