import React, { useState, useRef } from 'react';
import { 
  User, 
  Upload, 
  FileText, 
  CheckCircle2, 
  Sparkles, 
  Save, 
  Briefcase, 
  Layers, 
  Cloud, 
  Cpu, 
  Database,
  MapPin,
  Mail,
  Phone
} from 'lucide-react';
import { CandidateProfile } from '../types';
import { api } from '../services/api';

interface CandidateProfileViewProps {
  profile: CandidateProfile | null;
  onProfileUpdated: () => void;
}

export const CandidateProfileView: React.FC<CandidateProfileViewProps> = ({
  profile,
  onProfileUpdated
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [formData, setFormData] = useState<CandidateProfile | null>(profile);
  const [isSaving, setIsSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    setFormData(profile);
  }, [profile]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadSuccess(null);
    try {
      const updated = await api.uploadResume(file);
      setFormData(updated);
      setUploadSuccess(`Parsed resume successfully: ${file.name}`);
      onProfileUpdated();
    } catch (err) {
      console.error('Resume upload failed:', err);
      alert('Resume extraction encountered an issue. Please try another file or plain text.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!formData) return;
    setIsSaving(true);
    try {
      await api.updateProfile(formData);
      setUploadSuccess('Candidate profile saved successfully.');
      onProfileUpdated();
    } catch (err) {
      console.error('Save failed:', err);
    } finally {
      setIsSaving(false);
    }
  };

  if (!formData) {
    return <div className="text-center p-8 text-slate-400">Loading candidate profile...</div>;
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Resume Upload Dropzone */}
      <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Upload className="w-5 h-5 text-brand-400" />
              Upload Resume (PDF or DOCX)
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Upload your resume once. Our Candidate Agent will extract your structured skills, experience, and projects.
            </p>
          </div>

          <div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".pdf,.txt,.docx"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white text-xs font-bold shadow-glow flex items-center gap-2 transition-all active:scale-95 cursor-pointer"
            >
              {isUploading ? (
                <>
                  <Cpu className="w-4 h-4 animate-spin text-accent-cyan" />
                  <span>Parsing Resume...</span>
                </>
              ) : (
                <>
                  <FileText className="w-4 h-4" />
                  <span>Upload & Parse Resume</span>
                </>
              )}
            </button>
          </div>
        </div>

        {uploadSuccess && (
          <div className="mt-4 p-3 rounded-xl bg-accent-emerald/15 border border-accent-emerald/30 text-accent-emerald text-xs font-semibold flex items-center gap-2 animate-fade-in">
            <CheckCircle2 className="w-4 h-4" />
            <span>{uploadSuccess}</span>
          </div>
        )}
      </div>

      {/* Candidate Profile Form */}
      <div className="glass-panel rounded-2xl p-6 border border-surfaceBorder space-y-6">
        <div className="flex items-center justify-between pb-4 border-b border-surfaceBorder">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <User className="w-5 h-5 text-brand-400" />
              Candidate Profile & Preferences
            </h3>
            <p className="text-xs text-slate-400">Verified data utilized by matching and application agents.</p>
          </div>

          <button
            onClick={handleSaveProfile}
            disabled={isSaving}
            className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold shadow-sm flex items-center gap-1.5 transition-all"
          >
            <Save className="w-4 h-4" />
            <span>{isSaving ? 'Saving...' : 'Save Profile'}</span>
          </button>
        </div>

        {/* Basic Fields */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block text-slate-400 font-semibold mb-1">Full Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full bg-background border border-surfaceBorder rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
            />
          </div>

          <div>
            <label className="block text-slate-400 font-semibold mb-1">Email Address</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full bg-background border border-surfaceBorder rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
            />
          </div>

          <div>
            <label className="block text-slate-400 font-semibold mb-1">Years of Experience</label>
            <input
              type="number"
              step="0.5"
              value={formData.years_of_experience}
              onChange={(e) => setFormData({ ...formData, years_of_experience: parseFloat(e.target.value) || 0 })}
              className="w-full bg-background border border-surfaceBorder rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
            />
          </div>
        </div>

        {/* Summary */}
        <div className="text-xs">
          <label className="block text-slate-400 font-semibold mb-1">Professional Summary</label>
          <textarea
            rows={3}
            value={formData.summary || ''}
            onChange={(e) => setFormData({ ...formData, summary: e.target.value })}
            className="w-full bg-background border border-surfaceBorder rounded-xl p-3 text-white focus:outline-none focus:border-brand-500 leading-relaxed font-sans"
          />
        </div>

        {/* Skills Taxonomy Badges */}
        <div className="space-y-4 pt-4 border-t border-surfaceBorder text-xs">
          <h4 className="font-bold text-white flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-brand-400" />
            Skills Taxonomy
          </h4>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Core & Technical Skills */}
            <div className="p-4 rounded-xl bg-surfaceHover border border-surfaceBorder space-y-2">
              <span className="text-slate-300 font-semibold block">Core Technical Skills</span>
              <div className="flex flex-wrap gap-1.5">
                {(formData.skills || []).map((s, idx) => (
                  <span key={idx} className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-200 border border-brand-500/30">
                    {s}
                  </span>
                ))}
              </div>
            </div>

            {/* Cloud & LLMs */}
            <div className="p-4 rounded-xl bg-surfaceHover border border-surfaceBorder space-y-2">
              <span className="text-slate-300 font-semibold block">Cloud, Models & Frameworks</span>
              <div className="flex flex-wrap gap-1.5">
                {[...(formData.cloud_skills || []), ...(formData.frameworks || []), ...(formData.models || [])].map((s, idx) => (
                  <span key={idx} className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/25">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Experience & Projects */}
        <div className="space-y-3 pt-4 border-t border-surfaceBorder text-xs">
          <h4 className="font-bold text-white flex items-center gap-1.5">
            <Briefcase className="w-4 h-4 text-accent-emerald" />
            Work Experience Highlights
          </h4>
          <div className="space-y-2">
            {(formData.work_experience || []).map((exp, idx) => (
              <div key={idx} className="p-3.5 rounded-xl bg-background border border-surfaceBorder">
                <div className="flex items-center justify-between font-bold text-white">
                  <span>{exp.title} — {exp.company}</span>
                  <span className="text-slate-400 font-normal text-[11px]">{exp.duration}</span>
                </div>
                <p className="text-slate-300 mt-1 text-[11px] leading-relaxed">{exp.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
