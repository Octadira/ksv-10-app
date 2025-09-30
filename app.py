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

# Check for the auth secret to enable login
if "CHAINLIT_AUTH_SECRET" in os.environ:
    @cl.password_auth_callback
    def auth_callback(username, password):
        user = get_user(username)
        if not user:
            return None  # User not found
        
        if not verify_password(password, user['password_hash']):
            return None # Invalid password

        # Return a cl.User object
        return cl.User(username=user['username'], role=user['role'])


@cl.on_chat_start
async def on_chat_start():
    # Display the content of chainlit.md
    try:
        with open("chainlit.md", "r", encoding="utf-8") as f:
            await cl.Message(content=f.read()).send()
    except FileNotFoundError:
        await cl.Message(content="Bun venit la KSV-10!").send()

@cl.on_message
async def main(message: cl.Message):
    term = message.content.strip()
    
    if not term:
        await cl.Message(content="Vă rog să introduceți un termen.").send()
        return

    try:
        lang = detect(term)
    except:
        lang = "en" # Default to english if detection fails

    # Use the correct field names from the updated schema
    search_lang_field = "lang_a" if lang == "en" else "lang_b"
    
    # 1. Search in Meilisearch using the search method for better matching
    search_results = meili_index.search(term, {
        'limit': 5, # Return a few results
        'attributesToSearchOn': [search_lang_field]
    })

    if search_results['hits']:
        response = "**Rezultate din dicționar:**\n\n"
        for i, hit in enumerate(search_results['hits']):
            ro_term = hit.get('lang_b', 'N/A')
            en_term = hit.get('lang_a', 'N/A')
            explanation = hit.get('explanation', 'Fără explicație.')
            response += f"**{i+1}. {en_term}** (EN) - **{ro_term}** (RO)\n*Explicație:* {explanation}\n---\n"
        
        await cl.Message(content=response).send()

    else:
        # 2. Fallback to LLM
        actions = [
            cl.Action(
                name="ask_llm", 
                payload={"term": term}, 
                label="Întreabă AI-ul"
            )
        ]
        await cl.Message(content=f"Termenul **'{term}'** nu a fost găsit în dicționar.", actions=actions).send()

@cl.action_callback("ask_llm")
async def on_action(action: cl.Action):
    term = action.payload.get("term")
    await action.remove()

    msg = cl.Message(content="Apelez la AI... 🧠")
    await msg.send()

    system_prompt = ("You are a helpful bilingual dictionary assistant. Your goal is to provide a concise and accurate translation and a brief explanation for the given term. "
                     "The user will provide a term in either Romanian or English. You must respond with the translation in the other language and a short explanation. "
                     "Format the response clearly in Markdown, starting with the translation and then the explanation.")
    
    try:
        response = completion(
            model=LLM_MODEL,
            messages=[
                {"content": system_prompt, "role": "system"},
                {"content": f"Translate and explain the term: '{term}'", "role": "user"}
            ]
        )
        llm_response = response.choices[0].message.content
        msg.content = f"**Rezultat de la AI pentru '{term}':**\n\n{llm_response}"
        await msg.update()
    except Exception as e:
        msg.content = f"A apărut o eroare la contactarea serviciului AI: {e}"
        await msg.update()
