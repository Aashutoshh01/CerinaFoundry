import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { ShieldAlert, Stethoscope, CheckCircle, XCircle, Play, Loader2, Bot, History } from 'lucide-react';

// --- Types ---

/**
 * Represents a single critique from an AI agent.
 */
interface Critique {
  agent_name: string;
  score: number;
  feedback: string;
  status: 'PASS' | 'FAIL';
}

/**
 * Represents the current state of the generation workflow.
 */
interface WorkflowState {
  status: 'IDLE' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'ERROR';
  draft: string;
  critiques: Critique[];
  final_status?: string;
}

// --- Configuration ---
const API_URL = 'http://127.0.0.1:8000';

/**
 * Main Application Component for Cerina Foundry.
 * Handles the interaction between the user, the AI workflow, and human review steps.
 */
function App() {
  // State Management
  const [threadId, setThreadId] = useState<string>('');
  const [query, setQuery] = useState('Create a hierarchy for fear of public speaking');
  const [rejectionFeedback, setRejectionFeedback] = useState('');
  
  const [state, setState] = useState<WorkflowState>({
    status: 'IDLE',
    draft: '',
    critiques: []
  });

  // Reference to manage the polling interval ID to prevent memory leaks
  const pollInterval = useRef<number | null>(null);

  /**
   * Effect: Session Restoration.
   * On component mount, checks LocalStorage for an existing session ID and query
   * to restore the user's previous context.
   */
  useEffect(() => {
    const savedSession = localStorage.getItem('cerina_session_id');
    const savedQuery = localStorage.getItem('cerina_query');

    if (savedSession) {
      console.log("🔄 Found saved session:", savedSession);
      setThreadId(savedSession);
      if (savedQuery) setQuery(savedQuery);
      refreshState(savedSession);
    }
  }, []);

  /**
   * Effect: Cleanup.
   * Ensures polling is stopped when the component unmounts.
   */
  useEffect(() => {
    return () => stopPolling();
  }, []);

  /**
   * Fetches the latest workflow state from the backend.
   * @param tid - The thread ID to fetch state for.
   */
  const refreshState = async (tid: string) => {
    try {
      const res = await axios.get(`${API_URL}/state/${tid}`);
      handleResponse(res.data);
    } catch (err) {
      console.error("Failed to restore session:", err);
    }
  };

  /**
   * Starts a polling interval to periodically fetch the workflow state.
   * Used to update the UI while the backend agents are processing.
   * @param tid - The thread ID to poll.
   */
  const startPolling = (tid: string) => {
    if (pollInterval.current) clearInterval(pollInterval.current);
    
    pollInterval.current = window.setInterval(async () => {
      await refreshState(tid);
    }, 2000); // Poll every 2 seconds
  };

  /**
   * Stops the active polling interval.
   */
  const stopPolling = () => {
    if (pollInterval.current) {
      clearInterval(pollInterval.current);
      pollInterval.current = null;
    }
  };

  /**
   * Initiates a new AI workflow session.
   * Generates a new thread ID, persists it, and calls the backend run endpoint.
   */
  const startWorkflow = async () => {
    const newThreadId = `session_${Math.floor(Math.random() * 100000)}`;
    setThreadId(newThreadId);
    
    // Persist session details
    localStorage.setItem('cerina_session_id', newThreadId);
    localStorage.setItem('cerina_query', query);

    setState(prev => ({ ...prev, status: 'RUNNING', critiques: [], draft: '' }));
    startPolling(newThreadId);

    try {
      const res = await axios.post(`${API_URL}/run`, {
        thread_id: newThreadId,
        user_query: query
      });
      handleResponse(res.data);
    } catch (err) {
      console.error(err);
      setState(prev => ({ ...prev, status: 'ERROR' }));
      stopPolling();
    }
  };

  /**
   * Submits a human review decision (approve or reject) to the backend.
   * @param action - 'approve' to finalize, 'reject' to request changes.
   */
  const submitReview = async (action: 'approve' | 'reject') => {
    setState(prev => ({ ...prev, status: 'RUNNING' }));
    startPolling(threadId); // Resume polling for post-review updates

    try {
      const res = await axios.post(`${API_URL}/human-review`, {
        thread_id: threadId,
        action: action,
        feedback: action === 'reject' ? rejectionFeedback : null 
      });
      handleResponse(res.data);
      setRejectionFeedback(''); 
    } catch (err) {
      console.error(err);
      setState(prev => ({ ...prev, status: 'ERROR' }));
      stopPolling();
    }
  };

  /**
   * Centralized handler for mapping backend responses to UI state.
   * Determines when to stop polling based on workflow status.
   * @param data - The JSON response from the backend.
   */
  const handleResponse = (data: any) => {
    // Map backend status to UI status
    let uiStatus: WorkflowState['status'] = 'RUNNING';
    
    if (data.status === 'PAUSED') uiStatus = 'PAUSED';
    else if (data.status === 'COMPLETED') uiStatus = 'COMPLETED';
    
    // Stop polling if waiting for human input or if workflow is finished
    if (uiStatus === 'PAUSED' || uiStatus === 'COMPLETED') {
        stopPolling();
    }

    setState(prev => ({
      status: uiStatus,
      draft: data.draft || data.final_draft || prev.draft,
      critiques: data.critiques || prev.critiques || [], // Preserve existing critiques if response is empty
      final_status: data.final_status
    }));
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans p-8">
      <div className="max-w-6xl mx-auto grid grid-cols-12 gap-8 h-[90vh]">
        
        {/* --- LEFT PANEL: Agent Logic & Controls --- */}
        <div className="col-span-4 bg-white rounded-xl shadow-sm border border-slate-200 p-6 flex flex-col overflow-hidden">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold flex items-center gap-2 text-slate-800">
              <Bot className="w-6 h-6 text-blue-600" />
              Cerina Foundry
            </h2>   
            
            <button 
                onClick={() => {
                    localStorage.removeItem('cerina_session_id');
                    localStorage.removeItem('cerina_query');
                    window.location.reload();
                }}
                className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1"
                title="Start New Session"
            >
                <History className="w-3 h-3" /> New
            </button>
          </div>
          
          <div className="mb-6 pl-9 -mt-2">
            <p className="text-xs font-semibold text-slate-400">
              Project by <span className="text-blue-600 font-bold">Aashutosh Joshi</span>
            </p>
          </div>

          {/* Input Area */}
          <div className="mb-6 space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">Mission Objective</label>
            <textarea 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full p-3 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none resize-none bg-slate-50"
              rows={3}
              disabled={state.status === 'RUNNING'}
            />
            <button 
              onClick={startWorkflow}
              disabled={state.status === 'RUNNING'}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {state.status === 'RUNNING' ? (
                <>
                  <Loader2 className="animate-spin w-4 h-4" />
                  Agents Working...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  Start Agents
                </>
              )}
            </button>
          </div>

          {/* Critique Stream */}
          <div className="flex-1 overflow-y-auto space-y-3 pr-1 custom-scrollbar">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider sticky top-0 bg-white pb-2">
              Agent Audit Log
            </h3>
            
            {state.critiques.length === 0 && state.status === 'RUNNING' && (
               <div className="text-center py-8 text-slate-400 animate-pulse">
                 <p className="text-sm">Agents are debating...</p>
               </div>
            )}

            {state.critiques.map((critique, idx) => (
              <div key={idx} className={`p-3 rounded-lg border-l-4 shadow-sm ${critique.status === 'PASS' ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'}`}>
                <div className="flex justify-between items-center mb-1">
                  <div className="flex items-center gap-1.5">
                    {critique.agent_name === 'SafetyGuardian' ? <ShieldAlert className="w-4 h-4 text-slate-700"/> : <Stethoscope className="w-4 h-4 text-slate-700"/>}
                    <span className="font-semibold text-xs text-slate-700 uppercase">{critique.agent_name}</span>
                  </div>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${critique.status === 'PASS' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'}`}>
                    {critique.status} {critique.score}/10
                  </span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">{critique.feedback}</p>
              </div>
            ))}
          </div>
        </div>

        {/* --- RIGHT PANEL: The Artifact --- */}
        <div className="col-span-8 bg-white rounded-xl shadow-lg border border-slate-200 flex flex-col overflow-hidden relative">
          
          {/* Header */}
          <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 backdrop-blur">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${state.status === 'PAUSED' ? 'bg-amber-500 animate-pulse' : state.status === 'COMPLETED' ? 'bg-green-500' : 'bg-slate-300'}`}></span>
              <span className="text-xs font-bold uppercase text-slate-500 tracking-wide">
                {state.status === 'PAUSED' ? 'Waiting for Human Approval' : state.status}
              </span>
            </div>
            {state.status === 'COMPLETED' && (
               <span className="text-xs font-bold text-green-600 flex items-center gap-1">
                 <CheckCircle className="w-3 h-3" /> Published
               </span>
            )}
          </div>

          {/* Content Area */}
          <div className="flex-1 p-8 overflow-y-auto prose prose-slate max-w-none">
            {state.draft ? (
              <div className="whitespace-pre-wrap font-serif text-slate-800 leading-7">
                {state.draft}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-300 gap-4">
                <Bot className="w-12 h-12 opacity-20" />
                <p className="text-sm">Generated clinical protocol will appear here.</p>
              </div>
            )}
          </div>

          {/* Action Bar (Only visible when PAUSED) */}
          {state.status === 'PAUSED' && (
            <div className="p-4 bg-white border-t border-slate-200 flex flex-col gap-3 animate-in slide-in-from-bottom-4 duration-300 shadow-xl z-20">
              
              <input 
                type="text" 
                placeholder="If rejecting, explain what needs to be fixed..."
                value={rejectionFeedback}
                onChange={(e) => setRejectionFeedback(e.target.value)}
                className="w-full p-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-red-500 outline-none"
              />

              <div className="flex gap-4">
                <button 
                  onClick={() => submitReview('reject')}
                  className="flex-1 py-3 px-4 border-2 border-red-100 text-red-600 hover:bg-red-50 hover:border-red-200 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all"
                >
                  <XCircle className="w-5 h-5" />
                  Reject & Retry
                </button>
                <button 
                  onClick={() => submitReview('approve')}
                  className="flex-[2] py-3 px-4 bg-green-600 hover:bg-green-700 text-white rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-green-200 transition-all hover:scale-[1.01]"
                >
                  <CheckCircle className="w-5 h-5" />
                  Approve Protocol
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;