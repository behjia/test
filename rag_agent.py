"""
rag_agent.py
============
Retrieval-Augmented Generation (RAG) agent for the EDA pipeline.

Stores verified hardware specification documents (RISC-V ISA, AMBA AXI
protocol rules, Cyclone V timing constraints, etc.) in a persistent local
ChromaDB vector database. The LLM's RTL generation prompts are then
augmented with the most semantically relevant rules so it never has to
rely on its training data alone.

Dependencies
------------
pip install chromadb sentence-transformers

Usage
-----
>>> from rag_agent import HardwareRAG
>>> rag = HardwareRAG()
>>> rag.ingest_document("specs/riscv_opcodes.txt")
>>> context = rag.retrieve_context("ADD instruction encoding in RV32I")
>>> print(context)
"""

from __future__ import annotations

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

from pathlib import Path
from typing import Dict, List, Optional
import re

import networkx as nx

import chromadb
from chromadb.utils import embedding_functions

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Persistent DB will be written here; you can change this to any local path.
_CHROMA_PERSIST_DIR = os.getenv("HARDWARE_RAG_DIR", "./hardware_rag_db")

# SentenceTransformer model — runs 100 % locally, no API key required.
# "all-MiniLM-L6-v2" is tiny (80 MB) and very fast while still being
# accurate for dense technical text retrieval.
_EMBED_MODEL = os.getenv("HARDWARE_RAG_EMBED_MODEL", "all-MiniLM-L6-v2")

# Default ChromaDB collection name
_DEFAULT_COLLECTION_NAME = "hardware_specs"
# Specialized collection for curated Python oracles
_TESTBENCH_COLLECTION_NAME = "testbench_examples"

# How many characters per chunk when splitting documents.
_CHUNK_SIZE = 500

# Overlap between consecutive chunks (helps with boundary rules being split).
_CHUNK_OVERLAP = 80


# ---------------------------------------------------------------------------
# HardwareRAG class
# ---------------------------------------------------------------------------

