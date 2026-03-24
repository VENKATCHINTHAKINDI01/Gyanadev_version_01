import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { streamAsk, transcribeAudio, speakText, getWelcome, BookFilter } from "../utils/api";

interface Message {
  id: string;
  role: "user" | "guru";
  text: string;
  sources?: string[];
  pronunciationNote?: string | null;
  isStreaming?: boolean;
  language?: string;
}

const LANGUAGES = [
  { code: "auto", flag: "🌐", label: "Auto" },
  { code: "en",   flag: "🇬🇧", label: "English" },
  { code: "hi",   flag: "🇮🇳", label: "हिंदी" },
  { code: "te",   flag: "🇮🇳", label: "తెలుగు" },
  { code: "ta",   flag: "🇮🇳", label: "தமிழ்" },
  { code: "kn",   flag: "🇮🇳", label: "ಕನ್ನಡ" },
  { code: "ml",   flag: "🇮🇳", label: "മലയാളം" },
  { code: "mr",   flag: "🇮🇳", label: "मराठी" },
  { code: "bn",   flag: "🇮🇳", label: "বাংলা" },
];

const BOOK_LABELS: Record<string, string> = {
  mahabharata:   "⚔️ Mahabharata",
  ramayana:      "🏹 Ramayana",
  bhagavad_gita: "🪷 Bhagavad Gita",
};

const SUGGESTIONS = [
  "Who is Arjuna?",
  "What did Hanuman do in Lanka?",
  "Tell me about dharma",
  "Why did the Pandavas go to exile?",
  "Who is Krishna?",
  "What is the Bhagavad Gita?",
];

// ── Voice recorder with WAV conversion ────────────────────────────
function useVoiceRecorder(onResult: (text: string) => void, language: string) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recRef  = useRef<MediaRecorder | null>(null);
  const chunks  = useRef<Blob[]>([]);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Prefer audio/webm;codecs=opus, fallback to whatever is supported
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/ogg";
      const rec = new MediaRecorder(stream, { mimeType });
      chunks.current = [];
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunks.current.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: mimeType });
        setTranscribing(true);
        try {
          const res = await transcribeAudio(blob, language === "auto" ? "auto" : language);
          if (res.text?.trim()) onResult(res.text);
          else alert("Could not hear clearly. Please try again.");
        } catch (e) {
          console.error("STT error:", e);
          alert("Voice transcription failed. Check your Sarvam API key.");
        } finally {
          setTranscribing(false);
        }
      };
      rec.start(100); // collect data every 100ms
      recRef.current = rec;
      setRecording(true);
    } catch {
      alert("Microphone access is needed for voice input. Please allow it in your browser.");
    }
  }, [language, onResult]);

  const stop = useCallback(() => {
    if (recRef.current?.state === "recording") {
      recRef.current.stop();
    }
    setRecording(false);
  }, []);

  return { recording, transcribing, start, stop };
}

