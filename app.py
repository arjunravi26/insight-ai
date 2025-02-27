import asyncio
import streamlit as st
from pipeline.pipeline import Pipeline

# Ensure an asyncio event loop is running.
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Configure the Streamlit page.
st.set_page_config(
    page_title="INSIGHTAI",
    page_icon="🍏",
    layout="wide"
)

def inject_css():
    """Inject minimal, elegant CSS inspired by Apple's design."""
    st.markdown("""
    <style>
        body {
            background: #f9f9f9;
            font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif;
            color: #333;
            margin: 0;
            padding: 0;
        }
        .header {
            background: #ffffff;
            padding: 2rem;
            margin-bottom: 1.5rem;
            border-bottom: 2px solid #eaeaea;
            text-align: center;
            font-size: 2.5rem;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .chat-container {
            background: #ffffff;
            padding: 1.2rem 1.5rem;
            margin: 1rem 0;
            border-radius: 10px;  /* Fixed typo: was a10px */
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            font-size: 1.15rem;
            line-height: 1.5;
        }
        .chat-container.user {
            border-left: 5px solid #007aff;
        }
        .chat-container.assistant {
            border-left: 5px solid #888;
        }
        .suggestions {
            background: #ffffff;
            padding: 1.5rem;
            margin: 1rem 0;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            font-size: 1.1rem;
            line-height: 1.6;
            border-left: 5px solid #007aff;
        }
        .css-1d391kg {
            background: #ffffff;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
        }
        .stSpinner > div {
            color: #007aff;
        }
        button {
            transition: all 0.2s ease;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def load_pipeline() -> Pipeline:
    """Load the pipeline (model, embeddings, etc.) only once."""
    return Pipeline()

# Initialize the pipeline at module level for persistence
try:
    pipeline = load_pipeline()
except Exception as e:
    st.error(f"Failed to load pipeline: {e}")
    pipeline = None

def get_response(model_number: int, query: str, chat_history: list) -> tuple:
    """
    Generate a response using the selected model.
    Returns a tuple: (answer, follow_up_questions)
    """
    try:
        # Make a clean copy of the chat history to avoid any reference issues
        history_copy = [dict(msg) for msg in chat_history]
        answer, follow_ups = pipeline.predict(query, model_number)
        # Ensure follow_ups is always a list
        if follow_ups is None:
            follow_ups = []
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        answer, follow_ups = f"An error occurred: {e}", []
    return answer, follow_ups

def render_chat(chat_history):
    """Render the complete chat history."""
    for message in chat_history:
        if message["role"] == "user":
            st.markdown(
                f"<div class='chat-container user'><strong>You:</strong> {message['content']}</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div class='chat-container assistant'>\n\n{message['content']}</div>",
                unsafe_allow_html=True
            )

def process_query(query, model_number, chat_placeholder, followup_placeholder):
    """
    Process any query (entered manually, suggestion, or follow-up) uniformly.
    Appends the query to chat history, shows 'Processing...', then updates chat and follow-ups.
    """
    if not query or query.strip() == "":
        return  # Skip empty queries

    # Add the user query to chat history
    st.session_state["chat_history"].append({"role": "user", "content": query})

    # Add a placeholder for the assistant's response
    st.session_state["chat_history"].append({"role": "assistant", "content": "Processing..."})

    # Update the chat display to show the processing state
    chat_placeholder.empty()
    with chat_placeholder.container():
        render_chat(st.session_state["chat_history"])

    # Generate the response - use history excluding the "Processing..." message
    with st.spinner("Processing..."):
        # Create a copy of chat history without the last message (which is "Processing...")
        history_for_model = st.session_state["chat_history"][:-1]
        answer, follow_ups = get_response(model_number, query, history_for_model)

    # Update the placeholder with the actual response
    st.session_state["chat_history"][-1]["content"] = answer

    # Save follow-ups in session state for persistence
    st.session_state["current_follow_ups"] = follow_ups

    # Re-render the chat with the updated response
    chat_placeholder.empty()
    with chat_placeholder.container():
        render_chat(st.session_state["chat_history"])

    # Render follow-up questions
    render_followups(follow_ups, model_number, chat_placeholder, followup_placeholder)

def render_followups(follow_ups, model_number, chat_placeholder, followup_placeholder):
    """
    Render follow-up questions as clickable buttons.
    When clicked, the follow-up text is processed.
    """
    # Clear existing follow-ups
    followup_placeholder.empty()

    # Store follow-ups in session state for persistence
    st.session_state["current_follow_ups"] = follow_ups

    if not follow_ups or len(follow_ups) == 0:
        return

    with followup_placeholder.container():
        st.markdown(
            "<div class='suggestions'><strong>Follow-up Questions:</strong></div>",
            unsafe_allow_html=True
        )

        # Use a container for buttons to ensure proper rendering
        button_cols = st.columns(min(len(follow_ups), 3))

        # Create buttons with truly unique keys
        for idx, question in enumerate(follow_ups[:3]):
            button_key = f"followup_{st.session_state.get('button_key_counter', 0) + idx}"

            if button_cols[idx].button(question, key=button_key, use_container_width=True):
                # Set the clicked question for processing
                st.session_state["followup_to_process"] = question
                # Increment button key counter to ensure uniqueness
                st.session_state["button_key_counter"] = st.session_state.get("button_key_counter", 0) + len(follow_ups)
                st.rerun()

def render_suggestions(model_number, chat_placeholder, followup_placeholder):
    """
    Render three clickable AI topic suggestions (when no conversation exists).
    """
    suggestions = [
        "What is Artificial Intelligence?",
        "How do neural networks work?",
        "What are the ethical implications of AI?"
    ]
    st.markdown(
        "<div class='suggestions'><strong>Explore AI Topics:</strong></div>",
        unsafe_allow_html=True
    )
    cols = st.columns(3)
    for idx, suggestion in enumerate(suggestions):
        # Use unique keys
        suggestion_key = f"suggestion_{idx}_{st.session_state.get('suggestion_counter', 0)}"
        if cols[idx].button(suggestion, key=suggestion_key, use_container_width=True):
            st.session_state["suggestion_counter"] = st.session_state.get("suggestion_counter", 0) + 1
            process_query(suggestion, model_number, chat_placeholder, followup_placeholder)
            st.rerun()  # Force a rerun to update the UI

def main():
    """Main function to run INSIGHTAI."""
    inject_css()

    # Initialize session state variables
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if "button_key_counter" not in st.session_state:
        st.session_state["button_key_counter"] = 0

    if "suggestion_counter" not in st.session_state:
        st.session_state["suggestion_counter"] = 0

    if "current_follow_ups" not in st.session_state:
        st.session_state["current_follow_ups"] = []

    # Separate variable for follow-up to process
    if "followup_to_process" not in st.session_state:
        st.session_state["followup_to_process"] = None

    # Sidebar configuration
    st.sidebar.title("Options")
    models = ["Gemini", "Mistral", "Llama"]
    selected_model = st.sidebar.selectbox("Select a Model", models)
    model_number = models.index(selected_model)

    if st.sidebar.button("Clear Chat History"):
        st.session_state["chat_history"] = []
        st.session_state["followup_to_process"] = None
        st.session_state["current_follow_ups"] = []
        st.rerun()

    # Main UI
    st.markdown("<div class='header'>INSIGHT-AI</div>", unsafe_allow_html=True)

    # Create placeholders for dynamic content
    chat_placeholder = st.empty()
    followup_placeholder = st.empty()

    # Check if we have a follow-up to process from a button click
    if st.session_state.get("followup_to_process"):
        query = st.session_state["followup_to_process"]
        # Clear the follow-up immediately to prevent processing loops
        st.session_state["followup_to_process"] = None
        # Process the follow-up query
        process_query(query, model_number, chat_placeholder, followup_placeholder)
    else:
        # Render the chat history or suggestions
        with chat_placeholder.container():
            if not st.session_state["chat_history"]:
                render_suggestions(model_number, chat_placeholder, followup_placeholder)
            else:
                render_chat(st.session_state["chat_history"])

        # Re-render any follow-up questions from the last response
        if st.session_state.get("current_follow_ups"):
            render_followups(
                st.session_state["current_follow_ups"],
                model_number,
                chat_placeholder,
                followup_placeholder
            )

    # Process new user input from chat box
    user_input = st.chat_input("Type your question here...")
    if user_input:
        # Clear any pending follow-ups
        st.session_state["followup_to_process"] = None
        process_query(user_input, model_number, chat_placeholder, followup_placeholder)

if __name__ == "__main__":
    main()