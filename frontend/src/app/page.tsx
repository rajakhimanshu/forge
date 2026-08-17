"use client";

import { useState, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Check, 
  Loader2, 
  Play, 
  TerminalSquare, 
  Command,
  LayoutDashboard,
  Search,
  CheckCircle2,
  Sparkles,
  Zap,
  Box,
  Target,
  BarChart3,
  Map,

  LucideIcon,
  Upload,
  FileText,
  X,
  AlertTriangle,
  Monitor,
  Wrench,
  Download,
  Server,
} from "lucide-react";

// Types & Config
const PHASES = [
  { id: "idea_analysis",     label: "Idea Analysis",  nodeKey: "idea_analysis_task",  icon: Sparkles },
  { id: "market_research",   label: "Market Research", nodeKey: "market_research_task", icon: Search },
  { id: "verdict",           label: "Verdict",         nodeKey: "verdict_task",         icon: CheckCircle2 },
  { id: "technical_rd",      label: "Tech R&D",        nodeKey: "technical_rd_task",    icon: Box },
  { id: "services",          label: "Services",        nodeKey: "service_resolver",     icon: Server },
  { id: "blueprint",         label: "Blueprint",       nodeKey: "blueprint_task",       icon: LayoutDashboard },
  { id: "build_steps",       label: "Build Steps",     nodeKey: "step_generator",       icon: Wrench },
  { id: "gtm",               label: "GTM",             nodeKey: "gtm",                  icon: Target },
  { id: "business",          label: "Business",        nodeKey: "business",             icon: BarChart3 },
  { id: "roadmap",           label: "Roadmap",         nodeKey: "roadmap",              icon: Map },
];