// ── TTS Player ─────────────────────────────────────────────────────
async function playAudio(text: string, language: string): Promise<void> {
  try {
    // Strip markdown and emoji from TTS text
    const clean = text
      .replace(/📖.*$/gm, "")           // remove citation line
      .replace(/[*_`#]/g, "")           // remove markdown
      .replace(/\[.*?\]/g, "")          // remove labels like [BG 2.47]
      .replace(/[\u{1F300}-\u{1FFFF}]/gu, "") // remove emoji
      .trim();
    if (!clean) return;

    const blob = await speakText(clean.slice(0, 800), language);
    const url  = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    audio.onerror = () => URL.revokeObjectURL(url);
    await audio.play();
  } catch (e) {
    console.warn("TTS failed:", e);
  }
}

// ── Main Component ─────────────────────────────────────────────────
export default function ChatPage() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const bookParam = params.get("book") as BookFilter;

  const [messages, setMessages]     = useState<Message[]>([]);
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [lang, setLang]             = useState("auto");
  const [book, setBook]             = useState<BookFilter>(bookParam);
  const [voiceMode, setVoiceMode]   = useState(false); // auto-play TTS
  const [showLang, setShowLang]     = useState(false);
  const [welcomeMsg, setWelcomeMsg] = useState("");
  const [speakingId, setSpeakingId] = useState<string | null>(null);

  const bottomRef    = useRef<HTMLDivElement>(null);
  const stopStreamRef = useRef<(() => void) | null>(null);
  const inputRef     = useRef<HTMLTextAreaElement>(null);
  const detectedLang = useRef("en"); // tracks what language was detected

  const { recording, transcribing, start: startRec, stop: stopRec } =
    useVoiceRecorder((text) => {
      setInput(text);
      // Auto-send after voice input
      setTimeout(() => sendMessage(text), 300);
    }, lang);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    getWelcome().then((w) => { if (w.message) setWelcomeMsg(w.message); }).catch(() => {});
  }, []);

  const sendMessage = useCallback(async (text?: string) => {
    const q = (text || input).trim();
    if (!q || loading) return;

    const uid = Date.now().toString();
    const gid = (Date.now() + 1).toString();

    setMessages((prev) => [
      ...prev,
      { id: uid, role: "user", text: q },
      { id: gid, role: "guru", text: "", isStreaming: true },
    ]);
    setInput("");
    setLoading(true);

    let full = "";
    let responseLang = lang === "auto" ? "en" : lang;

    stopStreamRef.current = streamAsk(
      q, lang, book,
      (chunk) => {
        full += chunk;
        setMessages((prev) =>
          prev.map((m) => m.id === gid ? { ...m, text: full } : m)
        );
      },
      async () => {
        setMessages((prev) =>
          prev.map((m) => m.id === gid ? { ...m, isStreaming: false, language: responseLang } : m)
        );
        setLoading(false);
        // Auto-play in voice mode
        if (voiceMode && full) {
          setSpeakingId(gid);
          await playAudio(full, responseLang);
          setSpeakingId(null);
        }
      },
      (e) => { console.error(e); setLoading(false); }
    );
  }, [input, loading, lang, book, voiceMode]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleSpeak = async (msg: Message) => {
    if (speakingId === msg.id) { setSpeakingId(null); return; }
    setSpeakingId(msg.id);
    await playAudio(msg.text, msg.language || "en");
    setSpeakingId(null);
  };

  const currentLang = LANGUAGES.find((l) => l.code === lang) || LANGUAGES[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "transparent" }}>

      {/* Header */}
      <header style={{
        background: "rgba(15, 15, 20, 0.7)", borderBottom: "1px solid rgba(255,255,255,0.05)",
        backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)",
        padding: "12px 16px", display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
        position: "sticky", top: 0, zIndex: 10
      }}>
        <button onClick={() => nav("/dashboard")} style={iconBtn}>←</button>
        <span style={{ fontSize: 24, color: "#ffc837", filter: "drop-shadow(0 0 8px rgba(255,160,0,0.4))" }}>ॐ</span>
        <span className="cinzel" style={{ fontWeight: 700, color: "#ffc837", fontSize: 18, flex: 1, letterSpacing: "1px" }}>Guruji</span>

        {/* Book filter */}
        <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 2 }}>
          {([null, "mahabharata", "ramayana", "bhagavad_gita"] as const).map((b) => {
            const isActive = book === b;
            return (
              <button key={String(b)} onClick={() => setBook(b as BookFilter)} style={{
                padding: "6px 12px", borderRadius: 20,
                border: `1px solid ${isActive ? "rgba(255,200,55,0.4)" : "rgba(255,255,255,0.1)"}`,
                fontSize: 12, fontWeight: 500, cursor: "pointer", whiteSpace: "nowrap",
                background: isActive ? "rgba(255,128,8,0.15)" : "rgba(0,0,0,0.3)",
                color: isActive ? "#ffc837" : "#cbd5e1",
                transition: "all 0.2s"
              }}>
                {b ? BOOK_LABELS[b] : "📚 All"}
              </button>
            )
          })}
        </div>

        {/* Language */}
        <div style={{ position: "relative" }}>
          <button onClick={() => setShowLang(!showLang)} style={{ ...iconBtn, fontSize: 18, padding: "4px 8px" }}>
            {currentLang.flag}
          </button>
          {showLang && (
            <div className="glass-panel" style={{ position: "absolute", right: 0, top: 40, zIndex: 50, minWidth: 140, overflow: "hidden", padding: "4px 0" }}>
              {LANGUAGES.map((l) => (
                <button key={l.code} onClick={() => { setLang(l.code); setShowLang(false); }}
                  style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "10px 14px", border: "none", background: lang === l.code ? "rgba(255,128,8,0.15)" : "transparent", cursor: "pointer", fontSize: 13, color: lang === l.code ? "#ffc837" : "#cbd5e1", transition: "all 0.2s" }}>
                  <span>{l.flag}</span><span style={{ fontWeight: lang === l.code ? 600 : 400 }}>{l.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Voice mode toggle */}
        <button onClick={() => setVoiceMode(!voiceMode)} style={{ ...iconBtn, background: voiceMode ? "rgba(255,128,8,0.15)" : "transparent", color: voiceMode ? "#ffc837" : "#94a3b8", borderColor: voiceMode ? "rgba(255,200,55,0.3)" : "rgba(255,255,255,0.1)" }} title={voiceMode ? "Voice mode ON" : "Voice mode OFF"}>
          {voiceMode ? "🔊" : "🔇"}
        </button>
      </header>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column" }}>

        {welcomeMsg && messages.length === 0 && (
          <div className="glass-panel" style={{ padding: "16px 20px", marginBottom: 20, fontSize: 14, color: "#f8fafc", display: "flex", alignItems: "center", gap: 12, border: "1px solid rgba(255,200,55,0.2)", boxShadow: "0 8px 24px rgba(255,128,8,0.1)" }}>
            <span style={{ fontSize: 24, filter: "drop-shadow(0 0 8px rgba(255,200,55,0.6))" }}>🌸</span> 
            <span style={{ flex: 1 }}>{welcomeMsg}</span>
          </div>
        )}

        {messages.length === 0 && (
          <div style={{ marginBottom: 16, marginTop: "auto", paddingBottom: "20vh" }}>
            <p style={{ fontSize: 14, color: "#94a3b8", marginBottom: 16, textAlign: "center", fontWeight: 500, letterSpacing: "0.5px" }}>Ask Guruji anything about the sacred texts…</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "center", maxWidth: 600, margin: "0 auto" }}>
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => sendMessage(s)}
                  className="glass-panel"
                  style={{ padding: "10px 16px", borderRadius: 20, fontSize: 13, color: "#e2e8f0", cursor: "pointer", transition: "all 0.2s", backdropFilter: "blur(8px)" }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,128,8,0.15)"; e.currentTarget.style.color = "#ffc837"; e.currentTarget.style.borderColor = "rgba(255,200,55,0.3)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(20, 20, 25, 0.65)"; e.currentTarget.style.color = "#e2e8f0"; e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.1)"; }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} style={{ display: "flex", gap: 12, marginBottom: 20, flexDirection: msg.role === "user" ? "row-reverse" : "row" }}>

            <div style={{ width: 38, height: 38, borderRadius: 14, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, background: msg.role === "user" ? "linear-gradient(135deg, #ff8008 0%, #ffc837 100%)" : "rgba(15, 15, 20, 0.8)", border: msg.role === "guru" ? "1px solid rgba(255,200,55,0.4)" : "none", boxShadow: msg.role === "guru" ? "0 0 15px rgba(255,128,8,0.2)" : "0 4px 12px rgba(255,128,8,0.3)" }}>
              {msg.role === "user" ? "👤" : <span style={{ filter: "drop-shadow(0 0 5px rgba(255,200,55,0.5))" }}>🕉️</span>}
            </div>

            <div style={{ maxWidth: "80%", display: "flex", flexDirection: "column", alignItems: msg.role === "user" ? "flex-end" : "flex-start", gap: 8 }}>
              <div className={msg.role === "guru" ? "glass-panel" : ""} style={{
                padding: "14px 18px",
                borderRadius: msg.role === "user" ? "20px 6px 20px 20px" : "6px 20px 20px 20px",
                background: msg.role === "user" ? "linear-gradient(135deg, #ff8008 0%, #ffc837 100%)" : undefined,
                color: msg.role === "user" ? "#111" : "#f8fafc",
                fontSize: 15, lineHeight: 1.6,
                fontWeight: msg.role === "user" ? 500 : 400,
                boxShadow: msg.role === "user" ? "0 4px 15px rgba(255,128,8,0.2)" : "none",
                border: msg.role === "user" ? "none" : undefined
              }}>
                {msg.isStreaming && !msg.text ? (
                  <div style={{ display: "flex", gap: 5, padding: "6px 4px" }}>
                    {[0, 1, 2].map((i) => (
                      <div key={i} style={{ width: 8, height: 8, borderRadius: "50%", background: "#ffc837", filter: "drop-shadow(0 0 4px rgba(255,200,55,0.5))", animation: `bounce 1.2s ${i * 0.15}s infinite` }} />
                    ))}
                  </div>
                ) : (
                  <div style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>
                )}
              </div>

              {/* Speak button on Guru messages */}
              {msg.role === "guru" && !msg.isStreaming && msg.text && (
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginLeft: 8 }}>
                  <button onClick={() => handleSpeak(msg)} style={{ ...iconBtn, fontSize: 13, padding: "4px 12px", border: "1px solid rgba(255,255,255,0.1)", color: "#cbd5e1" }}
                    title="Listen to Guruji speak"
                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.color = "#fff"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#cbd5e1"; }}>
                    {speakingId === msg.id ? "⏹ Stop" : "🔉 Listen"}
                  </button>
                </div>
              )}

              {msg.pronunciationNote && (
                <div className="glass-panel" style={{ fontSize: 13, padding: "10px 14px", background: "rgba(74,222,128,0.1)", border: "1px solid rgba(74,222,128,0.3)", borderRadius: 12, color: "#86efac", maxWidth: 320, boxShadow: "0 4px 15px rgba(74,222,128,0.1)" }}>
                  ✨ {msg.pronunciationNote}
                </div>
              )}
            </div>
          </div>
        ))}

        {transcribing && (
          <div style={{ textAlign: "center", color: "#94a3b8", fontSize: 13, padding: "12px", background: "rgba(0,0,0,0.3)", borderRadius: 20, alignSelf: "center", backdropFilter: "blur(4px)", border: "1px solid rgba(255,255,255,0.05)" }}>
            <span style={{ animation: "pulse 1.5s infinite" }}>🎙 Transcribing your voice...</span>
          </div>
        )}

        <div ref={bottomRef} style={{ height: 20 }} />
      </div>

      {/* Input bar */}
      <div style={{ background: "rgba(15, 15, 20, 0.7)", borderTop: "1px solid rgba(255,255,255,0.05)", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", padding: "16px", flexShrink: 0 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", maxWidth: 760, margin: "0 auto" }}>

          {/* Voice button — hold to record */}
          <button
            onMouseDown={startRec}
            onMouseUp={stopRec}
            onTouchStart={(e) => { e.preventDefault(); startRec(); }}
            onTouchEnd={(e) => { e.preventDefault(); stopRec(); }}
            disabled={transcribing}
            style={{
              width: 48, height: 48, borderRadius: 16, border: "1px solid rgba(255,255,255,0.1)",
              background: recording ? "rgba(239, 68, 68, 0.2)" : transcribing ? "rgba(255, 200, 55, 0.2)" : "rgba(255,255,255,0.05)",
              color: recording ? "#f87171" : transcribing ? "#ffc837" : "#cbd5e1",
              fontSize: 22, cursor: "pointer", flexShrink: 0,
              boxShadow: recording ? "0 0 15px rgba(239,68,68,0.4)" : "none",
              transition: "all 0.2s",
              borderColor: recording ? "rgba(239,68,68,0.5)" : transcribing ? "rgba(255,200,55,0.5)" : "rgba(255,255,255,0.1)",
            }}
            title="Hold to speak">
            {transcribing ? "⏳" : recording ? "⏹" : "🎙"}
          </button>

          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask Guruji… or hold 🎙 to speak"
            rows={1}
            disabled={loading}
            style={{ flex: 1, resize: "none", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 16, padding: "13px 18px", fontSize: 15, color: "#f8fafc", fontFamily: "inherit", outline: "none", background: "rgba(0,0,0,0.4)", maxHeight: 120, overflowY: "auto", boxShadow: "inset 0 2px 4px rgba(0,0,0,0.2)", transition: "border-color 0.2s" }}
            onFocus={(e) => e.target.style.borderColor = "rgba(255,200,55,0.4)"}
            onBlur={(e) => e.target.style.borderColor = "rgba(255,255,255,0.1)"}
            onInput={(e) => {
              const el = e.target as HTMLTextAreaElement;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 120) + "px";
            }}
          />

          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading}
            className={input.trim() && !loading ? "btn-primary" : ""}
            style={{ 
              width: 48, height: 48, borderRadius: 16, border: input.trim() && !loading ? "none" : "1px solid rgba(255,255,255,0.05)", 
              background: input.trim() && !loading ? undefined : "rgba(255,255,255,0.05)", 
              color: input.trim() && !loading ? "#111" : "#64748b", 
              fontSize: 20, cursor: input.trim() ? "pointer" : "not-allowed", flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center"
            }}>
            {loading ? "⏳" : "➤"}
          </button>
        </div>

        <div style={{ minHeight: 18, marginTop: 8 }}>
          {recording && (
            <p style={{ textAlign: "center", fontSize: 12, color: "#f87171", fontWeight: 500, animation: "pulse 1.5s infinite" }}>
              🔴 Recording… release to send to Guruji
            </p>
          )}
          {voiceMode && !recording && !loading && (
            <p style={{ textAlign: "center", fontSize: 12, color: "#64748b" }}>
              🔊 Voice mode on — Guruji will speak answers automatically
            </p>
          )}
        </div>
      </div>

      <style>{`
        @keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
        @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }
      `}</style>
    </div>
  );
}

const iconBtn: React.CSSProperties = {
  padding: "8px", borderRadius: 12, border: "1px solid rgba(255,255,255,0.1)",
  background: "rgba(255,255,255,0.05)", cursor: "pointer", fontSize: 16, color: "#cbd5e1",
  display: "flex", alignItems: "center", justifyContent: "center",
  transition: "all 0.2s"
};