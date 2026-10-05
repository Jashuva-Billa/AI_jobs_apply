import React from 'react';
import { 
  Bot, 
  Briefcase, 
  CheckSquare, 
  Kanban, 
  User, 
  BarChart3, 
  ShieldCheck, 
  Sparkles,
  Zap
} from 'lucide-react';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  pendingApprovalsCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  pendingApprovalsCount
}) => {
  const navItems = [
    { id: 'copilot', label: 'AI Copilot', icon: Bot },
    { id: 'jobs', label: 'Discovered Jobs', icon: Briefcase },
    { 
      id: 'approvals', 
      label: 'Human Approvals', 
      icon: CheckSquare, 
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined 
    },
    { id: 'pipeline', label: 'Applications Pipeline', icon: Kanban },
    { id: 'profile', label: 'Candidate Profile', icon: User },
    { id: 'analytics', label: 'Analytics & KPIs', icon: BarChart3 },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-surfaceBorder bg-surface/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('copilot')}>
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-brand-600 via-indigo-500 to-accent-cyan flex items-center justify-center shadow-glow">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-white tracking-tight">Antigravity AI</span>
                <span className="px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase bg-brand-500/20 text-brand-300 border border-brand-500/30 rounded-full">
                  Agentic
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium">Job Search & Outreach Platform</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all relative ${
                    isActive
                      ? 'bg-brand-600/15 text-brand-300 border border-brand-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-surfaceHover'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-brand-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                  {item.badge !== undefined && (
                    <span className="ml-1.5 px-2 py-0.5 text-xs font-bold bg-accent-rose text-white rounded-full animate-pulse-subtle">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Status Badges */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surfaceHover border border-surfaceBorder text-xs text-slate-300">
              <ShieldCheck className="w-4 h-4 text-accent-emerald" />
              <span className="text-[11px] font-medium">Zero-Scraping / Compliant</span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-brand-950/60 border border-brand-700/40 text-xs text-brand-300">
              <Zap className="w-3.5 h-3.5 text-accent-amber animate-pulse" />
              <span className="text-[11px] font-semibold">LangGraph Active</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Mobile nav bar */}
      <div className="md:hidden flex overflow-x-auto px-4 py-2 border-t border-surfaceBorder bg-surface space-x-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs whitespace-nowrap font-medium ${
                isActive ? 'bg-brand-600 text-white' : 'text-slate-400 hover:bg-surfaceHover'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{item.label}</span>
              {item.badge !== undefined && (
                <span className="px-1.5 py-0.2 text-[10px] bg-accent-rose text-white rounded-full">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </header>
  );
};
