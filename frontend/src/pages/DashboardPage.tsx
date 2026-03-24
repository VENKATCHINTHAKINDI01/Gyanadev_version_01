import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getProfile, getProgress, getWelcome,
  logout, Student, Progress, WelcomeResponse,
} from "../utils/api";
import { SwordsIcon, BowIcon, LotusIcon, BookIcon, FlameIcon, SpeechIcon } from "../components/Icons";

const BOOKS = [
  { id: "mahabharata",   label: "Mahabharata",  icon: <SwordsIcon size={36} color="#ffc837" />, color: "#ffc837" },
  { id: "ramayana",      label: "Ramayana",      icon: <BowIcon size={36} color="#60a5fa" />, color: "#60a5fa" },
  { id: "bhagavad_gita", label: "Bhagavad Gita", icon: <LotusIcon size={36} color="#a78bfa" />, color: "#a78bfa" },
];

export default function DashboardPage() {
  const nav = useNavigate();
  const [student, setStudent] = useState<Student | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [welcome, setWelcome] = useState<WelcomeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getProfile(), getProgress(), getWelcome()])
      .then(([s, p, w]) => { setStudent(s); setProgress(p); setWelcome(w); })
      .catch(() => nav("/login"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loader />;
  if (!student || !progress) return null;

  const firstName = student.name.split(" ")[0];

  return (
    <div style={pageStyle}>
      {/* Header */}
      <header style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 32, color: "#ffc837", filter: "drop-shadow(0 0 8px rgba(255,160,0,0.4))" }}>ॐ</span>
          <span className="cinzel" style={{ fontWeight: 700, fontSize: 20, color: "#ffc837", letterSpacing: "1px" }}>GyanaDev</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 13, color: "#cbd5e1" }}>Namaste, {firstName}-ji 🙏</span>
          <button onClick={logout} style={logoutBtn}>Logout</button>
        </div>
      </header>

      <div style={{ maxWidth: 780, margin: "0 auto", padding: "24px 16px" }}>

        {/* Welcome back banner */}
        {welcome?.is_returning && welcome.message && (
          <div className="glass-panel" style={welcomeBanner}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}><LotusIcon size={24} color="#fca5a5" /></div>
            <span style={{ flex: 1, fontSize: 15, color: "#f8fafc" }}>{welcome.message}</span>
            <button onClick={() => nav("/chat")} className="btn-primary" style={continueBtn}>
              Continue →
            </button>
          </div>
        )}

        {/* Streak */}
        {progress.streak_days > 0 && (
          <div style={streakBadge}>
            <span style={{ display: "inline-block", verticalAlign: "middle", marginRight: 4, marginTop: -2 }}><FlameIcon size={16} color="#ffc837" /></span> {progress.streak_days} day{progress.streak_days > 1 ? "s" : ""} study streak!
          </div>
        )}

        {/* Score cards */}
        <h2 className="cinzel" style={sectionTitle}>Your Progress</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 32 }}>
          <ScoreCard
            label="Knowledge"
            score={progress.knowledge_score}
            max={100}
            color="#ffc837"
            icon={<BookIcon size={28} color="#ffc837" />}
            desc={`Level: ${progress.teaching_level}`}
          />
          <ScoreCard
            label="Enthusiasm"
            score={progress.enthusiasm_score}
            max={100}
            color="#4ade80"
            icon={<FlameIcon size={28} color="#4ade80" />}
            desc={`${progress.total_interactions} sessions`}
          />
          <ScoreCard
            label="Pronunciation"
            score={progress.pronunciation_score}
            max={100}
            color="#a78bfa"
            icon={<SpeechIcon size={28} color="#a78bfa" />}
            desc="Sanskrit accuracy"
          />
        </div>

        {/* Choose a book */}
        <h2 className="cinzel" style={sectionTitle}>Start Learning</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 32 }}>
          {BOOKS.map((b) => (
            <button key={b.id}
              className="glass-panel"
              onClick={() => nav(`/chat?book=${b.id}`)}
              style={{ ...bookCard, border: `1px solid ${b.color}40`, boxShadow: `0 4px 20px ${b.color}15` }}>
              <span style={{ marginBottom: 12, filter: `drop-shadow(0 0 10px ${b.color}90)` }}>{b.icon}</span>
              <span className="cinzel" style={{ fontWeight: 600, color: b.color, fontSize: 15, letterSpacing: "0.5px" }}>{b.label}</span>
              {student.last_book === b.id && (
                <span style={{ fontSize: 11, color: "#94a3b8", marginTop: 6, background: "rgba(255,255,255,0.05)", padding: "2px 8px", borderRadius: 10 }}>Last studied</span>
              )}
            </button>
          ))}
        </div>

        {/* Quick ask button */}
        <button className="btn-primary" onClick={() => nav("/chat")}
          style={{
            width: "100%", padding: "18px 0", borderRadius: 16,
            fontSize: 16, cursor: "pointer", letterSpacing: "0.5px"
          }}>
          Ask the Guru 🙏
        </button>

        {/* Stats footer */}
        <div style={{ display: "flex", justifyContent: "center", gap: 32, marginTop: 32 }}>
          <Stat label="Sessions" value={progress.total_interactions} />
          <Stat label="Streak" value={`${progress.streak_days}d`} />
          <Stat label="Level" value={progress.teaching_level} />
        </div>
      </div>
    </div>
  );
}

