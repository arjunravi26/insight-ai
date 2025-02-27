from src.augument_prompt import AugmentPrompt


class AugmentPromptPipeline:
    def __init__(self, embedding_model, query, k=3):
        self.k = k
        self.query = query
        self.embedding_model = embedding_model
        self.pc_name = "ai-chatbot"

    def start_augment_prompt(self):
        augmentprompt_obj = AugmentPrompt(
            query=self.query, embedding_model=self.embedding_model)
        augmentprompt_obj.load_vector_db()
        contexts, scores = augmentprompt_obj.extract_contexts()
        contexts = [context for idx, context in enumerate(
            contexts) if scores[idx] >= 0.3]
        if contexts:
            augment_prompt = augmentprompt_obj.augment_prompt(contexts)
        else:
            augment_prompt = None
        return augment_prompt
