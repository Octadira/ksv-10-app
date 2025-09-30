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

def search_in_meilisearch(term: str, lang: str) -> dict | None:
    """Searches for a term in the specified language field in Meilisearch."""
    if not MEILI_AVAILABLE:
        return None
    
    search_field = 'lang_a' if lang == 'en' else 'lang_b'

    try:
        search_params = {
            'attributesToSearchOn': [search_field], # Search ONLY in the correct language field
            'limit': 1
        }
        # Use the term as the main search query 'q'
        results = meili_index.search(term, search_params)
        
        # Optional: Check if the result is a good enough match.
        # For a dictionary, we want a fairly exact match.
        if results['hits']:
            hit = results['hits'][0]
            # Check if the search term is a whole word in the result.
            # This avoids matching "art" inside "article".
            # We split the result field by common delimiters.
            words_in_hit = set(hit.get(search_field, '').lower().split(' /(),'))
            if term.lower() in words_in_hit:
                 return hit
        return None
    except Exception as e:
        print(f"Error searching Meilisearch: {e}")
        return None

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
    
    # Send a thinking indicator
    thinking_msg = cl.Message(content="")
    await thinking_msg.send()

    lang = detect_language(term)
    
    # Step 1: Search in Meilisearch
    meili_result = search_in_meilisearch(term, lang)
    
    if meili_result:
        # Found in Meilisearch
        # Use the correct field names: lang_b for Romanian, lang_a for English
        ro_term = meili_result.get('lang_b', 'N/A')
        en_term = meili_result.get('lang_a', 'N/A')
        details = meili_result.get('explanation', 'Nicio explicație suplimentară.')
        
        final_content = f"""
### Rezultat găsit în Meilisearch
---
**Română:** `{ro_term}`

**Engleză:** `{en_term}`

**Detalii:** `{details}`
"""
        await cl.Message(content=final_content).send()

    else:
        # Step 2: Fallback to LLM
        await thinking_msg.stream_token("**Sursă: LLM (Gemini)**\n\n")
        llm_response = await translate_with_llm(term)
        await cl.Message(content=llm_response).send()

    # The thinking indicator message can be removed if desired,
    # or updated. Here we just leave it.
    await thinking_msg.remove()
