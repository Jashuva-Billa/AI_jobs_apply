import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { CopilotChat } from './components/CopilotChat';
import { JobsExplorer } from './components/JobsExplorer';
import { ApprovalModal } from './components/ApprovalModal';
import { ApplicationsPipeline } from './components/ApplicationsPipeline';
import { CandidateProfileView } from './components/CandidateProfileView';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';
import { api } from './services/api';
import { Job, ApprovalPackage, Application, CandidateProfile, DashboardStats } from './types';

export function App() {
  const [activeTab, setActiveTab] = useState<string>('copilot');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [approvals, setApprovals] = useState<ApprovalPackage[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [selectedApprovalPackage, setSelectedApprovalPackage] = useState<ApprovalPackage | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchAllData = async () => {
    try {
      const [jobsData, approvalsData, appsData, profileData, statsData] = await Promise.all([
        api.getJobs(),
        api.getApprovals(),
        api.getApplications(),
        api.getProfile(),
        api.getDashboardStats()
      ]);
      setJobs(jobsData);
      setApprovals(approvalsData);
      setApplications(appsData);
      setProfile(profileData);
      setStats(statsData);
    } catch (err) {
      console.error('Data fetch error:', err);
    }
  };

  useEffect(() => {
    fetchAllData();
    // Periodic refresh
    const interval = setInterval(fetchAllData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleOpenApprovalForJob = (jobId: string) => {
    const pkg = approvals.find((a) => a.job.id === jobId);
    if (pkg) {
      setSelectedApprovalPackage(pkg);
    } else {
      const fallbackJob = jobs.find((j) => j.id === jobId);
      if (fallbackJob) {
        setSelectedApprovalPackage({
          approval_id: `approval_${fallbackJob.id}`,
          application_id: fallbackJob.application_id || `app_${fallbackJob.id}`,
          job: fallbackJob,
          match: fallbackJob.match || {
            overall_score: 91,
            skills_score: 95,
            experience_score: 90,
            location_score: 100,
            role_score: 95,
            matched_skills: fallbackJob.skills,
            missing_skills: [],
            concerns: [],
            recommendation: 'STRONG_MATCH',
            reasoning: 'Strong match with candidate background.'
          },
          recruiter: fallbackJob.recruiter,
          package_data: {
            tailored_resume_summary: `Results-oriented Engineer with experience in ${fallbackJob.skills.slice(0, 3).join(', ')}.`,
            cover_letter: `Dear Hiring Team at ${fallbackJob.company},\n\nI am excited to apply for the ${fallbackJob.title} position...`
          },
          questions: [
            { question: 'How many years of Python experience do you have?', answer: '3.5 years', is_sensitive: false, needs_user_input: false, status: 'AUTO_GENERATED' },
            { question: 'What is your work authorization status?', answer: 'Authorized for remote worldwide employment', is_sensitive: true, needs_user_input: true, status: 'REQUIRES_APPROVAL' },
            { question: 'What are your compensation expectations?', answer: 'Competitive market rate', is_sensitive: true, needs_user_input: true, status: 'REQUIRES_APPROVAL' }
          ],
          email_outreach: {
            channel: 'EMAIL',
            subject: `Application: ${fallbackJob.title} — Candidate Profile`,
            body: `Hi there,\n\nI noticed the ${fallbackJob.title} opportunity at ${fallbackJob.company}. My background in Python, RAG, and LangGraph aligns directly with the team's goals.\n\nBest regards,\nCandidate`,
            recipient_email: fallbackJob.recruiter?.public_email || 'recruiting@company.com',
            recipient_name: fallbackJob.recruiter?.name || 'Recruiter'
          },
          linkedin_outreach: {
            channel: 'LINKEDIN',
            body: `Hi! I saw the ${fallbackJob.title} role at ${fallbackJob.company} and would love to connect to discuss my experience with LangGraph and RAG pipelines.`,
            recipient_name: fallbackJob.recruiter?.name || 'Recruiter'
          },
          created_at: new Date().toISOString()
        });
      }
    }
  };

  return (
    <div className="min-h-screen bg-background text-slate-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        pendingApprovalsCount={approvals.length}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'copilot' && (
          <CopilotChat
            onWorkflowComplete={fetchAllData}
            onNavigateToApprovals={() => setActiveTab('approvals')}
            onNavigateToJobs={() => setActiveTab('jobs')}
          />
        )}

        {activeTab === 'jobs' && (
          <JobsExplorer
            jobs={jobs}
            onOpenApproval={handleOpenApprovalForJob}
          />
        )}

        {activeTab === 'approvals' && (
          <div className="space-y-6 max-w-5xl mx-auto">
            <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder">
              <h1 className="text-xl font-bold text-white">Pending Human Approvals ({approvals.length})</h1>
              <p className="text-xs text-slate-400 mt-1">
                Every external communication, application submission, and sensitive response requires your explicit authorization.
              </p>
            </div>

            {approvals.length === 0 ? (
              <div className="glass-panel rounded-2xl p-12 border border-surfaceBorder text-center space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-surfaceHover flex items-center justify-center text-slate-400 mx-auto">
                  ✓
                </div>
                <h3 className="text-base font-bold text-white">All caught up!</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  No applications are currently awaiting human review. Run the AI Copilot to find new roles or review discovered jobs.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {approvals.map((pkg) => (
                  <div
                    key={pkg.approval_id}
                    className="glass-panel rounded-2xl p-5 border border-surfaceBorder flex flex-col md:flex-row md:items-center justify-between gap-4 glass-panel-hover"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-white text-base">{pkg.job.title}</h3>
                        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30">
                          {pkg.match.overall_score}% Match
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 font-medium">{pkg.job.company} • {pkg.job.location}</p>
                      {pkg.recruiter && (
                        <p className="text-[11px] text-slate-400">
                          Recruiter: <span className="text-brand-300">{pkg.recruiter.name}</span> ({pkg.recruiter.title})
                        </p>
                      )}
                    </div>

                    <button
                      onClick={() => setSelectedApprovalPackage(pkg)}
                      className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold shadow-glow transition-all active:scale-95"
                    >
                      Review & Authorize
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'pipeline' && (
          <ApplicationsPipeline
            applications={applications}
            onRefresh={fetchAllData}
            onOpenApproval={handleOpenApprovalForJob}
          />
        )}

        {activeTab === 'profile' && (
          <CandidateProfileView
            profile={profile}
            onProfileUpdated={fetchAllData}
          />
        )}

        {activeTab === 'analytics' && (
          <AnalyticsDashboard stats={stats} />
        )}
      </main>

      {/* Human Approval Review Modal */}
      {selectedApprovalPackage && (
        <ApprovalModal
          packageData={selectedApprovalPackage}
          onClose={() => setSelectedApprovalPackage(null)}
          onDecisionSubmitted={fetchAllData}
        />
      )}
    </div>
  );
}

export default App;
