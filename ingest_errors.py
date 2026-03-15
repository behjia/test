from rag_agent import HardwareRAG
rag = HardwareRAG(collections=["eda_diagnostics"])
rag.ingest_document("eda_errors.txt", collection_name="eda_diagnostics")