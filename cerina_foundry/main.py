"""
Main Execution Entry Point for Cerina Workflow.

This script initializes the LangGraph thread, invokes the initial graph state,
and handles the human-in-the-loop interaction pattern by inspecting interrupts
and resuming execution based on console input.
"""

from graph import graph
from langgraph.types import Command

# Define the configuration for the execution thread
config = {"configurable": {"thread_id": "session_1"}}

print(">>> STARTING GRAPH EXECUTION")

# Initiate the graph execution with an empty state
initial_run = graph.invoke(
    {"messages": [], "iteration_count": 0, "critique_history": []}, 
    config=config
)

# Retrieve the current state to check for interruptions
# The graph is designed to pause at the 'human_approval' node
snapshot = graph.get_state(config)

if snapshot.next and snapshot.next[0] == 'human_approval':
    print("\n>>> GRAPH PAUSED FOR HUMAN INTERRUPT")
    
    # Extract the value provided by the interrupt in the human_approval_node
    interrupt_value = snapshot.tasks[0].interrupts[0].value
    
    # Display a snippet of the draft for context
    print(f"DRAFT GENERATED:\n{interrupt_value['draft'][:100]}...") 

    # Capture user input from the console to simulate human review
    user_decision = input("\n[Human] Type 'approve' or 'reject': ")
    
    print("\n>>> RESUMING GRAPH")
    
    # Resume the graph execution with the user's decision and feedback
    # The 'Command' object passes this data back to the interrupted node
    final_run = graph.invoke(
        Command(resume={"action": user_decision, "feedback": "Make it shorter."}), 
        config=config
    )
    
    print("\n>>> FINAL STATE:")
    print(final_run["final_status"])

else:
    print("Graph finished without interrupt (Did checks fail?)")