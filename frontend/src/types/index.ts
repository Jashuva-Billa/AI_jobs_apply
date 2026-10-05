export interface WorkExperienceItem {
  title: string;
  company: string;
  duration?: string;
  description?: string;
  technologies?: string[];
}

export interface EducationItem {
  degree: string;
  institution: string;
  year?: string;
}

export interface ProjectItem {
  name: string;
  description: string;
  technologies?: string[];
  link?: string;
}

export interface CandidateProfile {
  id?: string;
  name: string;
  email: string;
  phone?: string;
  location?: string;
  years_of_experience: number;
  summary?: string;
  skills: string[];
  technical_skills: string[];
  cloud_skills: string[];
  frameworks: string[];
  models: string[];
  databases: string[];
  certifications?: string[];
  education?: EducationItem[];
  work_experience?: WorkExperienceItem[];
  projects?: ProjectItem[];
  preferred_roles: string[];
  preferred_locations: string[];
  remote_preference: boolean;
  work_authorization?: string;
}

export interface MatchBreakdown {
  overall_score: number;
  skills_score: number;
  experience_score: number;
  location_score: number;
  role_score: number;
  matched_skills: string[];
  missing_skills: string[];
  concerns: string[];
  recommendation: 'STRONG_MATCH' | 'MATCH' | 'POSSIBLE_MATCH' | 'REJECT';
  reasoning?: string;
}

export interface Recruiter {
  id?: string;
  name: string;
  title: string;
  company_name: string;
  public_email?: string;
  linkedin_url?: string;
  source_evidence?: string;
}

export interface Job {
  id: string;
  canonical_job_id?: string;
  company: string;
  title: string;
  location: string;
  remote: boolean;
  employment_type: string;
  experience_required?: string;
  salary?: string;
  description: string;
  requirements: string[];
  skills: string[];
  application_url?: string;
  source_url?: string;
  posted_date?: string;
  company_url?: string;
  created_at: string;
  match?: MatchBreakdown;
  recruiter?: Recruiter;
  application_id?: string;
  status?: string;
}

export interface OutreachMessage {
  id?: string;
  application_id?: string;
  recruiter_id?: string;
  channel: 'EMAIL' | 'LINKEDIN' | 'FOLLOW_UP';
  subject?: string;
  body: string;
  recipient_email?: string;
  recipient_name?: string;
  status?: string;
  sent_at?: string;
}

export interface ApplicationQuestion {
  id?: string;
  question: string;
  answer?: string;
  is_sensitive: boolean;
  needs_user_input: boolean;
  status: string;
}

export interface ApprovalPackage {
  approval_id: string;
  application_id: string;
  job: Job;
  match: MatchBreakdown;
  recruiter?: Recruiter;
  package_data?: {
    tailored_resume_summary?: string;
    tailored_resume_text?: string;
    highlighted_skills?: string[];
    cover_letter?: string;
  };
  questions: ApplicationQuestion[];
  email_outreach?: OutreachMessage;
  linkedin_outreach?: OutreachMessage;
  created_at: string;
}

export interface Application {
  id: string;
  candidate_id: string;
  job_id: string;
  status: string;
  applied_at?: string;
  notes?: string;
  job?: Job;
  match?: MatchBreakdown;
  recruiter?: Recruiter;
  outreaches: OutreachMessage[];
  created_at: string;
  updated_at: string;
}

export interface AgentEvent {
  id: string;
  agent_name: string;
  step: string;
  message: string;
  payload?: any;
  timestamp: string;
}

export interface AgentRun {
  id: string;
  user_prompt: string;
  status: string;
  current_step: string;
  summary: any;
  latency_ms: number;
  started_at: string;
  completed_at?: string;
  events: AgentEvent[];
}

export interface DashboardStats {
  jobs_found: number;
  strong_matches: number;
  applications: number;
  recruiters_found: number;
  emails_sent: number;
  responses: number;
  interviews: number;
  status_breakdown: Record<string, number>;
  role_distribution: Record<string, number>;
  score_distribution: Record<string, number>;
  recent_runs: Array<{
    id: string;
    prompt: string;
    status: string;
    latency_ms: number;
    started_at: string;
  }>;
}
