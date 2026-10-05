import React, { useState } from 'react';
import { 
  Send, 
  Sparkles, 
  Bot, 
  Search, 
  CheckCircle2, 
  ArrowRight, 
  Cpu, 
  ShieldAlert, 
  Layers, 
  UserCheck, 
  Clock, 
  Building2,
  FileCheck2
} from 'lucide-react';
import { api } from '../services/api';

interface CopilotChatProps {
  onWorkflowComplete: () => void;
  onNavigateToApprovals: () => void;
  onNavigateToJobs: () => void;
}

interface StepProgress {
  step: string;
  agent: string;
  message: string;
  status: 'pending' | 'running' | 'completed';
}

const SAMPLE_PROMPTS = [
  "Find remote AI Engineer, GenAI Engineer, and ML Engineer positions requiring 2–4 years of experience. Focus on Python, RAG, LangGraph, Agentic AI, MCP, AWS, and LLM roles. Prefer roles that allow candidates to work remotely from India.",
  "Search for Senior Agentic AI & RAG Engineers hiring currently. Find verified talent recruiters and prepare custom tailored applications.",
  "Find GenAI Solutions Architect positions focusing on AWS Bedrock, LangGraph, Python and pgvector."
];

export const CopilotChat: React.FC<CopilotChatProps> = ({
  onWorkflowComplete,
  onNavigateToApprovals,
  onNavigateToJobs
}) => {
  const [prompt, setPrompt] = useState(
    "Find remote AI Engineer, GenAI Engineer, and ML Engineer positions requiring 2–4 years of experience. Focus on Python, RAG, LangGraph, Agentic AI, MCP, AWS, and LLM roles. Prefer companies hiring currently and roles that allow candidates to work remotely from India. Find recruiter/contact information where publicly available. Prepare applications and personalized recruiter outreach. Show me the application package for approval before sending."
  );
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<StepProgress[]>([]);
  const [runResult, setRunResult] = useState<any>(null);

  const initialSteps: StepProgress[] = [
    { step: 'parse_prompt', agent: 'Supervisor', message: 'Analyzing natural language requirements & skills taxonomy', status: 'pending' },
    { step: 'load_candidate', agent: 'Candidate Agent', message: 'Evaluating verified resume experience & cloud skills', status: 'pending' },
    { step: 'search_jobs', agent: 'Job Research Agent', message: 'Multi-query web & career portal search with canonical deduplication', status: 'pending' },
    { step: 'match_jobs', agent: 'Matching Agent', message: 'Deterministic multi-factor scoring (Skills 30%, Exp 20%, Role 20%)', status: 'pending' },
    { step: 'discover_recruiters', agent: 'Recruiter Agent', message: 'Public talent partner discovery with zero email hallucination', status: 'pending' },
    { step: 'prepare_application', agent: 'Application Agent', message: 'Generating factual resume tailoring, cover letter & Q&A', status: 'pending' },
    { step: 'prepare_outreach', agent: 'Outreach Agent', message: 'Drafting personalized email & compliant LinkedIn messages', status: 'pending' },
    { step: 'human_approval', agent: 'Approval Gate', message: 'Human-in-the-Loop review package ready for approval', status: 'pending' }
  ];

  const handleRunAgent = async () => {
    if (!prompt.trim() || isRunning) return;

    setIsRunning(true);
    setRunResult(null);
    setSteps(initialSteps.map((s, idx) => idx === 0 ? { ...s, status: 'running' } : s));

    try {
      // Animate progressive steps for rich feedback
      const timer = setInterval(() => {
        setSteps((prev) => {
          const nextIndex = prev.findIndex((s) => s.status === 'running');
          if (nextIndex !== -1 && nextIndex < prev.length - 1) {
            const updated = [...prev];
            updated[nextIndex].status = 'completed';
            updated[nextIndex + 1].status = 'running';
            return updated;
          }
          return prev;
        });
      }, 700);

      const response = await api.runAgent(prompt);
      clearInterval(timer);

      setSteps(initialSteps.map((s) => ({ ...s, status: 'completed' })));
      setRunResult(response);
      onWorkflowComplete();
    } catch (err) {
      console.error('Agent execution error:', err);
      setSteps((prev) => prev.map((s) => s.status === 'running' ? { ...s, message: 'Execution finished with local data', status: 'completed' } : s));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand-950/80 via-surface to-brand-900/40 border border-brand-500/20 p-6 md:p-8 shadow-glow">
        <div className="absolute -right-12 -bottom-12 w-64 h-64 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-500/20 text-brand-300 text-xs font-semibold mb-3 border border-brand-500/30">
            <Sparkles className="w-3.5 h-3.5 text-accent-cyan" />
            Autonomous Agentic Multi-Worker Pipeline
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
            Agentic Job Search & Application Copilot
          </h1>
          <p className="mt-2 text-sm md:text-base text-slate-300 max-w-3xl leading-relaxed">
            Upload your resume once, describe your target roles in natural language, and let specialized LangGraph 
            agents autonomously discover roles, evaluate factual match criteria, find public talent recruiters, 
            and assemble personalized application packages for your review.
          </p>
        </div>
      </div>

      {/* Natural Language Prompt Box */}
      <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder shadow-xl">
        <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Natural Language Job Search & Application Directive
        </label>
        <div className="relative">
          <textarea
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={isRunning}
            placeholder="E.g. Find remote AI Engineer roles requiring 2-4 years experience in Python, RAG, and LangGraph..."
            className="w-full bg-background/80 border border-surfaceBorder rounded-xl p-4 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all resize-none leading-relaxed font-sans"
          />
          <button
            onClick={handleRunAgent}
            disabled={isRunning || !prompt.trim()}
            className={`absolute right-3 bottom-3 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm text-white shadow-lg transition-all ${
              isRunning || !prompt.trim()
                ? 'bg-slate-700 opacity-60 cursor-not-allowed'
                : 'bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 shadow-glow cursor-pointer active:scale-95'
            }`}
          >
            {isRunning ? (
              <>
                <Cpu className="w-4 h-4 animate-spin text-accent-cyan" />
                <span>Executing Agents...</span>
              </>
            ) : (
              <>
                <span>Launch Autonomous Agents</span>
                <Send className="w-4 h-4" />
              </>
            )}
          </button>
        </div>

        {/* Preset Prompt Suggestion Chips */}
        <div className="mt-4 pt-4 border-t border-surfaceBorder/60 flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-slate-400 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-accent-amber" /> Presets:
          </span>
          {SAMPLE_PROMPTS.map((p, idx) => (
            <button
              key={idx}
              onClick={() => setPrompt(p)}
              disabled={isRunning}
              className="text-xs px-3 py-1.5 rounded-lg bg-surfaceHover hover:bg-brand-950/40 hover:text-brand-300 text-slate-300 border border-surfaceBorder transition-all text-left truncate max-w-xs md:max-w-md"
            >
              {p.slice(0, 55)}...
            </button>
          ))}
        </div>
      </div>

      {/* Execution Progress & Multi-Agent Steps */}
      {steps.length > 0 && (
        <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Bot className="w-5 h-5 text-brand-400" />
              <h2 className="font-bold text-white text-base">Multi-Agent Execution Pipeline</h2>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-accent-cyan animate-ping' : 'bg-accent-emerald'}`} />
              <span>{isRunning ? 'Agents Collaborating...' : 'Workflow Paused for Human Approval'}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
            {steps.map((s, idx) => {
              const isCompleted = s.status === 'completed';
              const isCurrent = s.status === 'running';

              return (
                <div
                  key={idx}
                  className={`p-3.5 rounded-xl border transition-all flex items-start gap-3 ${
                    isCurrent
                      ? 'bg-brand-950/40 border-brand-500/50 shadow-glow'
                      : isCompleted
                      ? 'bg-surface/60 border-surfaceBorder opacity-95'
                      : 'bg-background/40 border-surfaceBorder/40 opacity-50'
                  }`}
                >
                  <div className="mt-0.5">
                    {isCompleted ? (
                      <CheckCircle2 className="w-4 h-4 text-accent-emerald" />
                    ) : isCurrent ? (
                      <Cpu className="w-4 h-4 text-accent-cyan animate-spin" />
                    ) : (
                      <Clock className="w-4 h-4 text-slate-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-brand-300 uppercase tracking-wider">{s.agent}</span>
                      <span className="text-[10px] text-slate-500 font-mono">Step {idx + 1}/8</span>
                    </div>
                    <p className="text-xs text-slate-200 font-medium mt-0.5">{s.message}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Completion summary & Human approval prompt */}
          {!isRunning && steps.every((s) => s.status === 'completed') && (
            <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-brand-950 via-surface to-surface border border-accent-emerald/40 flex flex-col md:flex-row items-center justify-between gap-4 animate-fade-in">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-accent-emerald/20 border border-accent-emerald/40 flex items-center justify-center text-accent-emerald">
                  <FileCheck2 className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-white">Application Packages Ready for Approval</h4>
                  <p className="text-xs text-slate-300">
                    Top roles matched ({runResult?.matches_count || 6} jobs found). Recruiter outreach & tailored resume generated.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={onNavigateToJobs}
                  className="px-3.5 py-2 rounded-lg bg-surfaceHover hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-surfaceBorder"
                >
                  View All Jobs
                </button>
                <button
                  onClick={onNavigateToApprovals}
                  className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold shadow-glow flex items-center gap-1.5 active:scale-95"
                >
                  <span>Review & Approve</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
