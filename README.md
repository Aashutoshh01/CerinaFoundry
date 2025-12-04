# Cerina Foundry 🏥

**An Agentic Workflow for Clinical Protocol Generation**

![Architecture Diagram](cerina_foundry/architecture_diagram.png)
## 📖 Overview

**Cerina Foundry** is a specialized multi-agent AI system designed to assist mental health professionals in drafting **Cognitive Behavioral Therapy (CBT)** clinical protocols. Unlike standard LLM interactions, Cerina employs a "Foundry" of specialized agents that collaborate, critique, and refine clinical content before it ever reaches a human for final approval.

The system prioritizes **safety** and **clinical accuracy** through a rigorous Human-in-the-Loop (HITL) architecture, ensuring that no AI-generated medical advice is finalized without professional oversight.

### 🎥 [![Watch the Cerina Foundry Demo](./cerina_foundry/cover_photo.png)]([YOUR_VIDEO_LINK_HERE](https://drive.google.com/file/d/1JVs_IvuoTh7UXbgM4IEMntNBppH-Fzy4/view?usp=sharing))

*(Click the image above to watch the full system demonstration)*

---

## 🤖 The Agent Roster

The workflow is orchestrated using **LangGraph**, consisting of four distinct agents:

1.  **✍️ The Drafter (Creative Agent)**
    * **Role:** Generates the initial clinical protocol and rewrites drafts based on feedback.
    * **Behavior:** Uses a temperature of 0.7 for creativity. It is context-aware; if a draft is rejected, it analyzes the specific critique history to fix the errors in the next iteration.

2.  **🛡️ Safety Guardian (Compliance Agent)**
    * **Role:** The first line of defense. It analyzes content for self-harm, violence, or illegal advice.
    * **Mechanism:** Uses **Structured Output** validation. If high-risk content (e.g., suicide ideation) is detected, it bypasses standard loops and immediately triggers the *Crisis Manager*.

3.  **🩺 Clinical Critic (QA Agent)**
    * **Role:** Acts as a clinical supervisor. It scores drafts on "Empathy" and "CBT Structure" (1-10 scale).
    * **Mechanism:** If the score is below threshold, it rejects the draft and sends it back to the *Drafter* with actionable clinical feedback.

4.  **🚨 Crisis Manager (Intervention Agent)**
    * **Role:** Activates *only* during severe safety events.
    * **Action:** It overwrites the generated text with a safe, supportive resource message (e.g., helpline numbers) and sends a real-time **Discord Webhook** alert to the engineering/medical team.

---

## 🧠 System Architecture & State Logic

This project demonstrates advanced state management and fault tolerance.

### 1. Human-in-the-Loop (HITL)
The workflow is designed to explicitly pause at the `human_approval` node using LangGraph's **`interrupt`** mechanism.
* Agents refine the draft until it passes automated checks.
* The system pauses execution and waits.
* The Human (via the React UI or MCP) reviews the draft.
* **Feedback Loop:** If rejected, the human's feedback is injected into the state, and the *Drafter* attempts a rewrite.

### 2. SQLite Persistence (Fault Tolerance)
We utilize `SqliteSaver` as a checkpointer to persist the graph state after every node execution.
* **Why is this critical?** In standard web apps, refreshing the page often kills the active process.
* **In Cerina Foundry:** If a user generates a draft and refreshes the browser (or the server restarts), the session is **not lost**. The frontend re-fetches the state using the `thread_id` from the SQLite database, resuming the workflow exactly where it left off.

### 3. Model Context Protocol (MCP)
The system exposes an MCP Server (`mcp_server.py`), allowing external AI clients (like Claude Desktop or Cursor) to:
* Trigger protocol generation remotely.
* Receive "Approval Required" interrupts.
* Submit reviews directly from the external client environment.

---

## 🛠️ Tech Stack

* **Orchestration:** LangGraph, LangChain
* **LLM:** OpenAI GPT-4o
* **Backend:** FastAPI, Python 3.11
* **Frontend:** React, Vite, TailwindCSS, Lucide Icons
* **Persistence:** SQLite
* **Integration:** Discord Webhooks (Alerts), Model Context Protocol (MCP)

---

## 🚀 Installation & Setup

### 1. Environment Setup
The project requires Python 3.11.

```bash
# Create and activate environment
conda create -n cerina python=3.11
conda activate cerina
