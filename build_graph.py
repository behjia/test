import os
from lightrag.components.data_process import PDFProcessor
from lightrag.components.model_client import GoogleGenAI
from lightrag.components.graph_builder import GraphBuilder
from lightrag.core.generator import Generator

# Make sure your GOOGLE_API_KEY is an environment variable
if "GOOGLE_API_KEY" not in os.environ:
    raise ValueError("Please set the GOOGLE_API_KEY environment variable.")

# 1. Point to the PDF
pdf_path = "riscv-spec.pdf"
print(f"Processing PDF: {pdf_path}")

# 2. Use LightRAG's PDF Processor to extract and chunk text
processor = PDFProcessor()
documents = processor(input=pdf_path)

# 3. Configure the Graph Builder to use Gemini to extract relationships
# We are using the free Gemini Flash model to save costs.
model_client = GoogleGenAI(model="gemini-1.5-flash-latest")
graph_builder = GraphBuilder(model_client=model_client)

print("Building knowledge graph from PDF text... (This may take several minutes)")
# This crawls the text and asks Gemini to find all (Subject, Predicate, Object) triplets
graph_builder(documents)
graph = graph_builder.get_graph()

# 4. Save the graph to disk so we don't have to rebuild it every time
graph_output_path = "riscv_knowledge_graph.json"
graph_builder.save_graph(graph_output_path)

print(f"✅ Knowledge graph built and saved to {graph_output_path}")
print(f"Graph has {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")