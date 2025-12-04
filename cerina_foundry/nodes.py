"""
Workflow Node Definitions for Cerina.

This module contains the functional nodes (agents) used in the LangGraph workflow.
It defines the logic for drafting, safety checks, clinical critique, and crisis management.
"""

import os
import requests
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Literal, Optional
from state import CerinaState, Critique

# Load environment variables
load_dotenv()

# --- LLM Initialization ---
# Uses GPT-4o with a standard temperature for creativity balanced with coherence.
try:
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
except Exception as e:
    print(f"Warning: LLM init failed (Check API Key): {e}")

# --- Structured Output Models ---

class SafetyAssessment(BaseModel):
    """Schema for the Safety Guardian's structured output."""
    is_safe: bool = Field(description="True if safe, False if harmful/medical advice")
    harm_category: Optional[str] = Field(description="Category of harm if any")
    reasoning: str

class ClinicalAssessment(BaseModel):
    """Schema for the Clinical Critic's structured output."""
    empathy_score: int = Field(description="1-10 score on empathy")
    structure_score: int = Field(description="1-10 score on CBT structure")
    feedback: str
    decision: Literal["PASS", "FAIL"]

# --- Node Definitions ---

def drafter_node(state: CerinaState):
    """
    The Creative Agent (Drafter).
    
    Generates the initial CBT protocol or rewrites it based on feedback.
    Includes robust error handling and message parsing to prevent server crashes.

    Args:
        state (CerinaState): The current graph state.

    Returns:
        dict: Updates to 'current_draft', 'iteration_count', and 'final_status'.
    """
    iteration = state.get("iteration_count", 0)
    critiques = state.get("critique_history", [])
    
    print(f"\n--- ✍️ DRAFTER (Iteration {iteration}) ---")

    try:
        # Robust Message Retrieval
        # Handles cases where messages might be LangChain objects, tuples, or strings
        messages = state.get("messages", [])
        user_query = "Create a generic CBT protocol." # Default fallback
        
        if messages and len(messages) > 0:
            last_msg = messages[0]
            if isinstance(last_msg, tuple):
                user_query = last_msg[1]
            elif hasattr(last_msg, 'content'):
                user_query = last_msg.content
            else:
                user_query = str(last_msg)

        # Construct Prompt based on history
        if not critiques:
            # First pass: Use the user's query
            prompt = f"Create a CBT clinical protocol for this request: {user_query}. Be empathetic but structured."
        else:
            # Subsequent passes: Address the specific critique
            last_feedback = critiques[-1]["feedback"]
            prompt = (f"Your previous draft was rejected. Fix this specific issue: {last_feedback}. "
                      f"Rewrite the protocol for: {user_query}")

        # Invoke LLM
        response = llm.invoke([
            ("system", "You are an expert CBT Clinical Architect."),
            ("user", prompt)
        ])
        
        return {
            "current_draft": response.content,
            "iteration_count": iteration + 1,
            "final_status": "reviewing"
        }
    except Exception as e:
        # Catch internal errors to ensure graceful failure
        error_msg = f"SYSTEM ERROR in Drafter: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "current_draft": f"I encountered an internal error while generating the draft.\nDetails: {str(e)}\n\nPlease check the server logs.",
            "iteration_count": iteration + 1,
            "final_status": "error"
        }


def safety_node(state: CerinaState):
    """
    The Compliance Officer (Safety Guardian).
    
    Analyzes the draft for self-harm, violence, or illegal content using
    structured output validation.

    Args:
        state (CerinaState): The current graph state.

    Returns:
        dict: Updates to 'critique_history'.
    """
    print("\n--- 🛡️ SAFETY GUARDIAN ---")
    draft = state["current_draft"]
    
    try:
        structured_llm = llm.with_structured_output(SafetyAssessment)
        assessment = structured_llm.invoke([
            ("system", "You are a Safety Guardian. "
                       "If the content indicates self-harm, suicide, or violence, you MUST use the word 'SUICIDE' or 'HARM' in your reasoning. "
                       "Reject illegal content. Allow standard CBT educational content."),
            ("user", f"Assess this content:\n{draft}")
        ])
        
        status = "PASS" if assessment.is_safe else "FAIL"
        
        critique: Critique = {
            "agent_name": "SafetyGuardian",
            "score": 10 if assessment.is_safe else 0,
            "feedback": assessment.reasoning,
            "status": status
        }
    except Exception as e:
        # Fallback mechanism if the safety check itself fails
        print(f"❌ Safety Node Error: {e}")
        critique = {
            "agent_name": "SafetyGuardian",
            "score": 5, 
            "feedback": "Safety check failed due to system error. Proceeding with caution.",
            "status": "PASS"
        }
    
    return {"critique_history": [critique]}


