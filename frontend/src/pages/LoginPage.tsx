import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, register } from "../utils/api";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी" },
  { code: "te", label: "తెలుగు" },
  { code: "ta", label: "தமிழ்" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "ml", label: "മലയാളം" },
  { code: "mr", label: "मराठी" },
  { code: "bn", label: "বাংলা" },
  { code: "gu", label: "ગુજરાતી" },
  { code: "pa", label: "ਪੰਜਾਬੀ" },
];

export default function LoginPage() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    name: "", email: "", password: "",
    age: 12, preferred_language: "en",
  });

  const set = (k: string, v: string | number) =>
    setForm((f) => ({ ...f, [k]: v }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        await login(form.email, form.password);
      } else {
        await register(form);
      }
      nav("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", background: "transparent",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "20px",
    }}>
      <div className="glass-panel" style={{
        padding: "48px 44px", width: "100%", maxWidth: 420,
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 56, color: "#ffc837", marginBottom: 8, filter: "drop-shadow(0 0 10px rgba(255,200,100,0.5))" }}>ॐ</div>
          <h1 className="cinzel" style={{ margin: 0, fontSize: 32, color: "#ffc837", fontWeight: 700, letterSpacing: "1px" }}>
            GyanaDev
          </h1>
          <p style={{ margin: "4px 0 0", color: "#cbd5e1", fontSize: 14 }}>
            Your AI Guru for the Hindu Epics
          </p>
        </div>

        {/* Tab toggle */}
        <div style={{
          display: "flex", background: "rgba(0,0,0,0.4)", borderRadius: 12,
          padding: 4, marginBottom: 24, border: "1px solid rgba(255,255,255,0.1)"
        }}>
          {(["login", "register"] as const).map((m) => (
            <button key={m} onClick={() => { setMode(m); setError(""); }}
              style={{
                flex: 1, padding: "9px 0", border: "none", borderRadius: 10,
                fontWeight: 500, fontSize: 14, cursor: "pointer",
                background: mode === m ? "linear-gradient(135deg, #ff8008, #ffc837)" : "transparent",
                color: mode === m ? "#111" : "#94a3b8",
                transition: "all 0.2s",
                boxShadow: mode === m ? "0 4px 12px rgba(255,128,8,0.3)" : "none",
              }}>
              {m === "login" ? "Login" : "Register"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit}>
          {mode === "register" && (
            <>
              <Input label="Your Name" value={form.name}
                onChange={(v) => set("name", v)} placeholder="e.g. Arjun Kumar" />
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Age</label>
                <input type="number" min={6} max={18} value={form.age}
                  onChange={(e) => set("age", parseInt(e.target.value))}
                  style={inputStyle} />
              </div>
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Preferred Language</label>
                <select value={form.preferred_language}
                  onChange={(e) => set("preferred_language", e.target.value)}
                  style={inputStyle}>
                  {LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code} style={{color: "#000"}}>{l.label}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          <Input label="Email" type="email" value={form.email}
            onChange={(v) => set("email", v)} placeholder="you@example.com" />
          <Input label="Password" type="password" value={form.password}
            onChange={(v) => set("password", v)} placeholder="••••••••" />

          {error && (
            <div style={{
              background: "rgba(220, 38, 38, 0.2)", border: "1px solid rgba(220, 38, 38, 0.4)", borderRadius: 10,
              padding: "10px 14px", marginBottom: 16, fontSize: 13, color: "#fca5a5",
            }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary" style={{
            width: "100%", padding: "13px 0", borderRadius: 12, fontSize: 15,
          }}>
            {loading ? "Please wait…" : mode === "login" ? "Login 🙏" : "Create Account 🙏"}
          </button>
        </form>

        <p style={{ textAlign: "center", marginTop: 24, fontSize: 13, color: "#94a3b8" }}>
          {mode === "login" ? "New here? " : "Already have an account? "}
          <span onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            style={{ color: "#ffc837", cursor: "pointer", fontWeight: 600 }}>
            {mode === "login" ? "Register" : "Login"}
          </span>
        </p>
      </div>
    </div>
  );
}

function Input({ label, value, onChange, type = "text", placeholder = "" }: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string;
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={labelStyle}>{label}</label>
      <input type={type} value={value} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle} />
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block", marginBottom: 6, fontSize: 13,
  fontWeight: 500, color: "#cbd5e1",
};

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "11px 14px", borderRadius: 10, fontSize: 14,
  border: "1px solid rgba(255,255,255,0.2)", outline: "none", 
  background: "rgba(0,0,0,0.3)", color: "#fff",
  fontFamily: "inherit", boxSizing: "border-box", transition: "border 0.2s"
};