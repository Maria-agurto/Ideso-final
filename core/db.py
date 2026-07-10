"""
Conexión a MongoDB Atlas — reemplaza la celda 6 del notebook
(Ernesto_Investing_AI_iDeSo_Mongo.ipynb), pero sin FastAPI ni ngrok:
aquí Streamlit llama directo a estas funciones en el mismo proceso.
"""
import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi


@st.cache_resource(show_spinner="Conectando a MongoDB Atlas…")
def get_mongo_client() -> MongoClient:
    uri = st.secrets.get("MONGO_URI")
    if not uri:
        raise RuntimeError(
            "Falta MONGO_URI en .streamlit/secrets.toml. "
            "Copia .streamlit/secrets.toml.example y completa tu connection string."
        )
    client = MongoClient(uri, server_api=ServerApi("1"))
    client.admin.command("ping")
    return client


def get_db():
    return get_mongo_client()["ideso"]


def get_collections():
    """Misma estructura que el notebook: usuarios, cache_modelos, logs_resultados."""
    db = get_db()
    col_usuarios = db["usuarios"]
    col_cache = db["cache_modelos"]
    col_logs = db["logs_resultados"]
    col_usuarios.create_index("email", unique=True)
    col_cache.create_index("key", unique=True)
    col_logs.create_index([("modulo", 1), ("ts", -1)])
    return col_usuarios, col_cache, col_logs


def mongo_status() -> tuple[bool, str]:
    """Para el punto de 'API conectada' del portal — ahora es 'Mongo conectada'."""
    try:
        client = get_mongo_client()
        client.admin.command("ping")
        return True, "Conectado"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
