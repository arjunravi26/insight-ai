from src.load_data import DataIngestion

class DataIngestionPipeline:
    def __init__(self):
        pass

    def start_ingestion(self):
        data_ingestion = DataIngestion()
        data = data_ingestion.load_data()
        return data
