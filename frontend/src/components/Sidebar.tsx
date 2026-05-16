import { NavLink, useNavigate } from "react-router-dom";
import {
  Home,
  Box,
  MessageCircle,
  BarChart2,
  Settings as SettingsIcon,
  Zap,
  Upload,
} from "lucide-react";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: Home },
  { to: "/products", label: "Products", icon: Box },
  { to: "/chat", label: "Chat with AI", icon: MessageCircle, badge: "NEW" },
  { to: "/compare", label: "Compare Months", icon: BarChart2 },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function Sidebar() {
  const navigate = useNavigate();

  return (
    <aside className="w-60 bg-navy-900 text-white flex flex-col h-full px-4 py-6">
      {/* Logo */}
      <div className="flex items-center gap-2 px-2 mb-8">
        <div className="bg-brand-green rounded-lg p-1.5">
          <Zap size={18} className="text-white" strokeWidth={2.5} />
        </div>
        <span className="text-xl font-bold tracking-tight">SellerLens</span>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 flex-1">
        {navItems.map(({ to, label, icon: Icon, badge }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <Icon size={18} />
            <span className="flex-1">{label}</span>
            {badge && (
              <span className="badge bg-brand-green text-white">{badge}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Upload */}
      <div className="mt-4">
        <button
          onClick={() => navigate("/upload")}
          className="w-full flex items-center justify-center gap-2 bg-brand-green hover:bg-emerald-700 text-white font-semibold py-2.5 rounded-lg transition"
        >
          <Upload size={16} />
          Upload Report
        </button>
      </div>

      {/* Powered by */}
      <div className="mt-4 text-center text-xs text-slate-400">
        Powered by <span className="text-white font-semibold">Azure AI</span>
      </div>
    </aside>
  );
}
