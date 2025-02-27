from src.extract_data import ExtractData
class ExtractDataPipeline:
    def __init__(self):
        self.extract_data = ExtractData()
    def start_extraction(self,pdf_documents):
        return self.extract_data.extract(pdf_documents)