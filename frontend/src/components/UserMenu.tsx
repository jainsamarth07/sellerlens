import { useNavigate } from "react-router-dom";
import { LogOut, Mail } from "lucide-react";
import MicrosoftLogo from "./MicrosoftLogo";
import { useAuthStore } from "../store/useAuth";

const AVATAR_COLORS = [
  "bg-emerald-500",
  "bg-amber-500",
  "bg-blue-500",
  "bg-pink-500",
  "bg-violet-500",
  "bg-rose-500",
  "bg-teal-500",
  "bg-orange-500",
];

function hashLetter(letter: string): string {
  const idx = (letter.toUpperCase().charCodeAt(0) - 65 + 26) % 26;
  return AVATAR_COLORS[idx % AVATAR_COLORS.length];
}

function initials(name: string | null | undefined, email: string): string {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return src.slice(0, 2).toUpperCase();
}

export default function UserMenu() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  if (!user) return null;

  const isMs = user.auth_provider === "microsoft";
  const name = user.business_name || user.email;
  const inits = initials(user.business_name, user.email);
  const tone = hashLetter(inits[0] || "?");

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="mt-4 border-t border-white/10 pt-4 flex items-center gap-3 px-1">
      {user.avatar_url ? (
        // eslint-disable-next-line jsx-a11y/alt-text
        <img
          src={user.avatar_url}
          className="w-9 h-9 rounded-full object-cover"
        />
      ) : (
        <div
          className={`w-9 h-9 rounded-full ${tone} text-white text-xs font-bold flex items-center justify-center shrink-0`}
        >
          {inits}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-white truncate">{name}</div>
        <div className="text-[11px] text-slate-400 truncate">{user.email}</div>
        <div className="flex items-center gap-1 mt-0.5 text-[10px] text-slate-300">
          {isMs ? <MicrosoftLogo size={10} /> : <Mail size={10} />}
          <span>{isMs ? "Microsoft" : "Email login"}</span>
        </div>
      </div>
      <button
        onClick={handleLogout}
        title="Log out"
        className="text-slate-400 hover:text-white p-1.5 rounded hover:bg-white/5"
        aria-label="Log out"
      >
        <LogOut size={14} />
      </button>
    </div>
  );
}
