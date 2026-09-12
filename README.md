# Vocalis — Local Multilingual Speech-to-English Translator

Vocalis is a 100% offline, real-time speech translation system that translates spoken speech from **Kannada, Hindi, Tamil, Telugu, Marathi, Spanish, French, German, and 90+ languages** directly into **fluent English text**.

It is powered by **Meta's SeamlessM4T Medium** neural model running locally on your hardware, paired with hardware-accelerated WebRTC Voice Activity Detection and a modern React dashboard.

---

## ✨ Key Features
- **Direct Speech-to-English (S2TT)**: Direct neural translation from spoken audio to English text without intermediate error cascades.
- **100% Offline & Private**: All acoustic recognition and translation inference runs locally on your GPU/CPU. Zero external APIs, zero latency from internet round-trips, and absolute privacy.
- **Deep Indic Language Support**: High accuracy across **Kannada (`kan`), Hindi (`hin`), Tamil (`tam`), Telugu (`tel`), Marathi (`mar`), Malayalam (`mal`), Bengali (`ben`), Gujarati (`guj`), Punjabi (`pan`), and Urdu (`urd`)**.
- **Dual-Layer Voice Activity Detection**: WebRTC VAD (Mode 2) + RMS dynamic volume filtering for accurate pause detection and background noise cancellation.
- **Modern Minimalist UI**: Centered interactive microphone control, live audio visualizer waves, real-time status updates, and single-click copy tools.

---

## 💻 Hardware Requirements
- **GPU**: NVIDIA GPU with at least 4 GB VRAM (e.g., RTX 3050, RTX 2060, GTX 1660, or higher) for CUDA acceleration, or modern multi-core CPU.
- **RAM**: 8 GB RAM minimum (16 GB recommended).
- **OS**: Windows 10/11, macOS, or Linux.
- **Node.js**: v18.0.0 or higher.
- **Python**: 3.10, 3.11, 3.12, or 3.13.

---

## 📥 Model Download & Directory Setup

Vocalis uses **Meta SeamlessM4T Medium** (`facebook/hf-seamless-m4t-medium`).

### 1. Create the Model Folder
Ensure the following directory exists inside your project root:
```
models/seamless-m4t-medium/
```

### 2. Download Model Files
Download all files from the official [Hugging Face Repository](https://huggingface.co/facebook/hf-seamless-m4t-medium/tree/main) and place them directly into `models/seamless-m4t-medium/`:

| File Name | Size | Direct Download Link |
| :--- | :--- | :--- |
| **`pytorch_model.bin`** | ~4.6 GB | [Download pytorch_model.bin](https://huggingface.co/facebook/hf-seamless-m4t-medium/resolve/main/pytorch_model.bin?download=true) |
| **`sentencepiece.bpe.model`** | ~4.7 MB | [Download sentencepiece.bpe.model](https://huggingface.co/facebook/hf-seamless-m4t-medium/resolve/main/sentencepiece.bpe.model?download=true) |
| **`config.json`** | ~2.5 KB | [Download config.json](https://huggingface.co/facebook/hf-seamless-m4t-medium/resolve/main/config.json?download=true) |
| **`generation_config.json`** | ~242 B | [Download generation_config.json](https://huggingface.co/facebook/hf-seamless-m4t-medium/resolve/main/generation_config.json?download=true) |
| **`preprocessor_config.json`** | ~340 B | [Download preprocessor_config.json](https://huggingface.co/facebook/hf-seamless-m4t-medium/resolve/main/preprocessor_config.json?download=true) |
| **`tokenizer_config.json`** | ~7.3 KB | [Download tokenizer_config.json](https://huggingface.co/facebook/hf-seamless-m4t-medium/resolve/main/tokenizer_config.json?download=true) |
| **`added_tokens.json`** | ~2.7 KB | [Download added_tokens.json](https://huggingface.co/facebook/hf-seamless-m4t-medium/resolve/main/added_tokens.json?download=true) |
| **`special_tokens_map.json`** | ~1.5 KB | [Download special_tokens_map.json](https://huggingface.co/facebook/hf-seamless-m4t-medium/resolve/main/special_tokens_map.json?download=true) |

---

## 🚀 Complete Installation & Setup Guide

### Step 1: Clone the Repository
```powershell
git clone https://github.com/your-username/vocalis.git
cd vocalis
```

### Step 2: Set Up Python Backend Dependencies
Create and activate a virtual environment (recommended):
```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows PowerShell:
.\venv\Scripts\Activate.ps1

# (Or on Linux/macOS:)
# source venv/bin/activate
```

Install the Python dependencies:
```powershell
pip install -r requirements.txt
```

### Step 3: Set Up Frontend Dependencies
Navigate to the `frontend` folder and install the npm packages:
```powershell
cd frontend
npm install
cd ..
```

---

## 🏃 Running the Application

### 1. Start the Backend API & Translation Server
In your first terminal (with your virtual environment active):
```powershell
python main.py
```
*The FastAPI backend will load SeamlessM4T into memory/GPU and start listening on `http://127.0.0.1:8000` (`ws://127.0.0.1:8000/ws`).*

### 2. Start the Frontend Web App
In a second terminal:
```powershell
cd frontend
npm start
```
*The Vite development server will open `http://localhost:5173` in your browser.*

### 3. Start Translating!
1. Open **`http://localhost:5173`** in your browser.
2. The bottom center button will display **`Mic is ON`**.
3. Speak naturally in **Kannada, Hindi, Tamil, Telugu, Marathi, Spanish, or English**.
4. When you pause speaking, the translation will automatically appear in English on the dashboard.

---

## 📂 Project Structure
```
├── main.py                      # FastAPI server, SoundDevice capture, WebRTC VAD & SeamlessM4T pipeline
├── requirements.txt             # Python backend dependencies (PyTorch, Transformers, FastAPI, etc.)
├── deployment.md                # System architecture, data flow & deployment guide
├── .gitignore                   # Git ignore rules for node_modules and large weights
│
├── models/
│   └── seamless-m4t-medium/     # Local Meta SeamlessM4T model weights & tokenizer
│       ├── pytorch_model.bin
│       ├── sentencepiece.bpe.model
│       └── *.json
│
└── frontend/                    # React + Vite web dashboard
    ├── package.json             # Frontend dependencies & scripts
    ├── index.html               # HTML entry point
    └── src/
        ├── App.jsx              # Main dashboard component with WebSocket listener
        ├── App.css              # Custom dark-theme styling & responsive design
        └── main.jsx             # React DOM root mounting
```

---

## 📜 License
This project is open-source under the MIT License. Model weights are governed by Meta's SeamlessM4T Community License Agreement.
