import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Dashboard from "./pages/Dashboard";
import LiveMonitoring from "./pages/LiveMonitoring";
import NetworkIntelligence from "./pages/NetworkIntelligence";
import SentimentTimeline from "./pages/SentimentTimeline";
import Trends from "./pages/Trends";
import Demographics from "./pages/Demographics";
import Ledger from "./pages/Ledger";
import AdminApprovals from "./pages/AdminApprovals";
import Settings from "./pages/Settings";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("socmint_access_token");
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<SignIn />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />

        <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/live" element={<RequireAuth><LiveMonitoring /></RequireAuth>} />
        <Route path="/network" element={<RequireAuth><NetworkIntelligence /></RequireAuth>} />
        <Route path="/sentiment" element={<RequireAuth><SentimentTimeline /></RequireAuth>} />
        <Route path="/trends" element={<RequireAuth><Trends /></RequireAuth>} />
        <Route path="/demographics" element={<RequireAuth><Demographics /></RequireAuth>} />
        <Route path="/ledger" element={<RequireAuth><Ledger /></RequireAuth>} />
        <Route path="/admin" element={<RequireAuth><AdminApprovals /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
