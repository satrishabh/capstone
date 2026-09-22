from pathlib import Path
from typing import List, Dict, Tuple
import json
import numpy as np
from collections import Counter

from dotenv import load_dotenv

from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document

# Load environment variables
load_dotenv()

RAG_DOCS_PATH = Path("../rag_docs")
FAISS_PATH = Path("../vectorstore/faiss_index")
BM25_PATH = Path("../vectorstore/bm25_index")
EMBEDDING_MODEL = "gemini-embedding-2"

def get_embeddings():
    print(f"Initializing Gemini embedding model: {EMBEDDING_MODEL}")

    return GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2"
    )

def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """Simple text splitter without langchain_text_splitters dependency."""
    chunks = []
    words = text.split()
    current_chunk = []
    current_size = 0

    for word in words:
        word_len = len(word) + 1
        if current_size + word_len > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Keep overlap
            overlap_words = int(chunk_overlap / 5)  # Rough estimate
            current_chunk = current_chunk[-overlap_words:] if overlap_words > 0 else []
            current_size = sum(len(w) + 1 for w in current_chunk)

        current_chunk.append(word)
        current_size += word_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def load_documents_from_dir(docs_path: Path) -> List[Document]:
    """Load all markdown files from a directory."""
    documents = []

    if not docs_path.exists():
        print(f"Warning: RAG docs path {docs_path} does not exist")
        return documents

    for md_file in docs_path.rglob("*.md"):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
                documents.append(
                    Document(
                        page_content=content,
                        metadata={"source": str(md_file)}
                    )
                )
        except Exception as e:
            print(f"Error loading {md_file}: {e}")

    return documents


class BM25Retriever:
    """BM25 keyword-based retriever."""

    def __init__(self, documents: List[Document]):
        self.documents = documents
        self.corpus = [doc.page_content for doc in documents]
        self._build_bm25()

    def _build_bm25(self):
        """Build BM25 index from documents."""
        self.tokenized_corpus = [self._tokenize(doc) for doc in self.corpus]
        self.doc_freqs = []

        for tokens in self.tokenized_corpus:
            freq = Counter(tokens)
            self.doc_freqs.append(freq)

        self.avg_doc_len = sum(len(tokens) for tokens in self.tokenized_corpus) / len(self.tokenized_corpus) if self.tokenized_corpus else 1
        self.idf = self._compute_idf()

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        return text.lower().split()

    def _compute_idf(self) -> Dict[str, float]:
        """Compute IDF scores."""
        idf = {}
        N = len(self.corpus)

        for tokens in self.tokenized_corpus:
            for token in set(tokens):
                idf[token] = idf.get(token, 0) + 1

        for token in idf:
            idf[token] = np.log((N - idf[token] + 0.5) / (idf[token] + 0.5) + 1)

        return idf

    def retrieve(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        """Retrieve top-k documents using BM25."""
        query_tokens = self._tokenize(query)
        scores = []

        k1, b = 1.5, 0.75  # BM25 hyperparameters

        for i, doc_freq in enumerate(self.doc_freqs):
            score = 0.0
            for token in query_tokens:
                if token in doc_freq:
                    idf = self.idf.get(token, 0)
                    tf = doc_freq[token]
                    numerator = idf * tf * (k1 + 1)
                    denominator = tf + k1 * (1 - b + b * (len(self.tokenized_corpus[i]) / self.avg_doc_len))
                    score += numerator / denominator

            scores.append((self.documents[i], score))

        return sorted(scores, key=lambda x: x[1], reverse=True)[:k]


class HybridReranker:
    """Reranker that combines BM25 and vector search scores."""

    def __init__(self, bm25_weight: float = 0.4, vector_weight: float = 0.6):
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight

    def rerank(
        self,
        bm25_results: List[Tuple[Document, float]],
        vector_results: List[Dict],
        k: int = 5
    ) -> List[Dict]:
        """
        Combine BM25 and vector search results with weighted scoring.

        Args:
            bm25_results: List of (Document, score) tuples from BM25
            vector_results: List of dicts with 'content', 'source', 'score'
            k: Number of results to return

        Returns:
            Reranked list of result dicts
        """
        # Create a mapping of content to combined scores
        combined = {}

        # Normalize BM25 scores to [0, 1]
        bm25_scores = [score for _, score in bm25_results]
        max_bm25 = max(bm25_scores) if bm25_scores else 1

        for doc, score in bm25_results:
            normalized_bm25 = score / max_bm25 if max_bm25 > 0 else 0
            combined[doc.page_content[:100]] = {
                'document': doc,
                'bm25_score': normalized_bm25,
                'vector_score': 0,
                'source': doc.metadata.get('source', 'unknown'),
            }

        # Add vector search scores
        for result in vector_results:
            key = result['content'][:100]
            if key not in combined:
                combined[key] = {
                    'document': Document(
                        page_content=result['content'],
                        metadata={'source': result['source']}
                    ),
                    'bm25_score': 0,
                    'vector_score': result['score'],
                    'source': result['source'],
                }
            else:
                combined[key]['vector_score'] = result['score']

        # Compute hybrid scores
        for key in combined:
            item = combined[key]
            item['hybrid_score'] = (
                self.bm25_weight * item['bm25_score'] +
                self.vector_weight * (1 - item['vector_score'])  # Vector: lower is better
            )

        # Sort by hybrid score and return top-k
        sorted_results = sorted(
            combined.values(),
            key=lambda x: x['hybrid_score'],
            reverse=True
        )[:k]

        return [
            {
                'rank': i + 1,
                'content': item['document'].page_content,
                'source': item['source'],
                'bm25_score': round(item['bm25_score'], 3),
                'vector_score': round(item['vector_score'], 3),
                'hybrid_score': round(item['hybrid_score'], 3)
            }
            for i, item in enumerate(sorted_results)
        ]

def build_vectorstore():
    print("Loading RAG documents...")
    documents = load_documents_from_dir(RAG_DOCS_PATH)
    print(f"Loaded {len(documents)} documents")

    if not documents:
        raise ValueError(
            f"No documents found in {RAG_DOCS_PATH}"
        )

    # Split documents into chunks
    chunks = []
    for doc in documents:
        chunk_texts = split_text(doc.page_content)
        for chunk_text in chunk_texts:
            chunks.append(
                Document(
                    page_content=chunk_text,
                    metadata=doc.metadata
                )
            )

    print(f"Created {len(chunks)} chunks")


    # Build BM25 index
    print("Building BM25 index...")

    bm25_retriever = BM25Retriever(chunks)

    # Create the complete directory
    BM25_PATH.mkdir(parents=True, exist_ok=True)

    with open(
        BM25_PATH / "bm25_index.json",
        "w",
        encoding="utf-8"
    ) as f:
        bm25_data = {
            "corpus": [doc.page_content for doc in chunks],
            "sources": [
                doc.metadata.get("source", "unknown")
                for doc in chunks
            ],
            "idf": bm25_retriever.idf,
            "doc_freqs": [
                dict(df) for df in bm25_retriever.doc_freqs
            ],
            "avg_doc_len": bm25_retriever.avg_doc_len,
        }

        json.dump(bm25_data, f)

    print(f"BM25 index saved to {BM25_PATH}")

    # Create Gemini embeddings
    embeddings = get_embeddings()

    # Create FAISS vector store
    print("Generating Gemini embeddings for vector search...")
    vectorstore = FAISS.from_documents(
        documents=chunks,
        embedding=embeddings
    )

    # Save FAISS index
    FAISS_PATH.parent.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(FAISS_PATH))
    print(f"FAISS index saved to {FAISS_PATH}")

    return vectorstore


