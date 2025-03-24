from src.clean_data import DataPreprocessing


class DataPreProcessingPipeline:
    def __init__(self):
        self.data_preprocessing = DataPreprocessing()

    def start_cleaning(self, book):
        clean_book_func = self.data_preprocessing.clean_data
        book['chunk'] = book['chunk'].apply(clean_book_func)
        return book
