from src.generation.models import CreateModels, Provider
from src.generation.prompt import RAGGenerator
from src.retrieval.retrive import Retriever

class GenerationService:

    def __init__(self,config):
        self.model_factory = CreateModels()
        self.retriever = Retriever(config=config)
        self.rag_generator = RAGGenerator(self.model_factory)

    def generate_response(self, provider: Provider, query: str, document_id:str) -> dict:
        model = self.model_factory.get_model(provider)
        context = self.retriever.search_chunks(query=query, document_id=document_id)
        prompt = self.rag_generator.prompt.format(question=query,context=context)
        response = model.invoke(prompt)
        print(response)
        return response
