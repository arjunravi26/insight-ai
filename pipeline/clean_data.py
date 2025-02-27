from src.clean_data import DataPreprocessing


class DataPreProcessingPipeline:
    def __init__(self):
        self.data_preprocessing = DataPreprocessing()

    def start_cleaning(self, book, arvix):
        clean_book_func = self.data_preprocessing.clean_book_data
        clean_arvix_func = self.data_preprocessing.clean_arvix
        book['chunk'] = book['chunk'].apply(clean_book_func)
        arvix['chunk'] = arvix['chunk'].apply(clean_arvix_func)
        return book, arvix
