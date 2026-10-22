"""Optional persisted semantic memory, initialized on first use."""
from pathlib import Path
from uuid import uuid4

VECTOR_DIR = Path(__file__).resolve().parent / "gotchi_vector_store"


def get_collection():
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError as exc:
        raise RuntimeError(
            "Install optional AI dependencies: pip install -r requirements-ai.txt"
        ) from exc
    client = chromadb.PersistentClient(path=str(VECTOR_DIR))
    embeddings = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    return client.get_or_create_collection(
        name="gotchi_memory", embedding_function=embeddings
    )


def add_memory_to_vector(text, meta=None, doc_id=None):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Memory must be nonempty")
    collection = get_collection()
    options = {"documents": [text], "ids": [doc_id or str(uuid4())]}
    if meta:
        options["metadatas"] = [meta]
    collection.add(**options)


def search_memory(query, n=3):
    if not isinstance(query, str) or not query.strip():
        return []
    if not isinstance(n, int) or not 1 <= n <= 100:
        raise ValueError("n must be 1 through 100")
    collection = get_collection()
    available = collection.count()
    if available == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(n, available))
    return results.get("documents", [[]])[0]
