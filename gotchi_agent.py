import os, json, subprocess
from langchain.llms import Ollama
from langchain.vectorstores import Chroma
from langchain.embeddings import OllamaEmbeddings
from langchain.chains import RetrievalQA

brain_path = "gotchi_brain.json"
memory_dir = "gotchi_memory"

def load_brain():
    with open(brain_path) as f:
        return json.load(f)

def update_brain_log(entry):
    brain = load_brain()
    brain['memory_log'].append(entry)
    brain['xp'] += 10
    brain['level'] = 1 + brain['xp'] // 100
    with open(brain_path, "w") as f:
        json.dump(brain, f, indent=2)

def store_memory(text):
    embedding = OllamaEmbeddings(model="llama3")
    vectordb = Chroma(persist_directory=memory_dir, embedding_function=embedding)
    vectordb.add_texts([text])
    vectordb.persist()
    update_brain_log(f"Memory stored: {text[:50]}...")

def run_ai_chat():
    embedding = OllamaEmbeddings(model="llama3")
    vectordb = Chroma(persist_directory=memory_dir, embedding_function=embedding)
    retriever = vectordb.as_retriever()
    qa = RetrievalQA.from_chain_type(llm=Ollama(model="llama3"), retriever=retriever)
    while True:
        query = input("Ask Gotchi AI> ")
        if query.lower() in ["exit", "quit"]: break
        result = qa.run(query)
        print("Gotchi AI:", result)
        store_memory(f"Q: {query}
A: {result}")

if __name__ == "__main__":
    print("Type 'exit' to leave AI chat.")
    run_ai_chat()