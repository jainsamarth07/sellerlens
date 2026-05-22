import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Products from "./pages/Products";
import Chat from "./pages/Chat";
import Compare from "./pages/Compare";
import Settings from "./pages/Settings";
import Upload from "./pages/Upload";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import AuthCallback from "./pages/AuthCallback";
import PrivateRoute from "./components/PrivateRoute";
import OnboardingModal from "./components/OnboardingModal";

function Protected({ children }: { children: React.ReactNode }) {
  return (
    <PrivateRoute>
      <div className="flex h-full bg-slate-50">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">{children}</main>
        <OnboardingModal />
      </div>
    </PrivateRoute>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Public auth pages */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Protected app */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/upload" element={<Protected><Upload /></Protected>} />
      <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route path="/products" element={<Protected><Products /></Protected>} />
      <Route path="/chat" element={<Protected><Chat /></Protected>} />
      <Route path="/compare" element={<Protected><Compare /></Protected>} />
      <Route path="/settings" element={<Protected><Settings /></Protected>} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
