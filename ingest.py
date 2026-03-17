import fitz  # PyMuPDF
import re
from pathlib import Path
from rag_agent import HardwareRAG

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts raw text from a PDF document."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def intelligent_chunker(text: str) -> list[str]:
    """Splits text using a more robust recursive character splitter."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    # This splitter tries to split by paragraphs, then sentences, then words.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        length_function=len,
        is_separator_regex=False,
    )
    
    return text_splitter.split_text(text)

if __name__ == "__main__":
    PDF_FILE = "riscv-spec.pdf" # Make sure you rename your PDF to this
    
    print(f"Reading text from {PDF_FILE}...")
    raw_text = extract_text_from_pdf(PDF_FILE)
    
    print("Chunking document into semantic sections...")
    text_chunks = intelligent_chunker(raw_text)
    
    print(f"Found {len(text_chunks)} chunks. Ingesting into ChromaDB...")
    rag = HardwareRAG(collections=["hardware_specs"])
    
    # We will just use the PDF filename as the document ID
    doc_id = Path(PDF_FILE).name
    
    # Ingest the entire text as a single document with multiple chunks
    rag.ingest_text(
        text=raw_text, 
        doc_id=doc_id,
        collection_name="hardware_specs"
    )
    
    print(f"✅ Ingestion complete. {rag._collection_for('hardware_specs').count()} total documents now in collection.")