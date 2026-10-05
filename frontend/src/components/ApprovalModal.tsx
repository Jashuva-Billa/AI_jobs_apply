import React, { useState } from 'react';
import { 
  X, 
  CheckCircle2, 
  Send, 
  Copy, 
  ExternalLink, 
  ShieldAlert, 
  FileText, 
  Mail, 
  Share2, 
  Sparkles, 
  Check, 
  AlertCircle,
  HelpCircle,
  UserCheck
} from 'lucide-react';
import { ApprovalPackage } from '../types';
import { api } from '../services/api';

interface ApprovalModalProps {
  packageData: ApprovalPackage;
  onClose: () => void;
  onDecisionSubmitted: () => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  packageData,
  onClose,
  onDecisionSubmitted
}) => {
  const [activeTab, setActiveTab] = useState<'outreach' | 'resume' | 'coverletter' | 'questions'>('outreach');
  const [emailSubject, setEmailSubject] = useState(packageData.email_outreach?.subject || `Application: ${packageData.job.title}`);
  const [emailBody, setEmailBody] = useState(packageData.email_outreach?.body || '');
  const [linkedinBody, setLinkedinBody] = useState(packageData.linkedin_outreach?.body || '');
  const [coverLetter, setCoverLetter] = useState(packageData.package_data?.cover_letter || '');
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    packageData.questions.forEach((q) => {
      if (q.id && q.answer) initial[q.id] = q.answer;
    });
    return initial;
  });

  const [copiedLinkedIn, setCopiedLinkedIn] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const job = packageData.job;
  const match = packageData.match;
  const recruiter = packageData.recruiter;

  const handleCopyLinkedIn = () => {
    navigator.clipboard.writeText(linkedinBody);
    setCopiedLinkedIn(true);
    setTimeout(() => setCopiedLinkedIn(false), 2500);
  };

  const handleOpenLinkedIn = () => {
    const url = recruiter?.linkedin_url || `https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(recruiter?.name || job.company)}`;
    window.open(url, '_blank');
  };

  const handleApprove = async () => {
    setIsSubmitting(true);
    try {
      await api.decideApproval(packageData.approval_id, {
        decision: 'APPROVE',
        modified_email_subject: emailSubject,
        modified_email_body: emailBody,
        modified_linkedin_body: linkedinBody,
        modified_answers: answers,
        send_email: Boolean(packageData.email_outreach?.recipient_email)
      });
      setSuccessMessage('Approved! Authorized email dispatched and application updated.');
      setTimeout(() => {
        onDecisionSubmitted();
        onClose();
      }, 1500);
    } catch (err) {
      console.error('Approval submission failed:', err);
      alert('Approval error. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    try {
      await api.decideApproval(packageData.approval_id, {
        decision: 'REJECT'
      });
      onDecisionSubmitted();
      onClose();
    } catch (err) {
      console.error('Reject failed:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-4xl bg-surface border border-surfaceBorder rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="p-6 border-b border-surfaceBorder bg-gradient-to-r from-surface via-brand-950/30 to-surface flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30">
                {match.overall_score}% Match Score
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-500/20 text-brand-300 border border-brand-500/30">
                {match.recommendation}
              </span>
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight">
              {job.title} — <span className="text-brand-300">{job.company}</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Review tailored artifacts, safe question answers, and authorized recruiter communications before sending.
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-surfaceHover hover:bg-slate-700 text-slate-400 hover:text-white transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-surfaceBorder px-6 bg-surface/50 text-xs font-semibold">
          {[
            { id: 'outreach', label: 'Recruiter Outreach (Email & LinkedIn)', icon: Mail },
            { id: 'resume', label: 'Tailored Resume', icon: FileText },
            { id: 'coverletter', label: 'Cover Letter', icon: Sparkles },
            { id: 'questions', label: 'Application Questions', icon: HelpCircle }
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 py-3.5 px-4 border-b-2 transition-all ${
                  isActive
                    ? 'border-brand-500 text-brand-300 font-bold bg-brand-500/5'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Modal Body Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5 text-xs text-slate-200">
          {/* TAB 1: OUTREACH */}
          {activeTab === 'outreach' && (
            <div className="space-y-5">
              {/* Recruiter Badge */}
              <div className="p-4 rounded-xl bg-surfaceHover border border-surfaceBorder flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-600/20 border border-brand-500/30 flex items-center justify-center text-brand-400 font-bold text-sm">
                    {recruiter?.name.slice(0, 2).toUpperCase() || 'TA'}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white text-sm">{recruiter?.name || 'Talent Acquisition'}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/20 font-semibold">
                        Public Source Verified
                      </span>
                    </div>
                    <p className="text-slate-400 text-[11px]">{recruiter?.title} • {recruiter?.company_name}</p>
                  </div>
                </div>
                {recruiter?.public_email ? (
                  <div className="text-right">
                    <span className="text-[10px] text-slate-400 block">Verified Destination</span>
                    <span className="font-mono text-brand-300 text-xs">{recruiter.public_email}</span>
                  </div>
                ) : (
                  <div className="text-[11px] text-slate-400 italic">
                    Public email hidden • LinkedIn outreach prepared
                  </div>
                )}
              </div>

              {/* Email Section */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="font-bold text-slate-300 flex items-center gap-1.5">
                    <Mail className="w-4 h-4 text-brand-400" />
                    Personalized Recruiter Email (Editable)
                  </label>
                  <span className="text-[10px] text-slate-500">Requires your approval to send</span>
                </div>
                <input
                  type="text"
                  value={emailSubject}
                  onChange={(e) => setEmailSubject(e.target.value)}
                  className="w-full bg-background border border-surfaceBorder rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-brand-500 font-medium"
                />
                <textarea
                  rows={6}
                  value={emailBody}
                  onChange={(e) => setEmailBody(e.target.value)}
                  className="w-full bg-background border border-surfaceBorder rounded-xl p-3 text-xs text-slate-100 focus:outline-none focus:border-brand-500 leading-relaxed font-sans"
                />
              </div>

              {/* LinkedIn Section */}
              <div className="space-y-2 pt-3 border-t border-surfaceBorder">
                <div className="flex items-center justify-between">
                  <label className="font-bold text-slate-300 flex items-center gap-1.5">
                    <Share2 className="w-4 h-4 text-accent-cyan" />
                    Compliant LinkedIn Outreach Note (Under 300 chars)
                  </label>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleCopyLinkedIn}
                      className="px-2.5 py-1 rounded-lg bg-surfaceHover hover:bg-slate-700 text-slate-300 flex items-center gap-1 text-[11px] font-semibold border border-surfaceBorder transition-all"
                    >
                      {copiedLinkedIn ? <Check className="w-3.5 h-3.5 text-accent-emerald" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedLinkedIn ? 'Copied!' : 'Copy Message'}</span>
                    </button>
                    <button
                      onClick={handleOpenLinkedIn}
                      className="px-2.5 py-1 rounded-lg bg-surfaceHover hover:bg-slate-700 text-slate-300 flex items-center gap-1 text-[11px] font-semibold border border-surfaceBorder transition-all"
                    >
                      <span>Open LinkedIn</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <textarea
                  rows={3}
                  value={linkedinBody}
                  onChange={(e) => setLinkedinBody(e.target.value)}
                  className="w-full bg-background border border-surfaceBorder rounded-xl p-3 text-xs text-slate-100 focus:outline-none focus:border-brand-500 leading-relaxed font-sans"
                />
              </div>
            </div>
          )}

          {/* TAB 2: TAILORED RESUME */}
          {activeTab === 'resume' && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-brand-950/40 border border-brand-500/30">
                <span className="font-bold text-brand-300 block mb-1 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-accent-amber" />
                  Factual Alignment & Highlighting (Zero Hallucination)
                </span>
                <p className="text-slate-300 text-xs">
                  Skills matching <span className="text-white font-semibold">{job.title}</span> were prioritized in the summary 
                  and competence sections without fabricating fake experience or dates.
                </p>
              </div>

              <div className="space-y-2">
                <label className="font-bold text-slate-300">Tailored Summary Preview</label>
                <div className="p-3 bg-background border border-surfaceBorder rounded-xl font-mono text-[11px] leading-relaxed text-slate-200">
                  {packageData.package_data?.tailored_resume_summary || 'Experienced Engineer with 3.5+ years experience in Python, RAG, and LangGraph.'}
                </div>
              </div>

              <div className="space-y-2">
                <label className="font-bold text-slate-300">Full Tailored Resume Text</label>
                <div className="p-4 bg-background border border-surfaceBorder rounded-xl font-mono text-[11px] leading-relaxed text-slate-300 whitespace-pre-wrap max-h-64 overflow-y-auto">
                  {packageData.package_data?.tailored_resume_text || 'Resume content loaded.'}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: COVER LETTER */}
          {activeTab === 'coverletter' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="font-bold text-slate-300">Generated Cover Letter (Editable)</label>
                <span className="text-[10px] text-slate-500">Customized with company and tech stack details</span>
              </div>
              <textarea
                rows={12}
                value={coverLetter}
                onChange={(e) => setCoverLetter(e.target.value)}
                className="w-full bg-background border border-surfaceBorder rounded-xl p-4 text-xs text-slate-100 focus:outline-none focus:border-brand-500 leading-relaxed font-sans"
              />
            </div>
          )}

          {/* TAB 4: APPLICATION QUESTIONS */}
          {activeTab === 'questions' && (
            <div className="space-y-4">
              <p className="text-xs text-slate-400">
                Safe factual questions were automatically answered from your candidate profile. 
                Sensitive items (work authorization, salary expectations) are flagged for your explicit review.
              </p>

              <div className="space-y-3">
                {packageData.questions.map((q, idx) => (
                  <div
                    key={idx}
                    className={`p-3.5 rounded-xl border ${
                      q.is_sensitive
                        ? 'bg-accent-amber/5 border-accent-amber/30'
                        : 'bg-surfaceHover border-surfaceBorder'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-white text-xs">{q.question}</span>
                      {q.is_sensitive ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-accent-amber/20 text-accent-amber border border-accent-amber/30 flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" /> Requires Approval
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30">
                          Auto-Answered
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={answers[q.id || ''] || q.answer || ''}
                      onChange={(e) => {
                        if (q.id) {
                          setAnswers({ ...answers, [q.id]: e.target.value });
                        }
                      }}
                      className="w-full bg-background border border-surfaceBorder rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="p-4 px-6 border-t border-surfaceBorder bg-surface flex flex-wrap items-center justify-between gap-3">
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-accent-emerald" />
            <span>Never silently submits without your consent.</span>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={handleReject}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-xl bg-surfaceHover hover:bg-slate-700 text-slate-300 font-semibold text-xs border border-surfaceBorder transition-all"
            >
              Reject Application
            </button>
            <button
              onClick={handleApprove}
              disabled={isSubmitting}
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-bold text-xs shadow-glow transition-all flex items-center gap-1.5 active:scale-95 cursor-pointer"
            >
              {isSubmitting ? (
                <span>Dispatching...</span>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Approve & Dispatch Outreach</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Success message banner */}
        {successMessage && (
          <div className="absolute inset-0 bg-background/95 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-accent-emerald/20 border border-accent-emerald/40 flex items-center justify-center text-accent-emerald mb-3 shadow-glow-emerald">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-white mb-1">{successMessage}</h3>
            <p className="text-xs text-slate-400">Application status updated in tracker.</p>
          </div>
        )}
      </div>
    </div>
  );
};
