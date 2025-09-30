import os
import chainlit as cl
import meilisearch
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from litellm import completion
import asyncio

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
MEILI_HOST = os.getenv("MEILI_HOST")
MEILI_API_KEY = os.getenv("MEILI_API_KEY")
MEILI_INDEX_NAME = os.getenv("MEILI_INDEX_NAME")
LLM_MODEL = os.getenv("LLM_MODEL")

# --- Initialize Clients ---
try:
    meili_client = meilisearch.Client(MEILI_HOST, MEILI_API_KEY)
    meili_index = meili_client.index(MEILI_INDEX_NAME)
    # Check connection by fetching index stats
    meili_index.get_stats()
    MEILI_AVAILABLE = True
except Exception as e:
    print(f"Eroare la conectarea cu Meilisearch: {e}")
    meili_client = None
    MEILI_AVAILABLE = False

# System prompt for the LLM
LLM_SYSTEM_PROMPT = """
You are a professional translator and linguist. Your task is to translate the given term.
1.  First, detect the source language of the term (between Romanian and English).
2.  Translate it into the target language (if the source is Romanian, translate to English; if the source is English, translate to Romanian).
3.  Provide multiple translation variants if they exist, especially if the term has different meanings in different contexts.
4.  For each variant, provide a short, clear description or an example sentence to illustrate its usage.
5.  Format the output clearly using Markdown. Use bullet points for each variant.
"""

# --- Helper Functions ---
def detect_language(text: str) -> str:
    """Detects if the text is Romanian ('ro') or English ('en'). Defaults to 'en'."""
    try:
        lang = detect(text)
        if lang == 'ro':
            return 'ro'
        return 'en' # Default to English for other detected languages
    except LangDetectException:
        return 'en' # Default to English if detection fails

def search_in_meilisearch(term: str, lang: str) -> list[dict]:
    """Searches for a term and returns all matching documents."""
    if not MEILI_AVAILABLE:
        return [] # Return an empty list if not available
    
    search_field = 'lang_a' if lang == 'en' else 'lang_b'

    try:
        search_params = {
            'attributesToSearchOn': [search_field],
            'limit': 50 # Get up to 50 results
        }
        # Use the term as the main search query 'q'
        results = meili_index.search(term, search_params)
        return results.get('hits', []) # Return the list of hits, or empty list
    except Exception as e:
        print(f"Error searching Meilisearch: {e}")
        return [] # Return an empty list on error

async def translate_with_llm(term: str):
    """Generates a translation using the LLM."""
    messages = [
        {"role": "system", "content": LLM_SYSTEM_PROMPT},
        {"role": "user", "content": f"Please translate the following term: \"{term}\""}
    ]
    try:
        # Using async for non-blocking API call
        response = await asyncio.to_thread(
            completion,
            model=LLM_MODEL,
            messages=messages,
            # litellm will automatically use the GEMINI_API_KEY environment variable
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Am întâmpinat o eroare la contactarea LLM: {e}"

# --- Chainlit Logic ---
@cl.on_chat_start
async def start():
    """Function called when a new chat session starts."""
    await cl.Message(
        content="**Bun venit la KSV-10!**\n\nIntroduceți un termen în română sau engleză pentru a căuta traducerea."
    ).send()
    if not MEILI_AVAILABLE:
        await cl.Message(
            content="**Atenție:** Conexiunea la baza de date Meilisearch nu a putut fi stabilită. Se va folosi doar LLM-ul."
        ).send()

@cl.on_message
async def main(message: cl.Message):
    """Function called for every new message from the user."""
    term = message.content.strip()
    
    lang = detect_language(term)
    
    # Step 1: Search in Meilisearch
    meili_results = search_in_meilisearch(term, lang)
    
    if meili_results:
        # Found results in Meilisearch
        result_content = "### Din Baza de Cunoștințe:\n---\n"
        
        for hit in meili_results:
            en_term = hit.get('lang_a', '')
            ro_term = hit.get('lang_b', '')
            source = hit.get('source', '')
            
            rezultat_line = f"{en_term} / {ro_term}"

            result_content += f"**Rezultat:** {rezultat_line}\n"
            
            if source:
                result_content += f"**Sursa:** {source}\n"
            
            result_content += "\n" # Add a newline for spacing

        # Define the action button
        actions = [
            cl.Action(name="ask_llm", value=term, label="✨ Caută și cu LLM")
        ]

        # Send one message with both the results and the action button
        await cl.Message(
            content=result_content.strip(),
            actions=actions
        ).send()

    else:
        # Step 2: Fallback to LLM
        msg = cl.Message(content="")
        await msg.send()
        await msg.stream_token("**Sursă: LLM (Gemini)**\n\n")
        llm_response = await translate_with_llm(term)
        msg.content += llm_response
        await msg.update()

@cl.action_callback("ask_llm")
async def on_action(action: cl.Action):
    """Function called when the user clicks the 'ask_llm' action button."""
    term = action.value # The term to search is passed in the action's value
    
    # Let the user know the action is being processed
    await cl.Message(content=f'Se caută "{term}" cu LLM-ul...').send()
    
    # Call the LLM
    llm_response = await translate_with_llm(term)
    
    # Prepend the source to the response
    final_response = f"### Sursă: LLM (Gemini)\n---\n{llm_response}"
    
    await cl.Message(content=final_response).send()
