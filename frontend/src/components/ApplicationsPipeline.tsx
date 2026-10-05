import React, { useState } from 'react';
import { 
  Kanban, 
  Clock, 
  CheckCircle2, 
  Send, 
  Building2, 
  MapPin, 
  Mail, 
  Calendar, 
  ArrowRight,
  Filter,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import { Application } from '../types';
import { api } from '../services/api';

interface ApplicationsPipelineProps {
  applications: Application[];
  onRefresh: () => void;
  onOpenApproval: (jobId: string) => void;
}

const STAGES = [
  { id: 'REVIEW_REQUIRED', label: 'Review Required', color: 'border-accent-amber/40 text-accent-amber bg-accent-amber/10' },
  { id: 'APPROVED', label: 'Approved', color: 'border-brand-500/40 text-brand-300 bg-brand-500/10' },
  { id: 'RECRUITER_CONTACTED', label: 'Recruiter Contacted', color: 'border-accent-cyan/40 text-accent-cyan bg-accent-cyan/10' },
  { id: 'INTERVIEW', label: 'Interview Scheduled', color: 'border-accent-emerald/40 text-accent-emerald bg-accent-emerald/10' },
  { id: 'APPLIED', label: 'Applied', color: 'border-indigo-500/40 text-indigo-300 bg-indigo-500/10' },
];

export const ApplicationsPipeline: React.FC<ApplicationsPipelineProps> = ({
  applications,
  onRefresh,
  onOpenApproval
}) => {
  const [viewMode, setViewMode] = useState<'kanban' | 'table'>('kanban');

  const handleStatusChange = async (appId: string, newStatus: string) => {
    try {
      await api.updateApplicationStatus(appId, newStatus);
      onRefresh();
    } catch (err) {
      console.error('Status update failed:', err);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Controls */}
      <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Kanban className="w-5 h-5 text-brand-400" />
            Applications & Outreach Pipeline ({applications.length})
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Track every job, recruiter contact, personalized message, and lifecycle status in real time.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode('kanban')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
              viewMode === 'kanban'
                ? 'bg-brand-600 text-white border-brand-500'
                : 'bg-surfaceHover text-slate-400 border-surfaceBorder hover:text-white'
            }`}
          >
            Kanban Board
          </button>
          <button
            onClick={() => setViewMode('table')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
              viewMode === 'table'
                ? 'bg-brand-600 text-white border-brand-500'
                : 'bg-surfaceHover text-slate-400 border-surfaceBorder hover:text-white'
            }`}
          >
            Table View
          </button>
        </div>
      </div>

      {/* Kanban View */}
      {viewMode === 'kanban' ? (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 overflow-x-auto pb-4">
          {STAGES.map((stage) => {
            const stageApps = applications.filter((app) => (app.status || 'REVIEW_REQUIRED') === stage.id);

            return (
              <div
                key={stage.id}
                className="glass-panel rounded-2xl p-4 border border-surfaceBorder min-w-[240px] flex flex-col"
              >
                {/* Stage Header */}
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-surfaceBorder">
                  <span className="text-xs font-bold text-white">{stage.label}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold border ${stage.color}`}>
                    {stageApps.length}
                  </span>
                </div>

                {/* Cards */}
                <div className="space-y-3 flex-1">
                  {stageApps.length === 0 ? (
                    <div className="h-28 border border-dashed border-surfaceBorder rounded-xl flex items-center justify-center text-[11px] text-slate-500">
                      No applications
                    </div>
                  ) : (
                    stageApps.map((app) => {
                      const job = app.job;
                      const score = app.match?.overall_score ?? 88;

                      return (
                        <div
                          key={app.id}
                          className="p-3.5 rounded-xl bg-surfaceHover/80 border border-surfaceBorder hover:border-brand-500/40 transition-all space-y-2 shadow-sm"
                        >
                          <div className="flex items-start justify-between gap-1">
                            <h4 className="text-xs font-bold text-white leading-tight">
                              {job?.title || 'Engineer Role'}
                            </h4>
                            <span className="text-[10px] font-extrabold px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-300">
                              {score}%
                            </span>
                          </div>

                          <div className="text-[11px] text-slate-300 flex items-center gap-1">
                            <Building2 className="w-3 h-3 text-slate-400" />
                            <span>{job?.company || 'Company'}</span>
                          </div>

                          {app.recruiter && (
                            <div className="text-[10px] text-slate-400 bg-background/50 p-1.5 rounded-lg">
                              Recruiter: <span className="text-slate-200 font-semibold">{app.recruiter.name}</span>
                            </div>
                          )}

                          {/* Action button */}
                          <div className="pt-2 border-t border-surfaceBorder/60 flex items-center justify-between">
                            {stage.id === 'REVIEW_REQUIRED' ? (
                              <button
                                onClick={() => onOpenApproval(app.job_id)}
                                className="w-full py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-[11px] font-bold shadow-sm flex items-center justify-center gap-1"
                              >
                                <span>Review & Approve</span>
                                <ArrowRight className="w-3 h-3" />
                              </button>
                            ) : (
                              <select
                                value={app.status}
                                onChange={(e) => handleStatusChange(app.id, e.target.value)}
                                className="w-full bg-background border border-surfaceBorder rounded-lg px-2 py-1 text-[10px] text-slate-300 focus:outline-none focus:border-brand-500"
                              >
                                {STAGES.map((s) => (
                                  <option key={s.id} value={s.id}>Move: {s.label}</option>
                                ))}
                              </select>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Table View */
        <div className="glass-panel rounded-2xl border border-surfaceBorder overflow-hidden">
          <table className="w-full text-left text-xs text-slate-200">
            <thead className="bg-surfaceHover/80 text-[11px] uppercase tracking-wider text-slate-400 border-b border-surfaceBorder">
              <tr>
                <th className="py-3 px-4 font-semibold">Company & Role</th>
                <th className="py-3 px-4 font-semibold">Match Score</th>
                <th className="py-3 px-4 font-semibold">Recruiter Contact</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surfaceBorder">
              {applications.map((app) => (
                <tr key={app.id} className="hover:bg-surfaceHover/40 transition-colors">
                  <td className="py-3 px-4">
                    <span className="font-bold text-white block">{app.job?.title}</span>
                    <span className="text-slate-400 text-[11px]">{app.job?.company}</span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">
                      {app.match?.overall_score ?? 88}%
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {app.recruiter ? (
                      <div>
                        <span className="font-medium text-slate-200">{app.recruiter.name}</span>
                        <span className="text-slate-400 text-[10px] block">{app.recruiter.public_email || 'LinkedIn Contact'}</span>
                      </div>
                    ) : (
                      <span className="text-slate-500 italic">Not found</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <select
                      value={app.status}
                      onChange={(e) => handleStatusChange(app.id, e.target.value)}
                      className="bg-background border border-surfaceBorder rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none"
                    >
                      {STAGES.map((s) => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </select>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => onOpenApproval(app.job_id)}
                      className="px-3 py-1.5 rounded-lg bg-surfaceHover hover:bg-slate-700 text-brand-300 font-semibold text-xs border border-surfaceBorder"
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