function ScoreCard({ label, score, max, color, icon, desc }: {
  label: string; score: number; max: number;
  color: string; icon: React.ReactNode; desc: string;
}) {
  const pct = Math.min(100, (score / max) * 100);
  return (
    <div className="glass-panel" style={{
      padding: "20px 16px",
      textAlign: "center",
      transition: "transform 0.2s",
    }}>
      <div style={{ marginBottom: 8, display: "flex", justifyContent: "center", filter: `drop-shadow(0 0 8px ${color}80)` }}>{icon}</div>
      <div style={{ fontWeight: 500, fontSize: 13, color: "#cbd5e1", marginBottom: 12 }}>{label}</div>
      <div style={{
        height: 6, background: "rgba(0,0,0,0.3)", borderRadius: 3,
        overflow: "hidden", marginBottom: 10, border: "1px solid rgba(255,255,255,0.05)"
      }}>
        <div style={{
          height: "100%", width: `${pct}%`,
          background: color, borderRadius: 3,
          boxShadow: `0 0 10px ${color}`,
          transition: "width 0.8s ease",
        }} />
      </div>
      <div style={{ fontWeight: 700, fontSize: 20, color }}>{score.toFixed(0)}</div>
      <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>{desc}</div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div className="cinzel" style={{ fontWeight: 700, fontSize: 24, color: "#ffc837", textShadow: "0 2px 10px rgba(255,200,55,0.3)" }}>{value}</div>
      <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 4 }}>{label}</div>
    </div>
  );
}

function Loader() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "transparent" }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 56, color: "#ffc837", marginBottom: 16, animation: "glowFloat 2s infinite ease-in-out" }}>ॐ</div>
        <p style={{ color: "#cbd5e1", fontSize: 15, fontWeight: 500, letterSpacing: "1px" }}>Loading your journey…</p>
      </div>
    </div>
  );
}

// Styles
const pageStyle: React.CSSProperties = {
  minHeight: "100vh", background: "transparent",
};
const headerStyle: React.CSSProperties = {
  background: "rgba(15, 15, 20, 0.7)", borderBottom: "1px solid rgba(255,255,255,0.05)",
  backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)",
  padding: "16px 24px", display: "flex",
  justifyContent: "space-between", alignItems: "center",
  position: "sticky", top: 0, zIndex: 10,
};
const logoutBtn: React.CSSProperties = {
  padding: "6px 14px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(255,255,255,0.05)", color: "#cbd5e1", fontSize: 12,
  cursor: "pointer", transition: "all 0.2s"
};
const welcomeBanner: React.CSSProperties = {
  padding: "16px 20px", marginBottom: 24,
  display: "flex", alignItems: "center", gap: 14,
};
const continueBtn: React.CSSProperties = {
  padding: "8px 18px", borderRadius: 10,
  fontSize: 13,
};
const streakBadge: React.CSSProperties = {
  display: "inline-block", background: "rgba(255, 128, 8, 0.15)",
  border: "1px solid rgba(255, 128, 8, 0.3)", borderRadius: 20,
  padding: "6px 14px", fontSize: 13, fontWeight: 600,
  color: "#ffc837", marginBottom: 24, boxShadow: "0 0 12px rgba(255,128,8,0.2)"
};
const sectionTitle: React.CSSProperties = {
  fontSize: 18, fontWeight: 700, color: "#f8fafc",
  marginBottom: 16, marginTop: 8, letterSpacing: "0.5px"
};
const bookCard: React.CSSProperties = {
  padding: "24px 12px",
  cursor: "pointer",
  display: "flex", flexDirection: "column", alignItems: "center",
  transition: "transform 0.2s, background 0.2s",
};