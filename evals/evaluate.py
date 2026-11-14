
import json
import pandas as pd

from datasets import Dataset

from ragas import evaluate
from ragas.metrics import (
    NonLLMContextPrecisionWithReference,
    NonLLMContextRecall,
)
from core.read_yaml import read_yaml


# --------------------------------------------------
# 1. Load evaluation dataset
# --------------------------------------------------

with open("evals/dataset.json", "r", encoding="utf-8") as file:
    evaluation_data = json.load(file)

config = read_yaml()
# --------------------------------------------------
# 2. Run your actual retriever
# --------------------------------------------------

from services.generation_service import GenerationService

# Initialize using your application's normal configuration.
# Adapt initialization to your existing dependency setup.
generation_service = GenerationService(config=config)

records = []

for item in evaluation_data:

    question = item["question"]

    retrieved_chunks = generation_service.retriever.search_chunks(
        query=question,
        document_id=item.get("document_id"),
        user_id=item.get("user_id"),
        top_k=5
    )

    records.append({
        "user_input": question,

        "retrieved_contexts": [
            chunk["text"] for chunk in retrieved_chunks
        ],

        "reference": item["reference"],

        "reference_contexts": item["reference_contexts"]
    })


# --------------------------------------------------
# 3. Create RAGAS dataset
# --------------------------------------------------

dataset = Dataset.from_list(records)


# --------------------------------------------------
# 4. Select non-LLM metrics
# --------------------------------------------------

metrics = [
    NonLLMContextPrecisionWithReference(),
    NonLLMContextRecall()
]


# --------------------------------------------------
# 5. Evaluate
# --------------------------------------------------

results = evaluate(
    dataset=dataset,
    metrics=metrics
)


# --------------------------------------------------
# 6. Save results
# --------------------------------------------------

print(results)

results_df = results.to_pandas()

results_df.to_csv(
    "evals/retrieval_results.csv",
    index=False
)

print("\nAverage retrieval scores:")

print(
    results_df[
        [
            "non_llm_context_precision_with_reference",
            "non_llm_context_recall"
        ]
    ].mean()
)
