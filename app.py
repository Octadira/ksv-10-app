import chainlit as cl
import os
from dotenv import load_dotenv
import meilisearch
from langdetect import detect
from litellm import completion
import sqlite3
from passlib.context import CryptContext

# --- Load Environment Variables ---
load_dotenv()

# --- Database and Auth Setup ---
DB_FILE = "users.db"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Meilisearch Connection ---
MEILI_URL = os.getenv("MEILI_URL")
MEILI_API_KEY = os.getenv("MEILI_API_KEY")
MEILI_INDEX_NAME = os.getenv("MEILI_INDEX_NAME", "documents")
meili_client = meilisearch.Client(MEILI_URL, MEILI_API_KEY)
meili_index = meili_client.index(MEILI_INDEX_NAME)

# --- LiteLLM (Gemini) Setup ---
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-pro")
LLM_SYSTEM_PROMPT = os.getenv("LLM_SYSTEM_PROMPT", '''
You are a professional translator and linguist. Your task is to translate the given term.
1.  First, detect the source language of the term (between Romanian and English).
2.  Translate it into the target language (if the source is Romanian, translate to English; if the source is English, translate to Romanian).
3.  Provide multiple translation variants if they exist, especially if the term has different meanings in different contexts.
4.  For each variant, provide a short, clear description or an example sentence to illustrate its usage.
5.  Format the output clearly using Markdown. Use bullet points for each variant.
''')

# --- Password & User Helper Functions ---
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(username):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

# --- Chainlit Authentication ---
if "CHAINLIT_AUTH_SECRET" in os.environ:
    @cl.password_auth_callback
    def auth_callback(username, password):
        user = get_user(username)
        if not user:
            return None  # User not found
        
        if not verify_password(password, user['password_hash']):
            return None # Invalid password
        
        # In new versions of Chainlit, 'identifier' is a required field for cl.User.
        return cl.User(identifier=user['username'], role=user['role'])


@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content="Bun venit la KSV-10! Introduceți un termen pentru a începe.").send()

@cl.on_message
async def main(message: cl.Message):
    msg_content = message.content.strip()
    
    if msg_content.startswith("/schimba_parola"):
        await cl.Message(content="Funcționalitatea de schimbare a parolei este temporar dezactivată.").send()
        return

    term = msg_content
    if not term:
        await cl.Message(content="Vă rog să introduceți un termen.").send()
        return

    try:
        lang = detect(term)
    except:
        lang = "en"

    search_lang_field = "lang_a" if lang == "en" else "lang_b"
    
    search_results = meili_index.search(term, {
        'attributesToSearchOn': [search_lang_field]
    })

    if search_results['hits']:
        results_str = ""
        for hit in search_results['hits']:
            result_line = f"Rezultat: {hit.get('lang_a', '')} / {hit.get('lang_b', '')}"
            source_line = f"Sursa: {hit.get('source', 'N/A')}"
            results_str += f"{result_line}\n{source_line}\n\n"
        
        final_response = "**Din Baza de Cunoștințe:**\n\n" + results_str
        
        # Add the original content to the payload to preserve it later
        ask_llm_action = cl.Action(
            name="ask_llm", 
            payload={"term": term, "original_content": final_response},
            label="Caută cu AI (LLM)"
        )
        await cl.Message(content=final_response, actions=[ask_llm_action]).send()
    else:
        llm_button_message = f"Termenul **'{term}'** nu a fost găsit. Doriți să încerc cu AI?"
        ask_llm_action = cl.Action(name="ask_llm", payload={"term": term}, label="Caută cu AI (LLM)")
        await cl.Message(content=llm_button_message, actions=[ask_llm_action]).send()

async def query_llm_and_update(term: str, msg: cl.Message, is_regenerate: bool = False):
    """Queries the LLM, formats the response, and updates the message with the answer and a regenerate button."""
    try:
        response = completion(
            model=LLM_MODEL,
            messages=[
                {"content": LLM_SYSTEM_PROMPT, "role": "system"},
                {"content": term, "role": "user"}
            ]
        )
        llm_response = response.choices[0].message.content
        
        prefix = "**Rezultat de la AI:**\n\n"
        if is_regenerate:
            prefix = "🔄 **Răspuns regenerat:**\n\n"

        msg.content = f"{prefix}{llm_response}"
        
        # Set the actions list with a single, correctly configured regenerate button
        msg.actions = [
            cl.Action(
                name="regenerate_llm", 
                payload={"term": term, "msg_id": msg.id},
                label="🔄 Mai încearcă o dată"
            )
        ]
        await msg.update()

    except Exception as e:
        msg.content = f"A apărut o eroare la contactarea serviciului AI: {e}"
        await msg.update()

@cl.action_callback("ask_llm")
async def ask_llm(action: cl.Action):
    # Preserve the original Meilisearch results by restoring the content
    original_content = action.payload.get("original_content")
    if original_content:
        # Create a proxy for the original message to remove the button
        original_msg = cl.Message(id=action.forId, content=original_content)
        original_msg.actions = [] # Remove actions
        await original_msg.update()

    # Create a new message for the LLM query
    term = action.payload.get("term")
    msg = cl.Message(content=f"Apelez la AI pentru '{term}'... 🧠")
    await msg.send()
    
    # This helper function will now handle the logic
    await query_llm_and_update(term, msg)

@cl.action_callback("regenerate_llm")
async def regenerate_llm(action: cl.Action):
    term = action.payload.get("term")
    msg_id = action.payload.get("msg_id")

    # Create a proxy for the message to update
    msg = cl.Message(id=msg_id, content=f"Regenerez răspunsul pentru '{term}'... 🔄")
    await msg.update()

    # The helper function will handle the rest
    await query_llm_and_update(term, msg, is_regenerate=True)