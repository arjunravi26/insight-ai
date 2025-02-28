import re


class ExtractData:
    def __init__(self):
        self.chapter_no = 0
        self.chapter_contents = ""
        self.chapters = []
        self.dct_books = {
            "Artificial Intelligence: A Modern Approach, Global Edition, 4ed": range(19, 1073),
            'Designing Machine Learning Systems': range(1, 376),
            'Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow': range(28, 1230),
            'dga.ps': range(1, 9)
        }

    def extract(self, pdf_documents):
        chapter_no = 0
        chapter_contents = ""
        chapters =  []

        for doc in pdf_documents:
            text = doc.page_content
            try:
                page_label = int(doc.metadata['page_label'])
            except:
                continue
            if re.match(r'^Chapter \d.+\n', text) or re.match(r'^CHAPTER \d.+\n', text) or re.match(r'^CHAPTER \d+\n', text):
                if page_label in self.dct_books[doc.metadata['title']]:
                    if chapter_contents:
                        chapter_no += 1
                        chapters.append({
                            "chapter_no": f'CHAPTER {chapter_no}',
                            "content": chapter_contents,
                            "title": doc.metadata['title'],
                            "page_label": page_label
                        })
                    page_label = doc.metadata['page_label']
                    chapter_contents = text
            else:
                if page_label in self.dct_books[doc.metadata['title']]:
                    chapter_contents += text

        if page_label in self.dct_books[doc.metadata['title']]:
            if chapter_contents:
                chapter_no += 1
                chapters.append({
                            "chapter_no": f'CHAPTER {chapter_no}',
                            "content": chapter_contents,
                            "title": doc.metadata['title'],
                            "page_label": doc.metadata['page_label']
                        })
        return self.chapters