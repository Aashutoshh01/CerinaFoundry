"""
Graph Visualization Utility for Cerina.

This script generates a static image (PNG) of the LangGraph workflow architecture.
It uses the Mermaid.js rendering engine via LangChain to visualize the nodes,
edges, and conditional routing logic defined in `graph.py`.
"""

from graph import graph
from langchain_core.runnables.graph import MermaidDrawMethod

def generate_graph_image():
    """
    Compiles the current graph state and exports it as a PNG image.
    
    This function inspects the compiled graph object, including 'x-ray' views
    of nested subgraphs if present, and saves the visual representation to the
    local filesystem.
    
    Raises:
        Exception: If the graph cannot be rendered (often due to missing network
                   access for the API or missing local rendering libraries).
    """
    print(">>> Generating Architecture Diagram...")
    
    try:
        # Retrieve the graph object from the compiled workflow
        # xray=True allows visualization of inner workings of subgraphs
        app_graph = graph.get_graph(xray=True)
        
        # Render the graph as a PNG binary
        # Uses the default Mermaid renderer (requires internet for API or local install)
        png_data = app_graph.draw_mermaid_png()
        
        # Define output path
        output_file = "architecture_diagram.png"
        
        # Write binary data to disk
        with open(output_file, "wb") as f:
            f.write(png_data)
            
        print(f">>> ✅ Success! Saved diagram to '{output_file}'")
        
    except Exception as e:
        print(f">>> ❌ Failed to generate graph: {e}")
        print("Tip: Ensure you have internet access or the necessary graphviz/grandalf libraries installed.")

if __name__ == "__main__":
    generate_graph_image()