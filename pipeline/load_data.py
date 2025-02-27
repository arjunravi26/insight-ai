from src.load_data import DataIngestion

class DataIngestionPipeline:
    def __init__(self):
        pass

    def start_ingestion(self):
        data_ingestion = DataIngestion()
        book = data_ingestion.load_book_pdf()
        arvix = data_ingestion.load_arvix_data()
        return book, arvix
