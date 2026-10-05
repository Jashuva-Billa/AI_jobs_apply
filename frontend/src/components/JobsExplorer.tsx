import React, { useState } from 'react';
import { 
  Search, 
  Filter, 
  MapPin, 
  DollarSign, 
  Briefcase, 
  ExternalLink, 
  CheckCircle2, 
  UserCheck, 
  AlertTriangle, 
  ChevronDown, 
  ChevronUp, 
  Sparkles,
  ArrowUpRight
} from 'lucide-react';
import { Job } from '../types';

interface JobsExplorerProps {
  jobs: Job[];
  onOpenApproval: (jobId: string) => void;
}

export const JobsExplorer: React.FC<JobsExplorerProps> = ({
  jobs,
  onOpenApproval
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);

  const filteredJobs = jobs.filter((job) => {
    const score = job.match?.overall_score ?? 80;
    if (score < minScore) return false;
    if (remoteOnly && !job.remote) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchTitle = job.title.toLowerCase().includes(q);
      const matchCompany = job.company.toLowerCase().includes(q);
      const matchSkills = job.skills.some((s) => s.toLowerCase().includes(q));
      if (!matchTitle && !matchCompany && !matchSkills) return false;
    }
    return true;
  });

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'bg-accent-emerald/20 text-accent-emerald border-accent-emerald/30';
    if (score >= 80) return 'bg-brand-500/20 text-brand-300 border-brand-500/30';
    if (score >= 70) return 'bg-accent-amber/20 text-accent-amber border-accent-amber/30';
    return 'bg-slate-700/40 text-slate-400 border-slate-600';
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header and Filter Controls */}
      <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-brand-400" />
              Discovered & Evaluated Jobs ({filteredJobs.length})
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Multi-source aggregated roles evaluated using deterministic multi-factor scoring against your resume.
            </p>
          </div>

          <div className="flex items-center gap-3 w-full md:w-auto">
            <div className="relative flex-1 md:w-64">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Filter by role or skill..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-background border border-surfaceBorder rounded-xl pl-9 pr-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500"
              />
            </div>
            
            <button
              onClick={() => setRemoteOnly(!remoteOnly)}
              className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all flex items-center gap-1.5 ${
                remoteOnly
                  ? 'bg-brand-600/20 text-brand-300 border-brand-500/40'
                  : 'bg-surfaceHover text-slate-400 border-surfaceBorder'
              }`}
            >
              <MapPin className="w-3.5 h-3.5" />
              <span>Remote Only</span>
            </button>
          </div>
        </div>

        {/* Score Threshold Filter */}
        <div className="flex items-center gap-4 pt-2 border-t border-surfaceBorder/60 text-xs text-slate-400">
          <span className="font-medium">Min Match Score:</span>
          <div className="flex items-center gap-2">
            {[0, 70, 80, 90].map((threshold) => (
              <button
                key={threshold}
                onClick={() => setMinScore(threshold)}
                className={`px-2.5 py-1 rounded-lg border text-xs font-semibold transition-all ${
                  minScore === threshold
                    ? 'bg-brand-600 text-white border-brand-500 shadow-sm'
                    : 'bg-surfaceHover text-slate-400 border-surfaceBorder hover:text-slate-200'
                }`}
              >
                {threshold === 0 ? 'All' : `${threshold}%+`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Jobs Grid */}
      <div className="grid grid-cols-1 gap-4">
        {filteredJobs.map((job) => {
          const match = job.match;
          const score = match?.overall_score ?? 85;
          const isExpanded = expandedJobId === job.id;

          return (
            <div
              key={job.id}
              className="glass-panel rounded-2xl border border-surfaceBorder p-5 transition-all glass-panel-hover"
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                {/* Job Title & Company */}
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-bold text-white hover:text-brand-300 transition-colors">
                      {job.title}
                    </h3>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-extrabold border ${getScoreColor(score)}`}>
                      {score}% Match
                    </span>
                    {job.remote && (
                      <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/25">
                        Remote
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
                    <span className="font-semibold text-slate-100">{job.company}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1 text-slate-400">
                      <MapPin className="w-3.5 h-3.5" /> {job.location}
                    </span>
                    {job.salary && (
                      <>
                        <span>•</span>
                        <span className="flex items-center gap-1 text-accent-emerald font-medium">
                          <DollarSign className="w-3.5 h-3.5" /> {job.salary}
                        </span>
                      </>
                    )}
                    {job.experience_required && (
                      <>
                        <span>•</span>
                        <span className="text-slate-400">Exp: {job.experience_required}</span>
                      </>
                    )}
                  </div>
                </div>

                {/* Recruiter & Actions */}
                <div className="flex flex-wrap items-center gap-2.5">
                  {job.recruiter && (
                    <div className="px-3 py-1.5 rounded-xl bg-surfaceHover border border-surfaceBorder text-xs text-slate-300 flex items-center gap-2">
                      <UserCheck className="w-3.5 h-3.5 text-accent-emerald" />
                      <div>
                        <span className="font-semibold text-white">{job.recruiter.name}</span>
                        <span className="text-[10px] text-slate-400 block">{job.recruiter.title}</span>
                      </div>
                    </div>
                  )}

                  <button
                    onClick={() => onOpenApproval(job.id)}
                    className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold shadow-glow transition-all active:scale-95 flex items-center gap-1.5"
                  >
                    <span>Review Application</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </button>

                  <button
                    onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
                    className="p-2 rounded-xl bg-surfaceHover hover:bg-slate-700 text-slate-400 hover:text-white border border-surfaceBorder transition-all"
                  >
                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Skills Tags */}
              <div className="mt-3.5 pt-3 border-t border-surfaceBorder/60 flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-semibold text-slate-400 mr-1">Skills:</span>
                {job.skills.map((skill, sIdx) => {
                  const isMatched = match?.matched_skills.some((ms) => ms.toLowerCase() === skill.toLowerCase());
                  return (
                    <span
                      key={sIdx}
                      className={`px-2.5 py-0.5 rounded-md text-[11px] font-medium border ${
                        isMatched
                          ? 'bg-brand-950/40 text-brand-200 border-brand-500/30'
                          : 'bg-surfaceHover text-slate-400 border-surfaceBorder'
                      }`}
                    >
                      {skill}
                    </span>
                  );
                })}
              </div>

              {/* Expandable Match Breakdown Details */}
              {isExpanded && (
                <div className="mt-4 pt-4 border-t border-surfaceBorder space-y-3 animate-fade-in text-xs">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
                    <div className="p-3 rounded-xl bg-surface border border-surfaceBorder">
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">Skills Alignment (30%)</span>
                      <span className="text-sm font-extrabold text-brand-300">{match?.skills_score ?? 90}%</span>
                    </div>
                    <div className="p-3 rounded-xl bg-surface border border-surfaceBorder">
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">Experience Match (20%)</span>
                      <span className="text-sm font-extrabold text-accent-emerald">{match?.experience_score ?? 100}%</span>
                    </div>
                    <div className="p-3 rounded-xl bg-surface border border-surfaceBorder">
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">Role Relevance (20%)</span>
                      <span className="text-sm font-extrabold text-brand-300">{match?.role_score ?? 95}%</span>
                    </div>
                    <div className="p-3 rounded-xl bg-surface border border-surfaceBorder">
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">Location / Remote (15%)</span>
                      <span className="text-sm font-extrabold text-accent-cyan">{match?.location_score ?? 100}%</span>
                    </div>
                  </div>

                  {match?.reasoning && (
                    <div className="p-3 rounded-xl bg-brand-950/30 border border-brand-500/20 text-slate-300">
                      <span className="font-bold text-brand-300 block mb-1">Reasoning Analysis:</span>
                      {match.reasoning}
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2">
                    <div className="text-slate-400">
                      Canonical Hash: <span className="font-mono text-slate-300">{job.canonical_job_id?.slice(0, 16)}...</span>
                    </div>
                    {job.application_url && (
                      <a
                        href={job.application_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-brand-400 hover:text-brand-300 font-semibold"
                      >
                        <span>Official Job Portal</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
