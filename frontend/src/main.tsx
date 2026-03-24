import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// Premium Google Fonts
const link = document.createElement("link");
link.rel = "stylesheet";
link.href = "https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Inter:wght@300;400;500;600&display=swap";
document.head.appendChild(link);

// Global styles and Glassmorphism utilities
const style = document.createElement("style");
style.textContent = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { 
    font-family: 'Inter', system-ui, sans-serif; 
    -webkit-font-smoothing: antialiased; 
    background-color: #030306;
    background-image: 
      linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
    background-size: 50px 50px;
    background-position: center center;
    color: #e2e8f0;
    min-height: 100vh;
    overflow-x: hidden;
    position: relative;
  }

  /* Wavelike Mesh Gradient / Aurora Background */
  body::before, body::after {
    content: "";
    position: fixed;
    border-radius: 50%;
    filter: blur(140px);
    z-index: -1;
    pointer-events: none;
    animation: floatLayer 20s infinite alternate ease-in-out;
  }
  
  body::before {
    width: 70vw; height: 70vh;
    background: radial-gradient(circle, rgba(139, 92, 246, 0.35) 0%, rgba(0, 0, 0, 0) 70%);
    top: -10%; left: -10%;
    animation-delay: -5s;
  }
  
  body::after {
    width: 80vw; height: 80vh;
    background: radial-gradient(circle, rgba(245, 158, 11, 0.25) 0%, rgba(239, 68, 68, 0.15) 40%, rgba(0, 0, 0, 0) 70%);
    bottom: -20%; right: -10%;
    animation-duration: 25s;
  }

  @keyframes floatLayer {
    0% { transform: translate(0, 0) scale(1); }
    33% { transform: translate(8%, 15%) scale(1.1); }
    66% { transform: translate(-5%, 10%) scale(0.9); }
    100% { transform: translate(0, 0) scale(1); }
  }
  h1, h2, h3, h4, h5, .cinzel { font-family: 'Cinzel', serif; }
  button { font-family: inherit; }
  textarea, input, select { font-family: inherit; }

  /* Premium Glassmorphism Panel */
  .glass-panel {
    background: rgba(20, 20, 25, 0.65);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
    border-radius: 24px;
  }

  /* Ambient Glow Animations */
  @keyframes glowFloat {
    0% { box-shadow: 0 0 20px rgba(255, 128, 8, 0.2); transform: translateY(0px); }
    50% { box-shadow: 0 0 40px rgba(255, 128, 8, 0.4); transform: translateY(-4px); }
    100% { box-shadow: 0 0 20px rgba(255, 128, 8, 0.2); transform: translateY(0px); }
  }

  .btn-primary {
    background: linear-gradient(135deg, #ff8008 0%, #ffc837 100%);
    color: #111;
    font-weight: 600;
    border: none;
    transition: all 0.3s ease;
  }
  .btn-primary:hover:not(:disabled) {
    animation: glowFloat 2s infinite ease-in-out;
    transform: scale(1.02);
  }
  .btn-primary:disabled { opacity: 0.7; cursor: not-allowed; }

  /* Smooth scrollbar */
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.4); }
`;
document.head.appendChild(style);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);