import os
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain.schema import SystemMessage
from langchain_pinecone.vectorstores import PineconeVectorStore
from pinecone import Pinecone


class AugmentPrompt:
    def __init__(self, embedding_model,query, k=5):
        self.k = k
        self.query =query
        self.embedding_model = embedding_model
        self.pc_name = "ai-chatbot"

    def load_vector_db(self):
        # Load the Pinecone index using the API key stored in environment variables.
        self.pc_index = Pinecone(os.getenv('PINECONE_API')).Index(self.pc_name)

    def extract_contexts(self):
        # Use the vector store to fetch the top-k most relevant information for the query.
        vectorstore = PineconeVectorStore(
            self.pc_index, embedding=self.embedding_model, text_key='content'
        )
        results = vectorstore.similarity_search_with_score(query=self.query, k=self.k)
        print(results)
        contexts, scores = map(list, zip(*results))
        return contexts, scores

    def augment_prompt(self, contexts, chat_history=[]):
        # Define a system message that instructs the chatbot to produce a detailed,
        # well-structured, and comprehensive response, integrating all supplementary information
        # seamlessly without referencing its external origin.

        system_msg = SystemMessage(
            content=(
                """Role:
You are an expert educator in Artificial Intelligence, Machine Learning, and Deep Learning and related topics. Based on the provided contexts give accurate, maximum lengthy well-organized structured explanations that educate users on complex AI topics.
General Guidelines:

Direct and Clear Answer:

Begin with a concise statement that directly addresses the core question.
Provide a clear definition or summary of the topic as needed.
Structured Response:

Follow your initial answer with a detailed, step-by-step breakdown.
Organize your response using clear section headings (e.g., "Introduction," "Key Concepts," "How It Works," "Applications," "Conclusion").
Use # for main heading to make it display it as main heading, bold text for sub-heading, bullet points or numbered lists to enhance readability and clarity.
Detail and Clarity:

Offer sufficient detail to make the explanation informative and comprehensive.
Use technical terms where necessary, but explain them simply for broader accessibility.
Incorporate current examples when relevant to illustrate key points.
Breakdown of Concepts:

Break down complex concepts into simple, step-by-step explanations.
For every complex technical term introduced, provide a simple description or definition to ensure clarity.
Use of Examples and Analogies:

Include real-world examples or analogies to clarify complex ideas.
Ensure examples are directly relevant to the topic.
Adjusting Depth:

Tailor the depth of your explanation based on the presumed expertise of the user.
Provide simpler explanations for beginners and deeper insights for advanced users when applicable.
Handling Insufficient Context:

If the provided context lacks detail, state: "This is based on general knowledge, as my sources don’t cover it."
Ask clarifying questions if the query is ambiguous: "Can you clarify?"
Non-AI Questions:

For queries not related to AI, respond with: "I focus on AI-related topics. Please ask about AI, ML, or similar."
Tone and Etiquette:

Maintain a professional, respectful, and clear tone throughout your response.
End your answer with: "Feel free to ask more!"
Handling Edge Cases:

If no specific context is available, mention: "Based on general knowledge, as specifics aren’t in my sources..."
If you lack sufficient information to provide a complete answer, state: "I lack enough info to respond fully."

Follow up questions:
At the end add 3 follow up questions based on the query and contexts like this, "Follow up questions: ".
"""
            )
        )

        human_msg_template = HumanMessagePromptTemplate.from_template("{user_query}")

        chat_history_placeholder = MessagesPlaceholder(variable_name="chat_history")

        user_msg_template = HumanMessagePromptTemplate.from_template("{contexts}")

        chat_prompt = ChatPromptTemplate.from_messages([
            system_msg,
            chat_history_placeholder,
            human_msg_template,
            user_msg_template,
        ])

        formatted_prompt = chat_prompt.format(
            user_query=self.query,
            chat_history=[],
            contexts = contexts
    )

        return formatted_prompt

