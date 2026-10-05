import React from 'react';
import { 
  BarChart3, 
  Briefcase, 
  CheckCircle2, 
  Mail, 
  Users, 
  Calendar, 
  TrendingUp, 
  Cpu, 
  Clock,
  Sparkles
} from 'lucide-react';
import { DashboardStats } from '../types';

interface AnalyticsDashboardProps {
  stats: DashboardStats | null;
}

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({ stats }) => {
  if (!stats) {
    return <div className="text-center p-8 text-slate-400">Loading analytics...</div>;
  }

  const kpis = [
    { label: 'Jobs Found', value: stats.jobs_found, icon: Briefcase, color: 'text-brand-400', bg: 'bg-brand-500/10' },
    { label: 'Strong Matches', value: stats.strong_matches, icon: Sparkles, color: 'text-accent-emerald', bg: 'bg-accent-emerald/10' },
    { label: 'Applications Prepared', value: stats.applications, icon: CheckCircle2, color: 'text-accent-cyan', bg: 'bg-accent-cyan/10' },
    { label: 'Recruiters Discovered', value: stats.recruiters_found, icon: Users, color: 'text-accent-violet', bg: 'bg-accent-violet/10' },
    { label: 'Outreach Dispatched', value: stats.emails_sent, icon: Mail, color: 'text-accent-amber', bg: 'bg-accent-amber/10' },
    { label: 'Interviews Landed', value: stats.interviews, icon: Calendar, color: 'text-accent-rose', bg: 'bg-accent-rose/10' },
  ];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-brand-400" />
          Application Metrics & Agent Observability
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          High-level analytics across multi-agent job searches, deterministic match scoring, recruiter outreach, and conversion rates.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div key={idx} className="glass-panel rounded-2xl p-4 border border-surfaceBorder space-y-2">
              <div className={`w-8 h-8 rounded-xl ${kpi.bg} flex items-center justify-center ${kpi.color}`}>
                <Icon className="w-4 h-4" />
              </div>
              <div>
                <span className="text-2xl font-black text-white">{kpi.value}</span>
                <p className="text-[11px] font-semibold text-slate-400">{kpi.label}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Charts & Distributions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Score Distribution */}
        <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder space-y-4">
          <h3 className="text-sm font-bold text-white">Match Score Distribution</h3>
          <div className="space-y-3">
            {Object.entries(stats.score_distribution || {}).map(([range, count], idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="font-semibold">{range}</span>
                  <span className="font-mono text-slate-400">{count} jobs</span>
                </div>
                <div className="h-2 w-full bg-background rounded-full overflow-hidden border border-surfaceBorder">
                  <div
                    className="h-full bg-gradient-to-r from-brand-600 to-accent-cyan rounded-full transition-all"
                    style={{ width: `${Math.min(count * 25, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Target Roles Distribution */}
        <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder space-y-4">
          <h3 className="text-sm font-bold text-white">Discovered Positions by Role</h3>
          <div className="space-y-3">
            {Object.entries(stats.role_distribution || {}).map(([role, count], idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="font-semibold">{role}</span>
                  <span className="font-mono text-slate-400">{count}</span>
                </div>
                <div className="h-2 w-full bg-background rounded-full overflow-hidden border border-surfaceBorder">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-accent-emerald rounded-full transition-all"
                    style={{ width: `${Math.min(count * 30, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Agent Runs Trace */}
      <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Cpu className="w-4 h-4 text-brand-400" />
          Recent Agent Run Telemetry
        </h3>

        <div className="divide-y divide-surfaceBorder text-xs">
          {(stats.recent_runs || []).map((run) => (
            <div key={run.id} className="py-3 flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div className="space-y-0.5">
                <span className="font-semibold text-white block">{run.prompt}</span>
                <span className="text-slate-500 font-mono text-[10px]">ID: {run.id}</span>
              </div>
              <div className="flex items-center gap-3 text-slate-400 text-[11px]">
                <span className="px-2 py-0.5 rounded-full bg-accent-emerald/15 text-accent-emerald font-bold text-[10px]">
                  {run.status}
                </span>
                <span className="flex items-center gap-1 font-mono">
                  <Clock className="w-3 h-3" /> {Math.round(run.latency_ms)}ms
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
