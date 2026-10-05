import axios from 'axios';
import type {
  CandidateProfile,
  Job,
  ApprovalPackage,
  Application,
  DashboardStats,
  AgentRun
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  // Candidates
  getProfile: async (): Promise<CandidateProfile> => {
    const res = await client.get('/candidates/profile');
    return res.data;
  },
  updateProfile: async (data: CandidateProfile): Promise<CandidateProfile> => {
    const res = await client.put('/candidates/profile', data);
    return res.data;
  },
  uploadResume: async (file: File): Promise<CandidateProfile> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await client.post('/candidates/resume', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  // Agent Execution
  runAgent: async (prompt: string, candidate_id?: string) => {
    const res = await client.post('/agent/run', { prompt, candidate_id });
    return res.data;
  },
  getAgentRun: async (runId: string): Promise<AgentRun> => {
    const res = await client.get(`/agent/runs/${runId}`);
    return res.data;
  },

  // Jobs
  getJobs: async (minScore?: number, remoteOnly?: boolean): Promise<Job[]> => {
    const params: Record<string, any> = {};
    if (minScore !== undefined) params.min_score = minScore;
    if (remoteOnly) params.remote_only = remoteOnly;
    const res = await client.get('/jobs', { params });
    return res.data;
  },
  getJob: async (jobId: string): Promise<Job> => {
    const res = await client.get(`/jobs/${jobId}`);
    return res.data;
  },

  // Approvals
  getApprovals: async (): Promise<ApprovalPackage[]> => {
    const res = await client.get('/approvals');
    return res.data;
  },
  decideApproval: async (
    approvalId: string,
    decision: {
      decision: 'APPROVE' | 'REJECT' | 'MODIFY';
      modified_email_subject?: string;
      modified_email_body?: string;
      modified_linkedin_body?: string;
      modified_answers?: Record<string, string>;
      send_email?: boolean;
    }
  ) => {
    const res = await client.post(`/approvals/${approvalId}/decide`, decision);
    return res.data;
  },

  // Applications
  getApplications: async (): Promise<Application[]> => {
    const res = await client.get('/applications');
    return res.data;
  },
  updateApplicationStatus: async (applicationId: string, status: string, notes?: string) => {
    const res = await client.patch(`/applications/${applicationId}/status`, { status, notes });
    return res.data;
  },

  // Analytics
  getDashboardStats: async (): Promise<DashboardStats> => {
    const res = await client.get('/analytics/dashboard');
    return res.data;
  },

  // Auth / Integrations
  getAuthStatus: async () => {
    const res = await client.get('/auth/status');
    return res.data;
  }
};
