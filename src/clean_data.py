import re
import unicodedata

class DataPreprocessing:
    def __init__(self):
        pass


    def clean_data(text):
        """
        Cleans textbook data for an AI chatbot by:
        - Normalizing Unicode text.
        - Removing chapter and section headers.
        - Removing code blocks enclosed in triple backticks.
        - Replacing unwanted characters while preserving key punctuation.
        - Normalizing whitespace.
        """
        # Normalize Unicode (this can help in standardizing characters)
        text = unicodedata.normalize('NFKC', text)

        # Remove chapter headings (e.g., "1 Chapter 2 ..." at start of a line)
        text = re.sub(r'^\d+\s+Chapter\s+\d+\s+.*?\n', '', text, flags=re.MULTILINE)

        # Remove section headings (e.g., "Section 1.1 ..." at start of a line)
        text = re.sub(r'^Section\s+\d+(?:\.\d+)?\s+.*?\n', '', text, flags=re.MULTILINE)

        # Remove code blocks enclosed in triple backticks
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

        # Replace any character not in the allowed set with a space.
        # Allowed characters: alphanumerics, common punctuation, and newlines.
        text = re.sub(r'[^A-Za-z0-9.,;:\(\)\{\}\[\]\+\-\*/=<>%&\|\^\$#@~\n]', ' ', text)

        # Normalize whitespace (collapse multiple spaces/newlines into one space)
        text = re.sub(r'\s+', ' ', text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text
