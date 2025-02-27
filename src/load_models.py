from langchain_huggingface import HuggingFaceEmbeddings
from langchain_huggingface.llms import HuggingFaceEndpoint
from langchain_google_genai import ChatGoogleGenerativeAI
from transformers import pipeline
from langchain_mistralai import ChatMistralAI
from langchain_together import Together
from dotenv import load_dotenv
import torch
import os


class CreateModels:
    def __init__(self):
        load_dotenv()

        self.hf_token = os.getenv('HF_TOKEN')
        if self.hf_token is None:
            raise ValueError("HF_TOKEN is not set in the environment.")
        self.gemini_key = os.getenv('GOOGLE_API_KEY')
        if self.gemini_key is None:
            raise ValueError("Gemini token is not set in the environment.")
        self.mistral_key = os.getenv('MISTRAL_API_KEY')
        if self.mistral_key is None:
            raise ValueError("MISTRAL token is not set in the environment.")
        self.together_key = os.getenv('TOGHTHER_API_KEY')
        if self.together_key is None:
            raise ValueError("TOGETHER  token is not set in the environment.")

    def create_embedding(self):

        if torch.cuda.is_available():
            model_kwargs = {'device': 'cuda'}
            print("Using GPU")
        else:
            model_kwargs = {'device': 'cpu'}
            print("Using CPU")
        encode_kwargs = {'normalize_embeddings': True}
        model_name = 'sentence-transformers/all-mpnet-base-v2'
        embedding_model = HuggingFaceEmbeddings(model_name=model_name,
                                                model_kwargs=model_kwargs,
                                                encode_kwargs=encode_kwargs
                                                )
        return embedding_model

    def create_gemini(self):
        gemini_model = ChatGoogleGenerativeAI(
            api_key=self.gemini_key,
            model="gemini-1.5-pro",
            temperature=0.4,
            max_tokens=8912,
            timeout=None,
            max_retries=2,
        )
        return gemini_model

    def create_deepseek(self):
        # falcon_repo = "mistralai/Mistral-8X22B-Instruct-v0.3"
        mistral_model = ChatMistralAI(
            api_key=self.mistral_key,
            model="mistral-large-latest",
            temperature=0,
            max_retries=2,
        )
        return mistral_model

    def create_llama(self):
        # Initialize the Together AI LLM with Llama 3
        llama_model = Together(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            together_api_key=self.together_key,
            max_tokens=2048,
            temperature=0.7
        )
        return llama_model
