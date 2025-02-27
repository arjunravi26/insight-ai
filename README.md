
# Chatbot-ai

A chatbot designed to respond to AI-related queries.

## Overview

Chatbot-ai is an interactive platform that leverages advanced Natural Language Processing (NLP) techniques to provide accurate and relevant answers to questions about Artificial Intelligence. The chatbot is built using Python and integrates several key technologies to enhance its functionality.

## Features

- **Natural Language Processing**: Utilizes *spaCy* for efficient text processing and understanding.
- **Vector Similarity Search**: Implements *Pinecone* to perform similarity searches, enabling the retrieval of contextually relevant information.
- **Language Model Framework**: Employs *LangChain* to manage prompts and chain together various components for coherent responses.
- **Web Interface**: Provides a user-friendly interface using *Streamlit* allowing users to interact with the chatbot seamlessly.

## Installation

To set up the Chatbot-ai locally, follow these steps:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/arjunravi26/Chatbot-ai.git
   cd Chatbot-ai
   ```

2. **Create a virtual environment** (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. **Install the required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

After installation, you can start the chatbot application:

```bash
streamlit run app.py
```

This command will launch the Streamlit web interface in your default browser, where you can interact with the chatbot.

## Project Structure

- `Data/`: Contains datasets and knowledge bases utilized by the chatbot.
- `pipeline/`: Includes data processing and model training pipelines.
- `research/`: Houses experimental notebooks and research related to chatbot development.
- `src/`: Contains the source code for the chatbot's core functionalities.
- `app.py`: The main script to run the Streamlit web application.
- `main.py`: Entry point for backend services or additional functionalities.
- `requirements.txt`: Lists all Python dependencies required for the project.

## Contributing

Contributions are welcome! If you'd like to enhance the chatbot or fix issues, please fork the repository, create a new branch, and submit a pull request with your changes.
