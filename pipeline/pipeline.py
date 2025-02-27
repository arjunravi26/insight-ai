import logging
import re
from .load_data import DataIngestionPipeline
from .clean_data import DataPreProcessingPipeline
from .load_model import CreateModelPipeline
from .vector_db import CreateVectorDBPipeline
from .augment_data import AugmentPromptPipeline
from .extract_data import ExtractDataPipeline
class Pipeline:
    def __init__(self):
        print("Embedding Loading")
        self.model_pipeline = CreateModelPipeline()
        self.embedding_model = self.model_pipeline.start_embedding_model()
        self.llms = self.model_pipeline.start_llm_model()
        print("Embedding Loaded")

    def train(self):
        print("Data Ingestion Started")
        data_ingestion_pipeline = DataIngestionPipeline()
        pdf_document = data_ingestion_pipeline.start_ingestion()
        print("Data Ingestion Completed")
        print("Data Preprocessing Started")
        extract_data_pipeline = ExtractDataPipeline()
        print("Data Preprocessing Completed")
        print("Data Extraction Started")
        extracted_data = extract_data_pipeline.start_extraction(pdf_document)
        data_cleaning_pipeline = DataPreProcessingPipeline()
        cleaned_data = data_cleaning_pipeline.start_cleaning(extracted_data)
        print("Data Extraction Completed")
        print("Data Preprocessing Completed")
        print("Vector Database Creation..")
        vector_db_pipeline = CreateVectorDBPipeline(embedding_model=self.embedding_model)
        vector_db_pipeline.start_vectordb(cleaned_data)
        print("Vector Database Creation Completed")


    def predict(self,query,selected_model_idx):
        augmnet_query_pipeline = AugmentPromptPipeline(embedding_model=self.embedding_model,k=3,query=query)
        augmnet_query = augmnet_query_pipeline.start_augment_prompt()
        if not augmnet_query:
            return "I don't know about this topic. You can try these topics", ["What is Generative AI",
            "Explain about bias-variance trade-off","Explain neural networks."]
        print("Aguemneted Promt")
        print("-"*100)
        # print(scores,augmnet_query)
        print(f'before model {selected_model_idx}')
        response = self.llms[selected_model_idx].invoke(augmnet_query)
        print(response)
        if selected_model_idx ==  0:
            text = response.text()
        elif selected_model_idx == 1:
            text = response.content
        else:
            text = response
        parts = text.split('Follow up questions:')
        print(len(parts))
        if len(parts) < 2:
            # Log an error or handle gracefully
            answer = text
            follow_up = []
        else:
            follow_up = parts[1].split('?')
            answer = parts[0] + " ".join(follow_up[-1])
            follow_up = [re.sub(r'^\s*\d+\.\s*', '', text) for text in follow_up]

        print(follow_up)

        return answer,follow_up

