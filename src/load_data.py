import pandas as pd
import logging
from datasets import load_dataset
from langchain_community.document_loaders import PyPDFDirectoryLoader


class DataIngestion:
    def __init__(self):
        pass

    def load_data(self):
        pdf_folder = "D:\BroCamp\Projects\Chatbot-ai\Data"
        try:
            pdf_loader = PyPDFDirectoryLoader(pdf_folder)
            pdf_documents = pdf_loader.load()
        except FileNotFoundError as e:
            logging.info(f"Error from data loading from pdf {e}")
        return pdf_documents