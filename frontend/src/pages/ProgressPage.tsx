import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getProgress, getPronunciationHistory, getProfile, Progress, Student } from "../utils/api";
import { SproutIcon, LeafIcon, TreeIcon, StarIcon, FlameIcon, SwordsIcon, BowIcon, ArrowLeftIcon, CheckIcon, LockIcon, SunIcon, BookIcon, SpeechIcon } from "../components/Icons";

const LEVELS = [
  { key: "beginner",     label: "Beginner",     icon: <SproutIcon size={36} color="#4ade80" />, min: 0,  max: 30 },
  { key: "intermediate", label: "Intermediate",  icon: <LeafIcon size={36} color="#fbbf24" />, min: 30, max: 70 },
  { key: "advanced",     label: "Advanced",      icon: <TreeIcon size={36} color="#f87171" />, min: 70, max: 100 },
];

const MILESTONES = [
  { score: 5,   label: "First lesson",      icon: <StarIcon size={28} color="#ffc837" /> },
  { score: 10,  label: "10 questions asked", icon: <FlameIcon size={28} color="#fca5a5" /> },
  { score: 25,  label: "Beginner complete",  icon: <SproutIcon size={28} color="#4ade80" /> },
  { score: 50,  label: "Halfway hero",       icon: <SwordsIcon size={28} color="#94a3b8" /> },
  { score: 75,  label: "Advanced student",   icon: <BowIcon size={28} color="#60a5fa" /> },
  { score: 100, label: "Guru's favourite",   icon: <span style={{fontSize:28, color:"#ffc837"}}>ॐ</span> },
];