def load_bm25_retriever() -> BM25Retriever:
    """Load BM25 retriever from saved index."""
    with open(BM25_PATH / "bm25_index.json", "r") as f:
        bm25_data = json.load(f)

    documents = [
        Document(page_content=content, metadata={'source': source})
        for content, source in zip(bm25_data['corpus'], bm25_data['sources'])
    ]

    bm25 = BM25Retriever(documents)
    bm25.idf = {k: float(v) for k, v in bm25_data['idf'].items()}
    bm25.doc_freqs = [Counter(df) for df in bm25_data['doc_freqs']]
    bm25.avg_doc_len = bm25_data['avg_doc_len']

    return bm25


def load_vectorstore():
    """Load existing FAISS vector store."""
    embeddings = get_embeddings()
    vectorstore = FAISS.load_local(
        str(FAISS_PATH),
        embeddings,
        allow_dangerous_deserialization=True
    )
    return vectorstore


def retrieve_documents(
    query: str,
    k: int = 5,
    use_hybrid: bool = True
) -> List[Dict]:
    """
    Retrieve documents using hybrid BM25 + Vector Search + Reranking.

    Args:
        query: Search query
        k: Number of results to return
        use_hybrid: Use hybrid retrieval (True) or vector-only (False)

    Returns:
        List of retrieved documents with scores
    """
    if not use_hybrid:
        # Fallback to vector-only search
        vectorstore = load_vectorstore()
        results = vectorstore.similarity_search_with_score(query, k=k)

        retrieved_documents = []
        for i, (doc, score) in enumerate(results, start=1):
            retrieved_documents.append({
                "rank": i,
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "score": float(score),
                "method": "vector_search"
            })
        return retrieved_documents

    # Hybrid retrieval: BM25 + Vector Search + Reranking
    print("Retrieving with BM25...")
    bm25_retriever = load_bm25_retriever()
    bm25_results = bm25_retriever.retrieve(query, k=k*2)

    print("Retrieving with Vector Search...")
    vectorstore = load_vectorstore()
    vector_results_raw = vectorstore.similarity_search_with_score(query, k=k*2)
    vector_results = [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source", "unknown"),
            "score": float(score)
        }
        for doc, score in vector_results_raw
    ]

    print("Reranking results...")
    reranker = HybridReranker(bm25_weight=0.4, vector_weight=0.6)
    reranked = reranker.rerank(bm25_results, vector_results, k=k)

    return reranked


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