const EMPTY_HINTS: Record<string, { title: string; desc: string, icon: LucideIcon }> = {
  idea_analysis:   { title: "Awaiting Core Concept",   desc: "Submit your idea to analyze the core job-to-be-done, persona pain score, AI native potential, and graveyard analysis.", icon: Sparkles },
  market_research: { title: "Pending Market Scan",     desc: "Scans 5+ real competitors, India pricing ceiling, and exact communities where your first 50 users live.",            icon: Search },
  verdict:         { title: "Decision Engine Idle",    desc: "Awaits upstream data to calculate BUILD / PIVOT / SKIP based on uniqueness and feasibility.",                       icon: CheckCircle2 },
  technical_rd:    { title: "Architecture Unassigned", desc: "Recommends architecture, free-tier India tech stack, and monthly INR cost estimates.",                              icon: Box },
  services:        { title: "Services Pending",        desc: "Live Tavily research to pick the best free service for each infra need (OTP, payments, DB, storage…).",            icon: Server },
  blueprint:       { title: "Blueprint Uncharted",     desc: "Generates a numbered task list with exact AI prompts for each file to build.",                                       icon: LayoutDashboard },
  build_steps:     { title: "Build Steps Pending",     desc: "OS-aware SETUP STEPS (terminal commands) and CODING STEPS (AI prompts) generated from Blueprint + Services.",       icon: Wrench },
  gtm:             { title: "GTM Plan Pending",        desc: "Drafts cold outreach scripts, week-by-week actions, and viral mechanics.",                                          icon: Target },
  business:        { title: "Business Model Pending",  desc: "Structures pricing tiers, upgrade triggers, and revenue milestones in INR.",                                        icon: BarChart3 },
  roadmap:         { title: "Roadmap Unscheduled",     desc: "Maps a 30-day launch plan, money ask messages, and Day 30 pivoting logic.",                                         icon: Map },
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Environment profile type
type EnvOS    = "windows" | "mac" | "linux";
type EnvAICLI = "gemini" | "claude_code" | "cursor" | "copilot";
type EnvExp   = "beginner" | "intermediate" | "advanced";

export default function Home() {
  const [ideaConcept, setIdeaConcept] = useState("");
  const [ideaContext, setIdeaContext] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  
  // Layer 3 — Environment profile
  const [envOS,    setEnvOS]    = useState<EnvOS>("windows");
  const [envAICLI, setEnvAICLI] = useState<EnvAICLI>("gemini");
  const [envExp,   setEnvExp]   = useState<EnvExp>("intermediate");
  const [envNode,  setEnvNode]  = useState(false);
  const [envPy,    setEnvPy]    = useState(true);

  // Layer 5 — Docx download
  const [docxUrl, setDocxUrl] = useState<string | null>(null);

  // Intake State
  const [uiStep, setUiStep] = useState<"idle" | "loading_questions" | "answering" | "processing" | "complete">("idle");
  const [q1, setQ1] = useState("");
  const [a1, setA1] = useState("");
  const [q2, setQ2] = useState("");
  const [a2, setA2] = useState("");
  const [q3, setQ3] = useState("");
  const [a3, setA3] = useState("");

  const [activeTab, setActiveTab] = useState("idea_analysis");
  const [activePhaseNodeKey, setActivePhaseNodeKey] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("System idle. Awaiting input.");
  
  const [completePhases, setCompletePhases] = useState<Set<string>>(new Set());
  const [markdownOutputs, setMarkdownOutputs] = useState<Record<string, string>>({});
  const [verdictCard, setVerdictCard] = useState<{
    decision?: string;
    decision_reason?: string;
    your_edge?: string;
    kill_condition?: string;
    kill_timeline?: string;
    build_first?: string;
    do_tomorrow?: string;
    score?: number;
    confidence?: string;
  } | null>(null);
  // failedPhases: phaseId → error message string (never mixed with real output)
  const [failedPhases, setFailedPhases] = useState<Record<string, string>>({});
  const [logs, setLogs] = useState<string[]>([]);
  const evtRef = useRef<EventSource | null>(null);

  const appendLog = (msg: string) => setLogs(prev => [...prev.slice(-40), msg]);

  const handleGenerateQuestions = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ideaConcept.trim()) return;
    
    setUiStep("loading_questions");
    try {
      const formData = new FormData();
      formData.append("idea_concept", ideaConcept);
      formData.append("idea_context", ideaContext);
      
      const res = await fetch(`${API_BASE_URL}/api/forge/intake`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setQ1(data.q1 || "Who is the primary user? (Be specific)");
      setQ2(data.q2 || "What does the user currently do instead of your solution?");
      setQ3(data.q3 || "What is the one feature without which the whole product is useless?");
      setUiStep("answering");
    } catch (err) {
      console.error(err);
      setQ1("Who is the primary user? (Be specific)");
      setQ2("What does the user currently do instead of your solution?");
      setQ3("What is the one feature without which the whole product is useless?");
      setUiStep("answering");
    }
  };

  const handleRunForge = useCallback(async () => {
    if (!ideaConcept.trim() || !a1.trim() || !a2.trim() || !a3.trim()) return;
    if (evtRef.current) evtRef.current.close();

    setUiStep("processing");
    setIsProcessing(true);
    setIsComplete(false);
    setMarkdownOutputs({});
    setVerdictCard(null);
    setCompletePhases(new Set());
    setFailedPhases({});
    setDocxUrl(null);
    setLogs(["[system] Initialization started..."]);
    setStatusMessage("Connecting to FORGE backend...");
    setActivePhaseNodeKey("idea_analysis_task");
    setActiveTab("idea_analysis");

    try {
      // Step 1: Sharpen idea
      const sharpenData = new FormData();
      sharpenData.append("idea_concept", ideaConcept);
      sharpenData.append("q1", q1); sharpenData.append("a1", a1);
      sharpenData.append("q2", q2); sharpenData.append("a2", a2);
      sharpenData.append("q3", q3); sharpenData.append("a3", a3);
      
      const sharpenRes = await fetch(`${API_BASE_URL}/api/forge/sharpen`, {
        method: "POST",
        body: sharpenData,
      });
      const sharpenedJson = await sharpenRes.json();
      const sharpenedIdea = sharpenedJson.sharpened_idea;

      // Step 2: Start pipeline
      const formData = new FormData();
      formData.append("idea_concept", sharpenedIdea); // Use sharpened
      formData.append("idea_context", ideaContext);
      if (pdfFile) formData.append("pdf_file", pdfFile);
      
      formData.append("q1", q1); formData.append("a1", a1);
      formData.append("q2", q2); formData.append("a2", a2);
      formData.append("q3", q3); formData.append("a3", a3);

      // Layer 3 — environment profile fields
      formData.append("env_os",              envOS);
      formData.append("env_ai_cli",          envAICLI);
      formData.append("env_experience",      envExp);
      formData.append("env_node_installed",  String(envNode));
      formData.append("env_python_installed",String(envPy));

      const res = await fetch(`${API_BASE_URL}/api/forge/start`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      const es = new EventSource(`${API_BASE_URL}/api/forge/stream/${data.session_id}`);
      evtRef.current = es;

      es.onmessage = (event) => {
        const payload = JSON.parse(event.data);

        if (payload.type === "verdict_card") {
          setVerdictCard(payload.data);
          return;
        }

        if (payload.node === "complete" || payload.node === "error") {
          setIsProcessing(false);
          setIsComplete(payload.node === "complete");
          setUiStep(payload.node === "complete" ? "complete" : "idle");
          setStatusMessage(payload.status_message);
          setActivePhaseNodeKey(null);
          // Handle docx URL on completion
          if (payload.updates?.docx_url) {
            setDocxUrl(`${API_BASE_URL}${payload.updates.docx_url}`);
            appendLog(`[system] Build guide .docx ready for download`);
          }
          appendLog(`[system] ${payload.status_message}`);
          es.close();
          return;
        }

        setStatusMessage(payload.status_message);
        setActivePhaseNodeKey(payload.node);
        appendLog(`[${payload.node}] ${payload.status_message}`);

        if (payload.updates) {
          const nodePhase = PHASES.find(p => p.nodeKey === payload.node);

          // Handle service_bundle → Services tab
          if (payload.updates.services && typeof payload.updates.services === "string") {
            setMarkdownOutputs(prev => ({ ...prev, services: payload.updates.services }));
            setCompletePhases(prev => new Set([...prev, "services"]));
            appendLog(`[service_resolver] Services resolved`);
          }

          // Handle build_steps_summary → Build Steps tab
          if (payload.updates.build_steps_summary && typeof payload.updates.build_steps_summary === "string") {
            setMarkdownOutputs(prev => ({ ...prev, build_steps: payload.updates.build_steps_summary }));
            setCompletePhases(prev => new Set([...prev, "build_steps"]));
            appendLog(`[step_generator] Build steps generated`);
          }

          // Handle docx_ready event
          if (payload.updates.docx_ready?.download_url) {
            setDocxUrl(`${API_BASE_URL}${payload.updates.docx_ready.download_url}`);
            appendLog(`[docx_export] Build guide ready for download`);
          }

          if (nodePhase) {
            const updateValue = payload.updates[nodePhase.id] ?? payload.updates[nodePhase.nodeKey];

            if (updateValue && typeof updateValue === "object" && updateValue._failed === true) {
              const errMsg: string = updateValue._error_message ?? "Unknown error";
              setFailedPhases(prev => ({ ...prev, [nodePhase.id]: errMsg }));
              appendLog(`[ERROR] ${nodePhase.label} failed: ${errMsg.slice(0, 120)}`);
            } else if (typeof updateValue === "string" && updateValue.length > 0) {
              setMarkdownOutputs(prev => ({ ...prev, [nodePhase.id]: updateValue }));
            }

            setCompletePhases(prev => new Set([...prev, nodePhase.id]));
            setActiveTab(nodePhase.id);
          }
        }
      };

      es.onerror = () => {
        setIsProcessing(false);
        setStatusMessage("Connection lost.");
        appendLog("[error] Connection to backend lost.");
        setActivePhaseNodeKey(null);
        es.close();
      };
    } catch {
      setIsProcessing(false);
      setStatusMessage("Failed to connect to backend.");
      appendLog("[error] Failed to create session.");
      setActivePhaseNodeKey(null);
    }
  }, [ideaConcept, ideaContext, pdfFile, envOS, envAICLI, envExp, envNode, envPy, q1, a1, q2, a2, q3, a3]);

  return (
    <div className="flex flex-col h-screen bg-background overflow-hidden font-sans text-foreground selection:bg-accent/30 selection:text-white">
      
      {/* ENTERPRISE HEADER */}
      <header className="flex-shrink-0 h-14 border-b border-border bg-background flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-white rounded-sm flex items-center justify-center">
              <Zap className="w-4 h-4 text-background fill-current" />
            </div>
            <div className="font-bold text-sm tracking-tighter uppercase">
              Forge <span className="text-muted font-medium lowercase">/ v2.0</span>
            </div>
          </div>
          <div className="h-4 w-[1px] bg-border" />
          <nav className="flex items-center gap-4">
             <div className="px-2 py-1 rounded-sm hover:bg-surface transition-colors cursor-pointer group">
                <span className="text-[11px] font-medium text-muted group-hover:text-secondary uppercase tracking-widest">Zero-Ambiguity Build System</span>
             </div>
             <a href="/dashboard" className="flex items-center gap-1.5 px-2 py-1 rounded-sm hover:bg-surface transition-colors cursor-pointer group">
                <LayoutDashboard className="w-3.5 h-3.5 text-muted group-hover:text-accent transition-colors" />
                <span className="text-[11px] font-medium text-muted group-hover:text-secondary uppercase tracking-widest">Dashboard</span>
             </a>
          </nav>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 bg-surface border border-border rounded-sm">
            {isProcessing ? (
              <Loader2 className="w-3 h-3 text-accent animate-spin" />
            ) : isComplete ? (
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]" />
            ) : (
              <div className="w-1.5 h-1.5 rounded-full bg-muted/30" />
            )}
            <span className="font-mono text-[10px] text-muted-hover uppercase tracking-tight">
              {statusMessage}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-muted hover:text-secondary cursor-pointer transition-colors">
            <Command className="w-3.5 h-3.5" />
            <span className="text-xs font-medium">K</span>
          </div>
        </div>
      </header>

      {/* MINIMAL HORIZONTAL STEPPER (Linear Style) */}
      <div className="flex-shrink-0 border-b border-border bg-background px-6 h-12 flex items-center overflow-x-auto no-scrollbar">
        <div className="flex items-center w-full max-w-screen-2xl mx-auto">
          {PHASES.map((p, i) => {
            const isDone = completePhases.has(p.id);
            const isFailed = p.id in failedPhases;
            const isSelected = activeTab === p.id;

            return (
              <div key={p.id} className="flex items-center">
                <button
                  onClick={() => (isDone || isSelected) && setActiveTab(p.id)}
                  disabled={!isDone && !isSelected}
                  className={`
                    flex items-center gap-2.5 px-3 py-1 rounded-sm transition-all duration-150 text-[13px] font-medium relative group
                    ${isSelected
                      ? isFailed ? "text-red-400" : "text-foreground"
                      : isDone
                        ? isFailed ? "text-red-500/70 hover:text-red-400 cursor-pointer" : "text-muted-hover hover:text-foreground cursor-pointer"
                        : "text-muted/40 cursor-default"}
                  `}
                >
                  <div className={`
                    w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border transition-colors
                    ${isSelected
                      ? isFailed ? "border-red-500 bg-red-500/20 text-red-400" : "border-accent bg-accent text-white"
                      : isDone
                        ? isFailed ? "border-red-500/50 bg-transparent text-red-500" : "border-muted/50 bg-transparent text-muted-hover"
                        : "border-border bg-transparent text-muted/30"}
                  `}>
                    {isDone
                      ? isFailed
                        ? <X className="w-3 h-3 stroke-[3]" />
                        : <Check className="w-3 h-3 stroke-[3]" />
                      : i + 1}
                  </div>
                  <span className="whitespace-nowrap tracking-tight">{p.label}</span>
                  {isSelected && (
                    <motion.div
                      layoutId="nav-glow"
                      className={`absolute -bottom-[13px] left-0 right-0 h-[2px] z-10 ${
                        isFailed ? "bg-red-500" : "bg-accent"
                      }`}
                    />
                  )}
                </button>
                {i < PHASES.length - 1 && (
                  <div className="w-8 h-[1px] bg-border mx-2" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        
        {/* LEFT PANEL - FORM */}
        <aside className="w-[380px] flex-shrink-0 border-r border-border bg-background flex flex-col">
          <div className="p-8 flex-1 overflow-y-auto no-scrollbar flex flex-col gap-10">
            
            <div className="space-y-3">
              <h1 className="text-2xl font-bold tracking-tight text-white leading-tight">
                Idea → Executable<br/>Build Guide.
              </h1>
              <p className="text-[13px] text-muted leading-relaxed max-w-[280px]">
                FORGE runs full analysis + resolves every infra service + generates a downloadable step-by-step build guide for your machine.
              </p>
            </div>

            <form onSubmit={uiStep === "idle" ? handleGenerateQuestions : (e) => { e.preventDefault(); handleRunForge(); }} className="flex flex-col gap-8">
              
              {uiStep === "idle" || uiStep === "loading_questions" ? (
                <>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-bold text-muted uppercase tracking-[0.2em]">
                        Core Concept
                      </label>
                      <span className="text-[10px] text-muted/40 font-mono">Required</span>
                    </div>
                    <div className="relative group">
                      <textarea
                        required
                        placeholder="Describe what you want to build..."
                        value={ideaConcept}
                        onChange={e => setIdeaConcept(e.target.value)}
                        disabled={uiStep === "loading_questions"}
                        rows={5}
                        className="w-full bg-surface border border-border rounded-sm p-4 text-[13px] text-white placeholder:text-muted/40 focus:outline-none focus:border-accent/50 focus:ring-[1px] focus:ring-accent/20 transition-all resize-none disabled:opacity-50 leading-relaxed"
                        spellCheck="false"
                      />
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-bold text-muted uppercase tracking-[0.2em]">
                        Context & Notes
                      </label>
                      <span className="text-[10px] text-muted/40 font-mono">Optional</span>
                    </div>
                    <textarea
                      placeholder="Competitors, target audience, tech constraints..."
                      value={ideaContext}
                      onChange={e => setIdeaContext(e.target.value)}
                      disabled={uiStep === "loading_questions"}
                      rows={3}
                      className="w-full bg-surface border border-border rounded-sm p-4 text-[13px] text-white placeholder:text-muted/40 focus:outline-none focus:border-accent/50 focus:ring-[1px] focus:ring-accent/20 transition-all resize-none disabled:opacity-50 leading-relaxed"
                      spellCheck="false"
                    />
                  </div>
                  
                  <div className="space-y-3">
                    <label className="text-[10px] font-bold text-muted uppercase tracking-[0.2em]">
                      Context PDF
                    </label>
                    {!pdfFile ? (
                      <label className="flex flex-col items-center justify-center w-full h-24 border border-dashed border-border rounded-sm bg-surface/50 hover:bg-surface hover:border-accent/30 cursor-pointer transition-all group">
                        <div className="flex flex-col items-center justify-center pt-2 pb-2">
                          <Upload className="w-5 h-5 text-muted group-hover:text-accent mb-2 transition-colors" />
                          <p className="text-[11px] text-muted group-hover:text-muted-hover">Click to upload or drag and drop</p>
                          <p className="text-[9px] text-muted/50 mt-1">PDF (MAX. 10MB)</p>
                        </div>
                        <input 
                          type="file" 
                          className="hidden" 
                          accept=".pdf" 
                          onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                          disabled={uiStep === "loading_questions"}
                        />
                      </label>
                    ) : (
                      <div className="flex items-center justify-between w-full p-3 bg-surface border border-accent/20 rounded-sm">
                        <div className="flex items-center gap-3 overflow-hidden">
                          <FileText className="w-4 h-4 text-accent flex-shrink-0" />
                          <span className="text-[11px] text-secondary truncate">{pdfFile.name}</span>
                        </div>
                        <button 
                          type="button"
                          onClick={() => setPdfFile(null)}
                          disabled={uiStep === "loading_questions"}
                          className="p-1 hover:bg-background rounded-sm text-muted hover:text-red-400 transition-colors"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                  
                  {/* ... Env Profile omitted for space here, it is rendered below in answering phase too if needed, but let's keep it simple ... */}
                  <button
                    type="submit"
                    disabled={uiStep === "loading_questions" || !ideaConcept.trim()}
                    className={`
                      relative w-full flex items-center justify-center gap-2.5 py-3 px-4 rounded-sm text-[13px] font-bold transition-all duration-200 overflow-hidden
                      ${uiStep === "loading_questions" 
                        ? "bg-surface text-muted border border-border" 
                        : "bg-accent text-white hover:bg-accent/90 active:scale-[0.98]"}
                      disabled:cursor-not-allowed
                    `}
                  >
                    {uiStep === "loading_questions" ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Thinking about your idea...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5 fill-current" />
                        <span>Generate Questions</span>
                      </>
                    )}
                  </button>
                </>
              ) : (
                <>
                  <div className="space-y-6">
                    <div className="p-3 bg-accent/10 border border-accent/20 rounded-sm mb-4">
                      <p className="text-[12px] text-accent font-medium">Answer these 3 questions to sharpen your idea before we build it.</p>
                    </div>
                    
                    <div className="space-y-2">
                      <label className="text-[11px] font-bold text-white block">{q1}</label>
                      <textarea required value={a1} onChange={e => setA1(e.target.value)} disabled={isProcessing} rows={2}
                        className="w-full bg-surface border border-border rounded-sm p-3 text-[13px] text-white focus:outline-none focus:border-accent/50 transition-all resize-none disabled:opacity-50" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[11px] font-bold text-white block">{q2}</label>
                      <textarea required value={a2} onChange={e => setA2(e.target.value)} disabled={isProcessing} rows={2}
                        className="w-full bg-surface border border-border rounded-sm p-3 text-[13px] text-white focus:outline-none focus:border-accent/50 transition-all resize-none disabled:opacity-50" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[11px] font-bold text-white block">{q3}</label>
                      <textarea required value={a3} onChange={e => setA3(e.target.value)} disabled={isProcessing} rows={2}
                        className="w-full bg-surface border border-border rounded-sm p-3 text-[13px] text-white focus:outline-none focus:border-accent/50 transition-all resize-none disabled:opacity-50" />
                    </div>
                  </div>

                  {/* Environment Profile */}
                  <div className="space-y-3 pt-4 border-t border-border">
                    <div className="flex items-center gap-2 mb-1">
                      <Monitor className="w-3.5 h-3.5 text-accent" />
                      <label className="text-[10px] font-bold text-muted uppercase tracking-[0.2em]">Your Environment</label>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] text-muted/60 uppercase tracking-widest">OS</label>
                        <select
                          value={envOS} onChange={e => setEnvOS(e.target.value as EnvOS)}
                          disabled={isProcessing}
                          className="w-full mt-1 bg-surface border border-border rounded-sm px-2 py-1.5 text-[12px] text-white focus:outline-none focus:border-accent/50 disabled:opacity-50"
                        >
                          <option value="windows">Windows</option>
                          <option value="mac">macOS</option>
                          <option value="linux">Linux</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[9px] text-muted/60 uppercase tracking-widest">AI Tool</label>
                        <select
                          value={envAICLI} onChange={e => setEnvAICLI(e.target.value as EnvAICLI)}
                          disabled={isProcessing}
                          className="w-full mt-1 bg-surface border border-border rounded-sm px-2 py-1.5 text-[12px] text-white focus:outline-none focus:border-accent/50 disabled:opacity-50"
                        >
                          <option value="gemini">Gemini CLI</option>
                          <option value="claude_code">Claude Code</option>
                          <option value="cursor">Cursor</option>
                          <option value="copilot">GitHub Copilot</option>
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="text-[9px] text-muted/60 uppercase tracking-widest">Experience</label>
                      <select
                        value={envExp} onChange={e => setEnvExp(e.target.value as EnvExp)}
                        disabled={isProcessing}
                        className="w-full mt-1 bg-surface border border-border rounded-sm px-2 py-1.5 text-[12px] text-white focus:outline-none focus:border-accent/50 disabled:opacity-50"
                      >
                        <option value="beginner">Beginner (1st–2nd year)</option>
                        <option value="intermediate">Intermediate (3rd year+)</option>
                        <option value="advanced">Advanced (worked on projects)</option>
                      </select>
                    </div>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked={envNode} onChange={e => setEnvNode(e.target.checked)} disabled={isProcessing}
                          className="w-3.5 h-3.5 accent-accent" />
                        <span className="text-[11px] text-muted">Node.js installed</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked={envPy} onChange={e => setEnvPy(e.target.checked)} disabled={isProcessing}
                          className="w-3.5 h-3.5 accent-accent" />
                        <span className="text-[11px] text-muted">Python installed</span>
                      </label>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={isProcessing || !a1.trim() || !a2.trim() || !a3.trim()}
                    className={`
                      relative w-full flex items-center justify-center gap-2.5 py-3 px-4 rounded-sm text-[13px] font-bold transition-all duration-200 overflow-hidden
                      ${isProcessing 
                        ? "bg-surface text-muted border border-border" 
                        : "bg-accent text-white hover:bg-accent/90 active:scale-[0.98]"}
                      disabled:cursor-not-allowed
                    `}
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Building your guide...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>Run FORGE v2.0</span>
                      </>
                    )}
                  </button>
                </>
              )}
            </form>

            {/* ENGINE LOGS */}
            <div className="mt-auto pt-8 border-t border-border/50">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <TerminalSquare className="w-3.5 h-3.5 text-muted" />
                  <span className="text-[10px] font-bold text-muted uppercase tracking-widest">Real-time Stream</span>
                </div>
                <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              </div>
              <div className="bg-surface/50 rounded-sm border border-border p-3 h-40 overflow-y-auto no-scrollbar font-mono text-[10px] leading-relaxed text-muted-hover">
                {logs.length === 0 ? (
                  <div className="opacity-30 italic">System ready. Awaiting telemetry...</div>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {logs.map((l, i) => (
                      <div key={i} className="flex gap-2">
                        <span className="text-accent/50 flex-shrink-0">›</span>
                        <span className="break-words">{l}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </aside>

        {/* MAIN CONTENT AREA */}
        <section className="flex-1 flex flex-col bg-background min-w-0">
          
          {verdictCard && activeTab === "verdict" && (
            <div className="flex-shrink-0 border-b border-border bg-surface p-6 overflow-y-auto">
               <div className="max-w-4xl mx-auto">
                 <h2 className="text-sm font-bold text-muted uppercase tracking-widest mb-4">Final Verdict</h2>
                 
                 {verdictCard.confidence === 'LOW' && (
                   <div className="col-span-full p-3 mb-4 rounded border border-yellow-600/50 bg-yellow-950/30">
                     <p className="text-xs font-bold uppercase tracking-widest text-yellow-400">
                       LOW CONFIDENCE — Fewer than 2 sourced complaints were found.
                     </p>
                     <p className="text-xs text-yellow-300/80 mt-1">
                       Do NOT build yet. Find 5 real people publicly complaining about this problem
                       before spending a single hour on code.
                     </p>
                   </div>
                 )}
                 
                 <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="col-span-2 md:col-span-1 p-4 bg-background border border-border rounded-sm">
                      <div className="text-[10px] text-muted uppercase tracking-widest mb-1">Decision</div>
                      <div className="flex items-center gap-2">
                        <span className="text-xl font-bold text-orange-500">{verdictCard.decision}</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                          verdictCard.confidence === 'HIGH' ? 'bg-green-900/50 text-green-400' :
                          verdictCard.confidence === 'MEDIUM' ? 'bg-yellow-900/50 text-yellow-400' :
                          'bg-red-900/50 text-red-400'
                        }`}>
                          {verdictCard.confidence}
                        </span>
                      </div>
                      <div className="text-[10px] text-muted-hover mt-1">Score: {verdictCard.score}/100</div>
                    </div>
                    <div className="col-span-2 md:col-span-3 p-4 bg-background border border-border rounded-sm">
                      <div className="text-[10px] text-muted uppercase tracking-widest mb-1">Reasoning</div>
                      <div className="text-sm text-white">{verdictCard.decision_reason}</div>
                    </div>
                    <div className="col-span-2 p-4 bg-background border border-border rounded-sm">
                      <div className="text-[10px] text-muted uppercase tracking-widest mb-1">Your Edge</div>
                      <div className="text-sm text-green-400">{verdictCard.your_edge}</div>
                    </div>
                    <div className="col-span-2 p-4 bg-background border border-border rounded-sm">
                      <div className="text-[10px] text-muted uppercase tracking-widest mb-1">Kill Condition</div>
                      <div className="text-sm text-red-400">{verdictCard.kill_condition}</div>
                      <div className="text-[10px] text-muted mt-1">Timeline: {verdictCard.kill_timeline}</div>
                    </div>
                    <div className="col-span-2 p-4 bg-background border border-border rounded-sm">
                      <div className="text-[10px] text-muted uppercase tracking-widest mb-1">Build First</div>
                      <div className="text-sm text-accent">{verdictCard.build_first}</div>
                    </div>
                    <div className="col-span-2 p-4 bg-background border border-border rounded-sm">
                      <div className="text-[10px] text-muted uppercase tracking-widest mb-1">Do Tomorrow</div>
                      <div className="text-sm text-blue-400">{verdictCard.do_tomorrow}</div>
                    </div>
                 </div>
               </div>
            </div>
          )}

          <div className="flex-1 overflow-y-auto no-scrollbar relative">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
                className="max-w-4xl mx-auto w-full min-h-full flex flex-col"
              >
                {failedPhases[activeTab] ? (
                  // ── PHASE FAILED — show honest error, never fake content ──────────
                  <div className="p-12 md:p-16 lg:p-20">
                    <header className="mb-10 pb-8 border-b border-red-900/40">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-8 h-8 rounded-sm bg-red-950/60 border border-red-800/50 flex items-center justify-center">
                          <AlertTriangle className="w-4 h-4 text-red-400" />
                        </div>
                        <h2 className="text-sm font-bold text-red-500 uppercase tracking-[0.3em]">
                          Phase 0{PHASES.findIndex(p => p.id === activeTab) + 1} — Failed
                        </h2>
                      </div>
                      <h1 className="text-4xl font-bold tracking-tight text-red-400 mb-4">
                        {PHASES.find(p => p.id === activeTab)?.label}
                      </h1>
                    </header>

                    {/* Failure explanation */}
                    <div className="rounded-sm border border-red-800/50 bg-red-950/30 p-6 mb-8">
                      <div className="flex items-start gap-4">
                        <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                        <div className="space-y-3">
                          <p className="text-sm font-semibold text-red-300">
                            This phase failed to produce valid output.
                          </p>
                          <p className="text-xs text-red-400/80 leading-relaxed">
                            The LLM could not generate a structured response that passed schema
                            validation after all retry tiers were exhausted. Downstream phases
                            that depend on this output may also be unreliable.
                          </p>
                          <div className="mt-3 pt-3 border-t border-red-800/40">
                            <p className="text-[10px] font-mono text-red-500/70 uppercase tracking-widest mb-1">Error Detail</p>
                            <p className="text-xs font-mono text-red-400 break-all leading-relaxed">
                              {failedPhases[activeTab]}
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Action hints */}
                    <div className="space-y-2">
                      <p className="text-[10px] font-bold text-muted uppercase tracking-widest">What to do</p>
                      <ul className="space-y-1.5 text-xs text-muted leading-relaxed list-none">
                        <li className="flex items-center gap-2"><span className="text-red-500">›</span> Check the backend terminal for the full traceback.</li>
                        <li className="flex items-center gap-2"><span className="text-red-500">›</span> Verify Ollama is running and the model is loaded.</li>
                        <li className="flex items-center gap-2"><span className="text-red-500">›</span> Switch <code className="bg-surface px-1 py-0.5 rounded text-[10px]">LLM_MODE</code> to <code className="bg-surface px-1 py-0.5 rounded text-[10px]">groq</code> for better structured output reliability.</li>
                        <li className="flex items-center gap-2"><span className="text-red-500">›</span> Re-run the pipeline with a more specific idea description.</li>
                      </ul>
                    </div>
                  </div>
                ) : markdownOutputs[activeTab] ? (
                  // ── PHASE SUCCEEDED — show real output ───────────────────────────
                  <div className="p-12 md:p-16 lg:p-20">
                    <header className="mb-12 pb-8 border-b border-border">
                       <div className="flex items-center gap-3 mb-4">
                         <div className="w-8 h-8 rounded-sm bg-surface border border-border flex items-center justify-center">
                            {(() => {
                              const Icon = PHASES.find(p => p.id === activeTab)?.icon || Box;
                              return <Icon className="w-4 h-4 text-accent" />;
                            })()}
                         </div>
                         <h2 className="text-sm font-bold text-accent uppercase tracking-[0.3em]">Phase 0{PHASES.findIndex(p=>p.id===activeTab)+1}</h2>
                       </div>
                       <h1 className="text-4xl font-bold tracking-tight text-white mb-4">
                         {PHASES.find(p => p.id === activeTab)?.label}
                       </h1>
                    </header>
                    <div className="prose-obsidian">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {markdownOutputs[activeTab]}
                      </ReactMarkdown>
                    </div>
                  </div>
                ) : (
                  // ── PHASE NOT YET RUN — show idle/processing placeholder ─────────
                  <div className="flex-1 flex items-center justify-center p-12">
                    <EmptyStateView
                      phaseId={activeTab}
                      isProcessing={isProcessing && activePhaseNodeKey === PHASES.find(p=>p.id===activeTab)?.nodeKey}
                    />
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </div>

          {isComplete && (() => {
            const failedCount = Object.keys(failedPhases).length;
            const hasFailures = failedCount > 0;
            return (
              <div className={`h-16 border-t px-8 flex items-center justify-between ${
                hasFailures
                  ? "border-red-900/50 bg-red-950/20"
                  : "border-border bg-surface/30"
              }`}>
                <div className="flex items-center gap-4 text-xs">
                  {hasFailures ? (
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                      <span className="font-medium text-red-400">
                        {failedCount} phase{failedCount > 1 ? "s" : ""} failed — outputs may be affected
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                      <span className="font-medium text-secondary">All phases complete</span>
                    </div>
                  )}
                  {docxUrl && (
                    <>
                      <div className="h-3 w-[1px] bg-border" />
                      <div className="flex items-center gap-1.5 text-green-400">
                        <CheckCircle2 className="w-3 h-3" />
                        <span className="text-[11px] font-medium">Build guide ready</span>
                      </div>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {/* Markdown export (always available) */}
                  <button
                    onClick={() => {
                      let content = "# FORGE Build Guide Export\n\n";
                      PHASES.forEach(p => {
                        if (failedPhases[p.id]) {
                          content += `## ${p.label} [FAILED]\n\nError: ${failedPhases[p.id]}\n\n`;
                        } else if (markdownOutputs[p.id]) {
                          content += `## ${p.label}\n\n${markdownOutputs[p.id]}\n\n`;
                        }
                      });
                      const blob = new Blob([content], { type: "text/markdown" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `forge-blueprint-${new Date().toISOString().split("T")[0]}.md`;
                      document.body.appendChild(a); a.click();
                      document.body.removeChild(a); URL.revokeObjectURL(url);
                    }}
                    className="px-3 py-1.5 bg-surface text-muted border border-border text-xs font-bold rounded-sm hover:text-white hover:border-accent/50 transition-colors flex items-center gap-1.5"
                  >
                    <FileText className="w-3 h-3" /> .md
                  </button>
                  {/* Docx download (appears when ready) */}
                  {docxUrl ? (
                    <a
                      href={docxUrl}
                      download
                      className="px-4 py-1.5 bg-accent text-white text-xs font-bold rounded-sm hover:bg-accent/90 transition-colors flex items-center gap-2 shadow-lg shadow-accent/20"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download Build Guide (.docx)
                    </a>
                  ) : (
                    <button
                      disabled
                      className="px-4 py-1.5 bg-surface text-muted/40 border border-border text-xs font-bold rounded-sm cursor-not-allowed flex items-center gap-2"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Build Guide (.docx)
                    </button>
                  )}
                </div>
              </div>
            );
          })()}
        </section>
      </div>
    </div>
  );
}

function EmptyStateView({ phaseId, isProcessing }: { phaseId: string, isProcessing: boolean }) {
  const hint = EMPTY_HINTS[phaseId];
  if (!hint) return null;
  const Icon = hint.icon;

  return (
    <div className="max-w-md w-full">
      <div className="flex flex-col items-center text-center">
        {isProcessing ? (
          <div className="space-y-8 flex flex-col items-center">
            <div className="relative">
              <div className="w-16 h-16 rounded-full border-[1.5px] border-border border-t-accent animate-spin" />
              <div className="absolute inset-0 flex items-center justify-center">
                <Icon className="w-6 h-6 text-accent/50" />
              </div>
            </div>
            <div className="space-y-3">
              <h3 className="text-xl font-bold text-white tracking-tight">Synthesizing Intel...</h3>
              <p className="text-sm text-muted leading-relaxed px-4">
                The engine is currently running the {PHASES.find(p=>p.id===phaseId)?.label} module. 
                Data is being streamed and structured for your review.
              </p>
            </div>
            <div className="flex gap-1">
              {[0, 1, 2].map(i => (
                <motion.div
                  key={i}
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                  className="w-1 h-1 bg-accent rounded-full"
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6 flex flex-col items-center">
            <div className="w-16 h-16 rounded-sm border border-border bg-surface flex items-center justify-center group-hover:border-accent/30 transition-colors">
              <Icon className="w-8 h-8 text-muted group-hover:text-accent transition-colors" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-bold text-white tracking-tight">{hint.title}</h3>
              <p className="text-sm text-muted leading-relaxed max-w-[320px] mx-auto">
                {hint.desc}
              </p>
            </div>
            <div className="pt-4">
               <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface border border-border text-[10px] font-bold text-muted uppercase tracking-widest">
                 System Idle
               </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