export default function ProgressPage() {
  const nav = useNavigate();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [student, setStudent] = useState<Student | null>(null);
  const [pronHistory, setPronHistory] = useState<{ word: string; correct: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getProgress(), getProfile(), getPronunciationHistory()])
      .then(([p, s, ph]) => {
        setProgress(p);
        setStudent(s);
        setPronHistory(ph.common_errors);
      })
      .catch(() => nav("/login"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loader />;
  if (!progress || !student) return null;

  const firstName = student.name.split(" ")[0];
  const knowledge = progress.knowledge_score;
  const currentLevel = LEVELS.find((l) => knowledge >= l.min && knowledge < l.max) || LEVELS[2];

  return (
    <div style={{ minHeight: "100vh", background: "transparent" }}>

      {/* Header */}
      <header style={{ 
        background: "rgba(15, 15, 20, 0.7)", borderBottom: "1px solid rgba(255,255,255,0.05)", 
        backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)",
        padding: "16px 24px", display: "flex", alignItems: "center", gap: 14,
        position: "sticky", top: 0, zIndex: 10 
      }}>
        <button onClick={() => nav("/dashboard")} style={backBtn}><ArrowLeftIcon size={14} color="currentColor" /> <span style={{ marginLeft: 4 }}>Back</span></button>
        <span style={{ fontSize: 28, color: "#ffc837", filter: "drop-shadow(0 0 8px rgba(255,160,0,0.4))" }}>ॐ</span>
        <span className="cinzel" style={{ fontWeight: 700, color: "#ffc837", fontSize: 20, letterSpacing: "1px" }}>
          {firstName}-ji's Journey
        </span>
      </header>

      <div style={{ maxWidth: 720, margin: "0 auto", padding: "32px 16px" }}>

        {/* Current level banner */}
        <div className="glass-panel" style={{
          padding: "32px 24px", marginBottom: 32, textAlign: "center",
          border: "1px solid rgba(255, 200, 55, 0.2)",
          boxShadow: "0 8px 32px rgba(255,128,8,0.15)"
        }}>
          <div style={{ marginBottom: 12, display: "flex", justifyContent: "center", filter: "drop-shadow(0 0 12px rgba(255,255,255,0.2))" }}>{currentLevel.icon}</div>
          <div className="cinzel" style={{ fontWeight: 800, fontSize: 28, color: "#ffc837", letterSpacing: "1px" }}>{currentLevel.label}</div>
          <div style={{ color: "#cbd5e1", fontSize: 15, marginTop: 8 }}>
            Knowledge mastery: <span style={{ color: "#fff", fontWeight: 600 }}>{knowledge.toFixed(0)}/100</span>
          </div>
          {progress.streak_days > 0 && (
            <div style={{ marginTop: 16, display: "inline-block", padding: "6px 16px", background: "rgba(255,128,8,0.2)", border: "1px solid rgba(255,128,8,0.4)", borderRadius: 20, fontSize: 13, fontWeight: 600, color: "#ffc837" }}>
              🔥 {progress.streak_days} day{progress.streak_days > 1 ? "s" : ""} unbroken streak
            </div>
          )}
        </div>

        {/* Progress bars */}
        <div className="glass-panel" style={{ padding: 24, marginBottom: 24 }}>
          <h3 className="cinzel" style={sectionTitle}>Your Attributes</h3>
          <ProgressBar label="Knowledge" value={progress.knowledge_score} color="#ffc837" icon={<BookIcon size={16} color="#cbd5e1" />} />
          <ProgressBar label="Enthusiasm" value={progress.enthusiasm_score} color="#4ade80" icon={<FlameIcon size={16} color="#cbd5e1" />} />
          <ProgressBar label="Pronunciation" value={progress.pronunciation_score} color="#a78bfa" icon={<SpeechIcon size={16} color="#cbd5e1" />} />
          <div style={{ display: "flex", justifyContent: "space-around", marginTop: 20, paddingTop: 20, borderTop: "1px solid rgba(255,255,255,0.1)" }}>
            <StatPill label="Sessions" value={progress.total_interactions} />
            <StatPill label="Streak" value={`${progress.streak_days}d`} />
            <StatPill label="Level" value={currentLevel.label} />
          </div>
        </div>

        {/* Level roadmap */}
        <div className="glass-panel" style={{ padding: 24, marginBottom: 24 }}>
          <h3 className="cinzel" style={sectionTitle}>Path of Wisdom</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {LEVELS.map((l) => {
              const active = l.key === currentLevel.key;
              const done   = knowledge >= l.max;
              return (
                <div key={l.key} style={{
                  display: "flex", alignItems: "center", gap: 16,
                  padding: "16px 20px", borderRadius: 16,
                  border: `1px solid ${active ? "rgba(255,200,55,0.4)" : done ? "rgba(74,222,128,0.2)" : "rgba(255,255,255,0.05)"}`,
                  background: active ? "rgba(255,128,8,0.15)" : done ? "rgba(74,222,128,0.05)" : "rgba(0,0,0,0.2)",
                  transition: "all 0.3s"
                }}>
                  <span style={{ filter: active ? "drop-shadow(0 0 10px rgba(255,200,55,0.5))" : "none" }}>{l.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div className="cinzel" style={{ fontWeight: 700, color: active ? "#ffc837" : done ? "#86efac" : "#94a3b8", fontSize: 16, letterSpacing: "0.5px" }}>{l.label}</div>
                    <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>Mastery {l.min}–{l.max}</div>
                  </div>
                  <span style={{ display: "flex", alignItems: "center", filter: done ? "drop-shadow(0 0 5px rgba(74,222,128,0.5))" : "none" }}>
                    {done ? <CheckIcon size={20} color="#86efac" /> : active ? <SunIcon size={20} color="#ffc837" /> : <LockIcon size={20} color="#64748b" />}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Milestones */}
        <div className="glass-panel" style={{ padding: 24, marginBottom: 24 }}>
          <h3 className="cinzel" style={sectionTitle}>Divine Milestones</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12 }}>
            {MILESTONES.map((m) => {
              const achieved = knowledge >= m.score || progress.total_interactions >= m.score;
              return (
                <div key={m.label} style={{
                  textAlign: "center", padding: "16px 10px", borderRadius: 16,
                  background: achieved ? "rgba(255,128,8,0.1)" : "rgba(0,0,0,0.2)",
                  border: `1px solid ${achieved ? "rgba(255,200,55,0.3)" : "rgba(255,255,255,0.05)"}`,
                  opacity: achieved ? 1 : 0.4,
                  transition: "all 0.3s"
                }}>
                  <div style={{ display: "flex", justifyContent: "center", marginBottom: 8, filter: achieved ? "drop-shadow(0 0 8px rgba(255,200,55,0.4))" : "none" }}>{m.icon}</div>
                  <div style={{ fontSize: 11, color: achieved ? "#ffc837" : "#94a3b8", fontWeight: achieved ? 600 : 400 }}>
                    {m.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Pronunciation history */}
        {pronHistory.length > 0 && (
          <div className="glass-panel" style={{ padding: 24, marginBottom: 32 }}>
            <h3 className="cinzel" style={sectionTitle}>Speech Refinement 🗣️</h3>
            <p style={{ fontSize: 14, color: "#cbd5e1", marginBottom: 16 }}>
              Sanskrit pronunciation corrections by the Guru:
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {pronHistory.slice(0, 6).map((e) => (
                <div key={e.word} style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 18px", background: "rgba(74,222,128,0.05)", border: "1px solid rgba(74,222,128,0.2)", borderRadius: 12 }}>
                  <span style={{ fontSize: 18 }}>✨</span>
                  <div style={{ flex: 1 }}>
                    <span style={{ color: "#fca5a5", textDecoration: "line-through", fontSize: 14 }}>{e.word}</span>
                    <span style={{ color: "#94a3b8", fontSize: 14, margin: "0 8px" }}> ⟶ </span>
                    <span style={{ color: "#86efac", fontWeight: 600, fontSize: 15 }}>{e.correct}</span>
                  </div>
                  <span style={{ fontSize: 12, color: "#64748b", background: "rgba(255,255,255,0.05)", padding: "2px 8px", borderRadius: 10 }}>{e.count}×</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CTA */}
        <button onClick={() => nav("/chat")}
          className="btn-primary"
          style={{ width: "100%", padding: "18px 0", borderRadius: 16, fontSize: 16, letterSpacing: "0.5px" }}>
          Continue Learning with the Guru 🙏
        </button>
      </div>
    </div>
  );
}

function ProgressBar({ label, value, color, icon }: { label: string; value: number; color: string; icon: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 14, color: "#cbd5e1", fontWeight: 500, display: "flex", alignItems: "center", gap: 6 }}>{icon} {label}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color }}>{value.toFixed(0)}/100</span>
      </div>
      <div style={{ height: 8, background: "rgba(0,0,0,0.4)", borderRadius: 4, overflow: "hidden", border: "1px solid rgba(255,255,255,0.05)" }}>
        <div style={{ height: "100%", width: `${Math.min(100, value)}%`, background: color, borderRadius: 4, boxShadow: `0 0 10px ${color}`, transition: "width 1s ease" }} />
      </div>
    </div>
  );
}

function StatPill({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div className="cinzel" style={{ fontWeight: 700, fontSize: 24, color: "#ffc837", textShadow: "0 2px 10px rgba(255,200,55,0.3)" }}>{value}</div>
      <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>{label}</div>
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

const sectionTitle: React.CSSProperties = { fontSize: 20, fontWeight: 700, color: "#f8fafc", marginBottom: 20, marginTop: 0, letterSpacing: "0.5px" };
const backBtn: React.CSSProperties = { padding: "8px 14px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(0,0,0,0.3)", color: "#cbd5e1", fontSize: 13, cursor: "pointer", transition: "all 0.2s" };