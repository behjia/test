from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter
from rag_agent import HardwareRAG
import os

if __name__ == "__main__":
    PDF_FILE = "riscv-spec.pdf" # Make sure your PDF is named this

    # 1. Load the PDF using Unstructured, which converts it to clean Markdown
    print(f"Loading and parsing {PDF_FILE} into structured Markdown...")
    loader = UnstructuredFileLoader(PDF_FILE, mode="elements")
    documents = loader.load()
    
    # Concatenate all elements into a single markdown string
    markdown_content = "\n\n".join([doc.page_content for doc in documents])

    # 2. Use a Markdown-aware splitter to chunk by headers
    # This keeps sections and tables semantically intact.
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    text_chunks = markdown_splitter.split_text(markdown_content)

    # Convert Langchain's Document objects to a single string, respecting the structure
    clean_markdown_text = "\n\n".join([chunk.page_content for chunk in text_chunks])

    # 3. Save the clean Markdown to a temporary file
    temp_markdown_file = "temp_riscv_spec.md"
    with open(temp_markdown_file, "w") as f:
        f.write(clean_markdown_text)
    
    print(f"Saved cleaned Markdown to {temp_markdown_file}. Now ingesting...")

    # 4. Ingest the CLEAN file using your existing, proven RAG agent method
    rag = HardwareRAG(collections=["hardware_specs"])
    
    # First, clear the old, broken chunks from the database
    # (We need to find the right method for this in your class. For now, let's assume direct access)
    try:
        # Get all documents with the old source to delete them
        old_docs = rag._collection_for("hardware_specs").get(where={"source": "riscv-spec.pdf"})
        if old_docs['ids']:
            rag._collection_for("hardware_specs").delete(ids=old_docs['ids'])
            print("Cleared old, broken chunks from the database.")
    except Exception as e:
        print(f"Could not clear old chunks (this might be ok on first run): {e}")

    # Now, ingest the clean file
    rag.ingest_document(temp_markdown_file, collection_name="hardware_specs")
    
    # Optional: clean up the temporary file
    os.remove(temp_markdown_file)

    print(f"✅ Ingestion complete. {rag._collection_for('hardware_specs').count()} documents stored in 'hardware_specs' collection.")