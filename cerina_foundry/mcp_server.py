"""
Model Context Protocol (MCP) Server for Cerina.

This module exposes the Cerina clinical workflow as a set of tools compatible with
the Model Context Protocol. It allows external MCP clients (such as LLM interfaces)
to trigger the clinical protocol generation and handle the human-in-the-loop
review process remotely.
"""

import sys
import io
import uuid
from mcp.server.fastmcp import FastMCP
from langgraph.types import Command

from graph import graph

# Ensure UTF-8 encoding for Windows terminals to prevent encoding errors
# during standard output operations.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Initialize MCP Server
mcp = FastMCP("Cerina Foundry")

@mcp.tool()
async def generate_cbt_protocol(topic: str) -> str:
    """
    Generates a CBT Clinical Protocol for a specific mental health topic.
    
    Initiates the workflow and runs until the first human approval interrupt.
    
    Args:
        topic (str): The mental health topic or condition (e.g., "Social Anxiety").

    Returns:
        str: A status message containing the initial draft and the session ID,
             requesting human approval.
    """
    # Create a unique session ID for this request
    thread_id = f"mcp_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"--- MCP Request: {topic} (Thread: {thread_id}) ---")

    # Initialize state matching the structure expected by the Drafter node
    initial_state = {
        "messages": [("user", topic)], 
        "iteration_count": 0, 
        "critique_history": [],
        "current_draft": ""
    }
    
    try:
        # Run the graph synchronously until it hits the "human_approval" interrupt
        graph.invoke(initial_state, config)
        
        # Inspect the state to determine pause location
        snapshot = graph.get_state(config)
        
        # Check if paused at the human_approval node
        if snapshot.next and snapshot.next[0] == 'human_approval':
            interrupt_val = snapshot.tasks[0].interrupts[0].value
            draft = interrupt_val["draft"]
            
            return (
                f"✅ Protocol Draft Generated for '{topic}'\n\n"
                f"--- DRAFT PREVIEW ---\n{draft[:200]}...\n\n"
                f"--- STATUS ---\n"
                f"System PAUSED for Human Approval.\n"
                f"Session ID: {thread_id}\n"
                f"ACTION REQUIRED: Please approve this in the Cerina Dashboard or via the review tool."
            )
        
        return "System finished without producing a draft (or encountered an unexpected state)."

    except Exception as e:
        return f"Error executing workflow: {str(e)}"
    

@mcp.tool()
async def review_cbt_protocol(thread_id: str, action: str, feedback: str = None) -> str:
    """
    Approves or Rejects a paused protocol draft.

    Resumes the workflow execution based on the human decision.

    Args:
        thread_id (str): The session ID provided by the generate tool.
        action (str): The decision, either "approve" or "reject".
        feedback (str, optional): Specific feedback if rejecting. Defaults to None.

    Returns:
        str: The final status of the protocol or the new draft if a rewrite was triggered.
    """
    print(f"--- MCP Review: {action.upper()} (Thread: {thread_id}) ---")
    
    config = {"configurable": {"thread_id": thread_id}}
    
    resume_payload = {
        "action": action.lower(),
        "feedback": feedback
    }
    
    try:
        # Resume the graph with the human decision
        graph.invoke(Command(resume=resume_payload), config)
        
        # Check the resulting state
        snapshot = graph.get_state(config)
        
        # Case 1: Graph finished (Approved)
        if not snapshot.next:
            return f"✅ Protocol Successfully APPROVED and Finalized for Session {thread_id}."
        
        # Case 2: Graph loop back (Rejected -> New Draft)
        if snapshot.next and snapshot.next[0] == 'human_approval':
             interrupt_val = snapshot.tasks[0].interrupts[0].value
             draft = interrupt_val["draft"]
             return (
                 f"🔄 Protocol REJECTED. The agents have rewritten the draft.\n\n"
                 f"--- NEW DRAFT ---\n{draft[:200]}...\n\n"
                 f"Action Required: Please approve or reject this new version."
             )
             
        return "System processed the review."

    except Exception as e:
        return f"Error submitting review: {str(e)}"


if __name__ == "__main__":
    mcp.run()