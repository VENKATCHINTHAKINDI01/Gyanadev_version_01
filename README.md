<div align="center">
  <h1>🕉️ GyanaDev</h1>
  <p><strong>An Intelligent, Multilingual AI Guru for the Sacred Texts of India</strong></p>

  <p>
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#getting-started">Getting Started</a> •
    <a href="#metrics--evaluation">Metrics</a> •
    <a href="#contributing">Contributing</a>
  </p>
</div>

---

## 📖 Overview

**GyanaDev** is an advanced Retrieval-Augmented Generation (RAG) platform bridging ancient Indian wisdom and modern AI. It provides an intuitive, voice-enabled, and multilingual AI "Guru" that guides users through texts like the *Mahabharata*, *Ramayana*, and *Bhagavad Gita*. 

Leveraging Groq's high-speed inference, Qdrant's vector search, and Sarvam AI's localized voice capabilities, GyanaDev provides hyper-fast, highly accurate, and culturally contextualized answers in multiple Indian languages.

## ✨ Features

- **Advanced RAG Engine:** Semantic and hybrid search over sacred texts using dense embeddings and BM25 ranking.
- **Multilingual Support:** Supports English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, and Bengali natively.
- **Voice Interactions:** Seamless Speech-to-Text (STT) and Text-to-Speech (TTS) integration powered by Sarvam AI.
- **Student Memory System:** MongoDB-backed conversational memory that tracks user progress, enthusiasm, knowledge, and pronunciation.
- **Real-Time Streaming:** Server-Sent Events (SSE) for minimal latency typing effect on the UI.
- **Premium Glassmorphism UI:** A sleek, modern React frontend blending traditional aesthetics with cutting-edge UI trends.

---

## 🏗️ Architecture & Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.12+)
- **LLM Inference:** Groq API (Llama 3 / Mixtral for blazing fast generation)
- **Vector Database:** Qdrant (Low-latency similarity search)
- **Database (Memory/Auth):** MongoDB with Motor (Async capabilities)
- **Authentication:** JWT + passlib (bcrypt)
- **Audio Processing:** Sarvam AI APIs & PyDub

### Frontend
- **Framework:** React 18, TypeScript, Vite
- **Routing:** React Router DOM
- **Design System:** Custom CSS (Glassmorphism, Aurora gradients, Cinzel typography)
- **HTTP Client:** Axios & Native Fetch (for streaming)

---

## 📊 Metrics & Evaluation

GyanaDev strictly adheres to industry-standard RAG evaluation frameworks (such as *Ragas* and *TruLens*) to ensure output quality, minimizing hallucination and preserving textual sanctity.

| Metric | Target Standard | Description |
|--------|-----------------|-------------|
| **Context Precision** | `> 0.85` | Ensures retrieved chunks directly answer the user's prompt. |
| **Context Recall** | `> 0.90` | Ensures all necessary information is retrieved from the Vector DB. |
| **Faithfulness** | `> 0.95` | Validates that the LLM's answer is strictly derived from the retrieved context without hallucination. |
| **Answer Relevance** | `> 0.90` | Assesses how directly the final answer addresses the user's intent. |
| **End-to-End Latency** | `< 800ms` | Time to first token (TTFT) via Groq. |
| **Voice STT/TTS Latency**| `< 1.2s` | Turnaround for regional voice synthesis via Sarvam AI. |

---

## 🚀 Getting Started

### Prerequisites
- **Python:** `3.12+`
- **Node.js:** `18.x+`
- **MongoDB:** Local instance or MongoDB Atlas.
- **Qdrant:** Docker container or Qdrant Cloud.
- **API Keys:** Groq, Sarvam AI.

### 1. Clone the repository
```bash
git clone https://github.com/your-username/gyanadeva.git
cd gyanadeva
```

### 2. Backend Setup
```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env and supply your GROQ_API_KEY, SARVAM_API_KEY, MONGO_URI, and QDRANT_URL
```

### 3. Frontend Setup
```bash
cd frontend

# Install packages
npm install

# Setup frontend variables if any
cp .env.example .env
```

### 4. Running the Application
**Start the backend server:**
```bash
# In the root project directory
uvicorn api.main:app --reload
```
*API will be running on `http://localhost:8000`*

**Start the frontend development server:**
```bash
# In the frontend directory
npm run dev
```
*UI will be accessible at `http://localhost:5173`*

---

## 🧪 Testing

To run the automated backend test suite (pytest):

```bash
pytest --cov=api --cov=memory --cov=rag tests/
```

---

## 🤝 Contributing

We welcome contributions! Please follow the standard GitHub workflow:
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request



---

<p align="center">
  <i>May the light of wisdom guide your code.</i> 🙏
</p>
