"""
State Definitions for the Cerina Workflow.

This module defines the TypedDict structures used to manage the state of the 
LangGraph application. It defines the structure for agent critiques and the 
global graph state.
"""

from typing import TypedDict, Annotated, List, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class Critique(TypedDict):
    """
    Represents a single piece of feedback from an automated agent.
    
    Attributes:
        agent_name (str): The name of the agent providing feedback (e.g., 'SafetyGuardian').
        score (int): A numerical score (typically 0-10) indicating quality.
        feedback (str): The specific actionable feedback provided by the agent.
        status (Literal): Whether the draft passed or failed the check.
    """
    agent_name: str
    score: int
    feedback: str
    status: Literal["PASS", "FAIL"]

class CerinaState(TypedDict):
    """
    The central state object for the Cerina workflow.
    
    This dictionary is passed between nodes in the graph, tracking the conversation
    history, the artifact being generated, and the audit log of critiques.
    """
    # Tracks the conversation history using LangGraph's standard add_messages reducer
    messages: Annotated[list[BaseMessage], add_messages]
    
    # The current content of the clinical protocol being drafted
    current_draft: str
    
    # Circuit breaker to prevent infinite loops during self-correction
    iteration_count: int
    
    # An append-only log of all critiques received during the session.
    # The lambda function `lambda x, y: x + y` ensures new critiques are added to the list
    # rather than overwriting the existing ones.
    critique_history: Annotated[List[Critique], lambda x, y: x + y]
    
    # The current high-level status of the workflow
    final_status: Literal["drafting", "reviewing", "human_review", "approved", "rejected", "error"]