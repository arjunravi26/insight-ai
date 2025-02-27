from pipeline.pipeline import Pipeline
import logging
if __name__ == "__main__":
    logging.debug("Running")
    pipeline = Pipeline()
    pipeline.train()