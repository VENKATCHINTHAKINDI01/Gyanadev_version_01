import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ChatPage from "./pages/ChatPage";
import ProgressPage from "./pages/ProgressPage";
import { isLoggedIn } from "./utils/api";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  return isLoggedIn() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login"     element={<LoginPage />} />
        <Route path="/dashboard" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
        <Route path="/chat"      element={<PrivateRoute><ChatPage /></PrivateRoute>} />
        <Route path="/progress"  element={<PrivateRoute><ProgressPage /></PrivateRoute>} />
        <Route path="*"          element={<Navigate to={isLoggedIn() ? "/dashboard" : "/login"} />} />
      </Routes>
    </BrowserRouter>
  );
}