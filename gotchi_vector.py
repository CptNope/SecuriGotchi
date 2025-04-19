import chromadb
from chromadb.utils import embedding_functions
import os

VECTOR_DIR = "gotchi_vector_store"

client = chromadb.Client(chromadb.config.Settings(chroma_db_impl="duckdb+parquet", persist_directory=VECTOR_DIR))
if not os.path.exists(VECTOR_DIR):
    os.makedirs(VECTOR_DIR)

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_or_create_collection(name="gotchi_memory", embedding_function=embedding_fn)

def add_memory_to_vector(text, meta=None, doc_id=None):
    if doc_id is None:
        doc_id = str(len(collection.get()["documents"]) + 1)
    collection.add(documents=[text], metadatas=[meta or {}], ids=[doc_id])
    client.persist()

def search_memory(query, n=3):
    results = collection.query(query_texts=[query], n_results=n)
    return results["documents"][0]