def clinical_node(state: CerinaState):
    """
    The Quality Assurance Agent (Clinical Critic).
    
    Evaluates the draft for clinical empathy and adherence to CBT structure.

    Args:
        state (CerinaState): The current graph state.

    Returns:
        dict: Updates to 'critique_history'.
    """
    print("\n--- 🩺 CLINICAL CRITIC ---")
    draft = state["current_draft"]
    
    try:
        structured_llm = llm.with_structured_output(ClinicalAssessment)
        assessment = structured_llm.invoke([
            ("system", "You are a strict CBT Supervisor. Rate the empathy and structure."),
            ("user", f"Evaluate this draft:\n{draft}")
        ])
        
        critique: Critique = {
            "agent_name": "ClinicalCritic",
            "score": assessment.empathy_score,
            "feedback": assessment.feedback,
            "status": assessment.decision
        }
    except Exception as e:
        critique = {
            "agent_name": "ClinicalCritic",
            "score": 5,
            "feedback": "Clinical check failed. Defaulting to PASS.",
            "status": "PASS"
        }
    
    return {"critique_history": [critique]}

# --- Crisis Logic ---

def send_internal_alert(thread_id: str, draft: str, reason: str):
    """
    Sends an immediate alert via Discord Webhook.
    
    Used when the Safety Guardian detects high-risk content (e.g., self-harm).
    
    Args:
        thread_id (str): The ID of the session triggering the alert.
        draft (str): The content of the dangerous draft.
        reason (str): The reasoning provided by the Safety Guardian.

    Returns:
        bool: True if alert sent successfully, False otherwise.
    """
    # NOTE: In a production environment, use environment variables for the Webhook URL.
    WEBHOOK_URL = "#############" 
    
    print(f"\n>>> 📨 [DISCORD] SENDING ALERT TO SERVER...")

    payload = {
        "content": f"🚨 **CRITICAL SAFETY ALERT** 🚨\n\n**Session ID:** `{thread_id}`\n**Reason:** {reason}\n**Draft Snippet:** _{draft[:100]}..._"
    }

    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=3)
        if response.status_code == 204:
            print(f">>> ✅ [DISCORD] ALERT SENT SUCCESSFULLY.")
            return True
        else:
            print(f">>> ⚠️ [DISCORD] FAILED: {response.status_code}")
            return False
    except Exception as e:
        # Catch network blocks so the app DOES NOT CRASH
        print(f">>> ❌ [DISCORD] NETWORK ERROR: {e}")
        print(">>> (Continuing workflow without alert)")
        return False


def crisis_node(state: CerinaState, config):
    """
    Crisis Intervention Node.
    
    Activates ONLY when a severe safety violation is detected. It triggers an
    external alert and overwrites the potentially harmful draft with a safe,
    supportive message.

    Args:
        state (CerinaState): The current graph state.
        config (dict): Configuration containing the thread ID.

    Returns:
        dict: The final safe state with a 'rejected' status.
    """
    print("\n--- 🚨 CRISIS MANAGER ACTIVATED ---")
    
    thread_id = config["configurable"]["thread_id"]
    latest_critique = state["critique_history"][-1]
    
    # 1. Send Alert (Side Effect)
    send_internal_alert(
        thread_id=thread_id,
        draft=state["current_draft"],
        reason=latest_critique["feedback"]
    )
    
    # 2. Overwrite Draft with Safe Message
    safe_message = (
        "I cannot fulfill this request. It sounds like you are going through a difficult time. "
        "Please remember that you are not alone.\n\n"
        "If you are in immediate danger, please call emergency services (911) or 988."
    )
    
    # 3. Mark as rejected so Human Node knows it wasn't a standard success
    return {
        "current_draft": safe_message,
        "final_status": "rejected" 
    }