from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv

from langchain_community.document_loaders import (
    DirectoryLoader,
    TextLoader
)

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

from langchain_community.vectorstores import FAISS

from langchain_google_genai import (
    GoogleGenerativeAIEmbeddings
)

# Load environment variables

load_dotenv()


RAG_DOCS_PATH = Path("../rag_docs")
FAISS_PATH = Path("../vectorstore/faiss_index")
EMBEDDING_MODEL = "gemini-embedding-2"

def get_embeddings():
    print(f"Initializing Gemini embedding model: "f"{EMBEDDING_MODEL}")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL
    )
    return embeddings

def build_vectorstore():
    print("Loading RAG documents...")
    loader = DirectoryLoader(
        str(RAG_DOCS_PATH),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={
            "encoding": "utf-8"
        }
    )
    documents = loader.load()
    print(f"Loaded {len(documents)} documents")
    if not documents:
        raise ValueError(
            f"No documents found in {RAG_DOCS_PATH}"
        )

    # Split documents into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(
        documents
    )

    print(f"Created {len(chunks)} chunks")
    # Create Gemini embeddings
    embeddings = get_embeddings()

    # Create FAISS vector store

    print("Generating Gemini embeddings...")

    vectorstore = FAISS.from_documents(
        documents=chunks,
        embedding=embeddings
    )
    # Save FAISS index
    FAISS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    vectorstore.save_local(
        str(FAISS_PATH)
    )

    print(f"FAISS index saved to {FAISS_PATH}")
    return vectorstore

# Load existing FAISS vector store
def load_vectorstore():
    embeddings = get_embeddings()
    vectorstore = FAISS.load_local(
        str(FAISS_PATH),
        embeddings,
        allow_dangerous_deserialization=True
    )

    return vectorstore


# Retrieve documents
def retrieve_documents(
    query: str,
    k: int = 5
) -> List[Dict]:

    vectorstore = load_vectorstore()
    results = vectorstore.similarity_search_with_score(
        query,
        k=k
    )

    retrieved_documents = []
    for i, (doc, score) in enumerate(
        results,
        start=1
    ):
        retrieved_documents.append(
            {
                "rank": i,
                "content": doc.page_content,
                "source": doc.metadata.get(
                    "source",
                    "unknown"
                ),
                "score": float(score)
            }
        )

    return retrieved_documents


# ---------------------------------------------------------
# Test retrieval
# ---------------------------------------------------------
"""
if __name__ == "__main__":

    print("\nBuilding vector store...\n")

    build_vectorstore()

    query = (
        "What are the common causes of "
        "engine overheating?"
    )

    print("\nRetrieving relevant documents...\n")

    results = retrieve_documents(
        query,
        k=5
    )

    for result in results:

        print("=" * 80)

        print(
            f"Result: {result['rank']}"
        )

        print(
            f"Score: {result['score']}"
        )

        print(
            f"Source: {result['source']}"
        )

        print(
            f"Content:\n{result['content']}"
        )

    print("=" * 80)
"""""