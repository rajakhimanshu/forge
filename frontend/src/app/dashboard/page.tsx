'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeft, CheckCircle, Clock, Trash2, AlertTriangle, RefreshCw } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Project {
  id: string;
  project_name: string;
  idea_summary: string;
  verdict: string;
  status: string;
  days_since_created: number;
  phase_reached: number;
  commitment: string;
  notes: string;
  created_at: string;
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Status mapping
  const STATUSES = ['Not Started', 'In Progress', 'Achieved', 'Abandoned'];

  const fetchDashboard = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/dashboard`);
      if (!res.ok) throw new Error('Failed to fetch dashboard data');
      const data = await res.json();
      setProjects(data);
      setError('');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not load dashboard.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const updateStatus = async (projectId: string, newStatus: string) => {
    // Optimistic update
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, status: newStatus } : p));
    try {
      const res = await fetch(`${API_BASE_URL}/api/dashboard/${projectId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      if (!res.ok) throw new Error('Update failed');
    } catch (err: unknown) {
      console.error(err);
      // Revert on failure
      fetchDashboard();
    }
  };

  // Stats computation
  const total = projects.length;
  const achieved = projects.filter(p => p.status === 'Achieved').length;
  const abandoned = projects.filter(p => p.status === 'Abandoned').length;
  const inProgress = projects.filter(p => p.status === 'In Progress').length;
  const rate = total > 0 ? Math.round((achieved / total) * 100) : 0;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'Achieved': return <CheckCircle className="w-5 h-5 text-emerald-500" />;
      case 'In Progress': return <RefreshCw className="w-5 h-5 text-blue-500" />;
      case 'Not Started': return <Clock className="w-5 h-5 text-slate-400" />;
      case 'Abandoned': return <Trash2 className="w-5 h-5 text-red-500" />;
      default: return <Clock className="w-5 h-5 text-slate-400" />;
    }
  };

  const getVerdictBadgeColor = (verdict: string) => {
    const v = verdict.toUpperCase();
    if (v.includes('BUILD')) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    if (v.includes('PIVOT')) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    if (v.includes('SKIP')) return 'bg-red-500/10 text-red-400 border-red-500/20';
    return 'bg-slate-800 text-slate-300 border-slate-700';
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-slate-300 p-8 font-sans">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <Link href="/" className="inline-flex items-center text-sm font-medium text-blue-400 hover:text-blue-300 mb-4 transition-colors">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Forge New Project
            </Link>
            <h1 className="text-4xl font-bold tracking-tight text-white flex items-center">
              Accountability Dashboard
            </h1>
            <p className="mt-2 text-slate-400">Track your execution graveyard and active projects.</p>
          </div>
        </div>

        {/* Accountability Warning */}
        {abandoned > 0 && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-4">
            <AlertTriangle className="w-6 h-6 text-red-400 shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-400">You have {abandoned} abandoned project{abandoned > 1 && 's'}.</h3>
              <p className="text-red-200/80 text-sm mt-1">Before starting something new, ask yourself: what was the real root cause of your past failures? Are you procrastinating by building again?</p>
            </div>
          </div>
        )}

        {/* API Error Banner */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-4">
            <AlertTriangle className="w-6 h-6 text-red-400 shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-400">Failed to load dashboard</h3>
              <p className="text-red-200/80 text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="text-slate-400 text-sm font-medium">Total Ideas</div>
            <div className="text-3xl font-bold text-white mt-1">{total}</div>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
             <div className="text-emerald-500/80 text-sm font-medium">Shipped & Achieved</div>
            <div className="text-3xl font-bold text-white mt-1">{achieved}</div>
          </div>
           <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
             <div className="text-blue-500/80 text-sm font-medium">In Progress</div>
            <div className="text-3xl font-bold text-white mt-1">{inProgress}</div>
          </div>
           <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
             <div className="text-slate-400 text-sm font-medium">Ship Rate</div>
            <div className="text-3xl font-bold text-white mt-1">{rate}%</div>
          </div>
        </div>

        {/* Main Table */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
          <div className="p-5 border-b border-slate-800 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Project Graveyard & Pipeline</h2>
            <button onClick={fetchDashboard} className="text-slate-400 hover:text-white p-2">
               <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs uppercase bg-slate-950/50 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-6 py-4 font-medium tracking-wider">Status</th>
                  <th className="px-6 py-4 font-medium tracking-wider">Project</th>
                  <th className="px-6 py-4 font-medium tracking-wider">Verdict</th>
                  <th className="px-6 py-4 font-medium tracking-wider">Age</th>
                  <th className="px-6 py-4 font-medium tracking-wider text-right">Phases</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {projects.map((p) => (
                  <tr key={p.id} className={`hover:bg-slate-800/30 transition-colors ${p.status === 'Abandoned' ? 'opacity-60' : ''}`}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(p.status)}
                        <select 
                          className="bg-transparent text-slate-300 font-medium focus:outline-none focus:ring-0 cursor-pointer hover:text-white transition-colors"
                          value={p.status}
                          onChange={(e) => updateStatus(p.id, e.target.value)}
                        >
                          {STATUSES.map(s => <option key={s} value={s} className="bg-slate-800">{s}</option>)}
                        </select>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-200 text-base">{p.project_name}</div>
                      <div className="text-slate-500 mt-1 line-clamp-1 max-w-sm" title={p.idea_summary}>{p.idea_summary}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2.5 py-1 text-xs font-semibold rounded-md border ${getVerdictBadgeColor(p.verdict)}`}>
                        {p.verdict}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-slate-400 font-medium">
                      {p.days_since_created} days
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                       <span className="inline-flex items-center text-slate-300 font-medium bg-slate-800 px-2 py-1 rounded-md text-xs">
                         {p.phase_reached} / 8
                       </span>
                    </td>
                  </tr>
                ))}
                
                {projects.length === 0 && !isLoading && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center">
                         <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center mb-4">
                            <Clock className="w-8 h-8 text-slate-500" />
                         </div>
                         <p className="text-lg font-medium text-white mb-1">No execution history found</p>
                         <p>Run your first project through FORGE to populate this dashboard.</p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