class HardwareRAG:
    """Local vector-database RAG agent for hardware specification documents.

    Architecture
    ------------
    - **Storage**: ChromaDB (persistent, file-backed — no server needed).
    - **Embeddings**: sentence-transformers ``all-MiniLM-L6-v2`` via
      ChromaDB's built-in ``SentenceTransformerEmbeddingFunction``.
      Everything runs fully offline after the first model download.
    - **Chunking**: Fixed-size sliding window with overlap, splitting on
      newlines where possible to respect paragraph boundaries.

    Parameters
    ----------
    persist_dir:
        Directory where ChromaDB stores its SQLite + index files.
        Defaults to ``./hardware_rag_db`` (or the ``HARDWARE_RAG_DIR``
        environment variable).
    embed_model:
        HuggingFace sentence-transformers model name.
        Defaults to ``all-MiniLM-L6-v2``.
    """

    def __init__(
        self,
        persist_dir: str = _CHROMA_PERSIST_DIR,
        embed_model: str = _EMBED_MODEL,
        collections: List[str] | None = None,
    ):
        print(f"[RAG] Initialising ChromaDB at: {persist_dir}")
        print(f"[RAG] Embedding model         : {embed_model}")

        # PersistentClient automatically loads an existing DB or creates one.
        self._client = chromadb.PersistentClient(path=persist_dir)

        # Use sentence-transformers locally — no OpenAI/Cohere API required.
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embed_model
        )

        # Initialize collections
        requested_collections = collections or [_DEFAULT_COLLECTION_NAME]
        self._default_collection = requested_collections[0]
        self._collections: Dict[str, chromadb.api.models.Collection] = {}

        for name in requested_collections:
            _ = self._collection_for(name)

        # Report status for each collection
        for name, collection in self._collections.items():
            doc_count = collection.count()
            print(f"[RAG] Collection '{name}' ready. Documents in store: {doc_count}")
        print()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_text(self, text: str, doc_id: str, collection_name: Optional[str] = None) -> int:
        """Ingests a raw text string into the specified collection."""
        target_collection = self._collection_for(collection_name)
        chunks = self._split_text(text)
        if not chunks:
            return 0
        
        ids = [f"{doc_id}::{i}" for i in range(len(chunks))]
        metadatas = [{"source": doc_id, "chunk": i} for i in range(len(chunks))]
        
        target_collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas
        )
        return len(chunks)

    def retrieve_context(self, query: str, n_results: int = 3,
                         collection_name: Optional[str] = None) -> str:
        """Query the vector DB and return the top-N matching spec rules.

        Parameters
        ----------
        query:
            A natural-language description of what you need rules for.
            Example: ``"RISC-V RV32I ADD opcode encoding"``
        n_results:
            How many chunks to retrieve.  3 is a good default; increase
            for very broad queries but be mindful of token budget.

        Returns
        -------
        str
            A formatted multi-line string ready to be injected into an
            LLM system prompt.  Returns an empty string when the
            collection is empty.
        """
        target_collection = self._collection_for(collection_name)
        if target_collection.count() == 0:
            print(
                f"[RAG] ⚠️  Collection '{self._collection_name(collection_name)}' is empty. "
                "Inject documents first via ingest_document()."
            )
            return ""

        # Clamp n_results to however many docs we actually have
        n_results = min(n_results, target_collection.count())

        results = target_collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        retrieved_chunks: List[str]  = results["documents"][0]
        retrieved_meta:   List[dict] = results["metadatas"][0]
        retrieved_scores: List[float] = results["distances"][0]

        if not retrieved_chunks:
            return ""

        lines = []
        for idx, (chunk, meta, dist) in enumerate(
            zip(retrieved_chunks, retrieved_meta, retrieved_scores), start=1
        ):
            similarity = round(1.0 - dist, 4)     # cosine distance → similarity
            source     = meta.get("source", "unknown")
            lines.append(
                f"[Rule {idx} | source: {source} | relevance: {similarity}]\n"
                f"{chunk.strip()}"
            )

        formatted = "\n\n".join(lines)
        print(
            f"[RAG] Retrieved {len(retrieved_chunks)} rules for query: '{query[:60]}...'"
        )
        return formatted

    def has_collection(self, name: str) -> bool:
        """Check whether the given collection is available."""
        actual = self._collection_name(name)
        return actual in self._collections

    def list_sources(self, collection_name: Optional[str] = None) -> List[str]:
        """Return the unique filenames currently stored in the collection."""
        target_collection = self._collection_for(collection_name)
        if target_collection.count() == 0:
            return []
        all_meta = target_collection.get(include=["metadatas"])["metadatas"]
        return sorted({m["source"] for m in all_meta if "source" in m})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collection_name(self, name: Optional[str]) -> str:
        return name or self._default_collection

    def _collection_for(self, name: Optional[str] = None):
        actual_name = self._collection_name(name)
        if actual_name not in self._collections:
            self._collections[actual_name] = self._client.get_or_create_collection(
                name=actual_name,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[actual_name]

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_text(text: str, chunk_size: int = _CHUNK_SIZE,
                    overlap: int = _CHUNK_OVERLAP) -> List[str]:
        """Split *text* into overlapping fixed-size chunks.

        Strategy
        --------
        1. Prefer splitting on blank lines (paragraph boundaries) first.
        2. If a paragraph is still longer than *chunk_size*, hard-split it
           by character with *overlap* carry-over.

        This keeps semantic units (e.g., a single opcode table row or an
        AXI handshake rule) together as much as possible.
        """
        # Step 1 — split on blank lines to respect paragraph structure
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks: List[str] = []
        for para in paragraphs:
            if len(para) <= chunk_size:
                chunks.append(para)
            else:
                # Step 2 — hard-split long paragraphs with overlap
                start = 0
                while start < len(para):
                    end = start + chunk_size
                    chunks.append(para[start:end])
                    start += chunk_size - overlap

        return [c for c in chunks if c.strip()]


class GraphRAG:
    """Lightweight relational graph retriever for hardware modules."""

    def __init__(self, edges: List[tuple[str, str, str]] | None = None):
        self.graph = nx.DiGraph()
        for subj, predicate, obj in edges or []:
            self.add_relation(subj, predicate, obj)

    def add_relation(self, subject: str, predicate: str, obj: str) -> None:
        self.graph.add_edge(subject, obj, relation=predicate)

    def add_node(self, module_name: str, attrs: dict | None = None) -> None:
        if attrs:
            self.graph.add_node(module_name, **attrs)
        else:
            self.graph.add_node(module_name)

    def extract_subgraph(self, query: str) -> str:
        if self.graph.number_of_edges() == 0:
            return "Graph database is empty."
        keywords = {token.lower() for token in re.findall(r"\w+", query)}
        matches = {
            node for node in self.graph.nodes if any(keyword in node.lower() for keyword in keywords)
        }
        if not matches:
            return "No relational data found for this query."
        relations = []
        for subj, obj, data in self.graph.edges(data=True):
            if subj in matches or obj in matches:
                relations.append(f"{subj} -> {data.get('relation')} -> {obj}")
        if not relations:
            return "No adjacent relations matched this query."
        return "\n".join(relations)


class HybridRAG:
    """Combines vector and graph retrieval for a hybrid context."""

    def __init__(
        self,
        *,
        persist_dir: str = _CHROMA_PERSIST_DIR,
        embed_model: str = _EMBED_MODEL,
        vector_collections: List[str] | None = None,
        graph_edges: List[tuple[str, str, str]] | None = None,
    ):
        self.vector_db = HardwareRAG(
            persist_dir=persist_dir,
            embed_model=embed_model,
            collections=vector_collections,
        )
        self.graph_db = GraphRAG(edges=graph_edges)

    def retrieve_hybrid_context(self, query: str) -> str:
        vector_context = self.vector_db.retrieve_context(query)
        graph_context = self.graph_db.extract_subgraph(query)
        combined_context = (
            "=== FACTUAL CONTEXT (VECTOR) ===\n"
            f"{vector_context}\n\n"
            "=== RELATIONAL LOGIC MAP (GRAPH) ===\n"
            f"{graph_context}"
        )
        return combined_context

    def retrieve_context(self, query: str, n_results: int = 3, collection_name: Optional[str] = None) -> str:
        return self.vector_db.retrieve_context(query, n_results=n_results, collection_name=collection_name)

    def has_collection(self, name: str) -> bool:
        return self.vector_db.has_collection(name)

    def insert_graph_node(self, module_name: str, inputs: list[dict], outputs: list[dict]) -> None:
        attrs = {
            "inputs": [port.get("name") for port in inputs if port.get("name")],
            "outputs": [port.get("name") for port in outputs if port.get("name")],
        }
        self.graph_db.add_node(module_name, attrs=attrs)

    def add_relation(self, subject: str, predicate: str, obj: str) -> None:
        self.graph_db.add_relation(subject, predicate, obj)


def TestbenchRAG(*, persist_dir: str = _CHROMA_PERSIST_DIR, embed_model: str = _EMBED_MODEL):
    """Convenience helper to spin up a RAG tuned to testbench examples."""
    return HardwareRAG(
        persist_dir=persist_dir,
        embed_model=embed_model,
        collections=[_TESTBENCH_COLLECTION_NAME],
    )


# ---------------------------------------------------------------------------
# CLI: ingest a file and run a quick sanity-query
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python rag_agent.py ingest  <path/to/spec.txt>")
        print("  python rag_agent.py query   '<query string>'")
        print("  python rag_agent.py sources")
        sys.exit(1)

    rag    = HardwareRAG()
    action = sys.argv[1].lower()

    if action == "ingest" and len(sys.argv) >= 3:
        n = rag.ingest_document(sys.argv[2])
        print(f"Ingested {n} chunks.")

    elif action == "query" and len(sys.argv) >= 3:
        ctx = rag.retrieve_context(sys.argv[2], n_results=3)
        print("\n--- Retrieved Context ---")
        print(ctx if ctx else "(empty — no documents ingested yet)")

    elif action == "sources":
        srcs = rag.list_sources()
        print("Ingested sources:" if srcs else "No sources ingested yet.")
        for s in srcs:
            print(f"  • {s}")

    else:
        print(f"Unknown action: '{action}'")
        sys.exit(1)
