# Aletheia: The Neuro-Symbolic Truth Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Gemini 3](https://img.shields.io/badge/AI-Gemini%203-orange)](https://deepmind.google/technologies/gemini/)

**Aletheia** is an open-source AI agent designed to verify scientific research and optimize high-performance code. Unlike standard LLM chat interfaces, Aletheia uses a **Neuro-Symbolic** architecture—combining the reasoning of Large Language Models (Gemini 3) with the deterministic execution of formal systems (AST Analysis, JAX, Sandboxed Python).

> *"Do not trust. Verify."* - Aletheia Principle

![Aletheia UI](https://via.placeholder.com/800x400?text=Aletheia+Dashboard+Preview)

## 🚀 Key Features

### 1. The Eyes: Vision-First Document Parsing
Solves the "OCR Problem" for scientific papers.
- **Visual Context**: Uses **Gemini 3 Flash Vision** to "read" papers like a human, preserving LaTeX formulas, complex tables, and layout structure that text-only parsers miss.
- **Vision Forensics**: Scans extracted images and figures for pixel manipulation and deepfake artifacts.

### 2. The Brain: Veritas & Prometheus
- **Veritas (Truth Scope)**: Implements **Chain-of-Verification (CoVe)** with **Deterministic Span-Level Verification (SLV)** to audit research papers. It cross-references claims against citations and flags insufficiently grounded claims.
- **Prometheus (Code Reactor)**: A specialized optimization engine that applies intelligent routing. Math-heavy loops are transpiled into **JAX** for 100x speedups, general logic degrades to a built-in **Algorithmic Complexity Reducer**, while business operations use the **SQL Performance Audit** mode.

### 3. The Nervous System: Hybrid Parallelism
- **AsyncIO + CPU-Bound Jobs**: Concurrently runs `AI Sentinel` security checks and `Model Classification` routing, ensuring heavy computation and I/O-bound API calls remain fast and buttery smooth.

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/Shafiyullah/Aletheia.git
cd Aletheia

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (pinned for stability)
pip install -r requirements.txt

# Install Poppler (Required for PDF processing)
# Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/
# Mac: brew install poppler
# Linux: sudo apt-get install poppler-utils
```

## 🔑 Configuration

Aletheia requires a **Google Gemini API Key or Any LLM API Key**.

1. Get your key from [Google AI Studio](https://aistudio.google.com/).
2. Set it as an environment variable or enter it in the UI.

```bash
# Optional: Set in environment
export GEMINI_API_KEY="your_api_key_here"
```

## ⚡ Usage

```bash
streamlit run app.py
```

Navigate to **localhost:8501**.

### Workflow
1. **Step 1: Audit Paper (Veritas)**: Upload a PDF. Aletheia extracts claims, verifies them via CoVe & Span-Level Verification, and performs Vision Forensics on embedded images to detect manipulation.
2. **Step 2: Reproduce Code (Bridge)**: Upload a paper with computational algorithms. Aletheia securely extracts math claims and generates a sandboxed Python simulation to test and independently verify the results.
3. **Step 3: Hyper-Optimize (Prometheus)**: Point Aletheia to a public GitHub repo, upload code files, or supply SQL queries. It automatically classifies the input—routing it to JAX optimization, an Algorithmic Complexity Reducer, or an SQL Analyzer.

## 🛡️ Security
Aletheia includes an Ironclad **Security Sandbox** and **Deterministic Output Firewall**:
- **AI Sentinel Protocol**: A dedicated async Gemini layer analyzing code for malicious intent (e.g. reverse shells, environment exfiltration).
- **Deterministic Output Firewall**: Zero-API scanning that leverages Shannon entropy and regex to block Prompt Injections, Secret/Key Leaks, and jailbreak attempts before rendering them.
- **AST Static Analysis**: Strict syntax checking that blocks dangerous execution nodes (`exec`, `eval`, `open`, `__import__`) and external imports (e.g. `subprocess`, `os`).
- **Module Whitelisting**: Safe execution guarantees, limiting computations to tightly controlled libraries (`numpy`, `pandas`, `jax`, `math`).

## 🤝 Contributing
We welcome contributions! Please see `CONTRIBUTING.md` for guidelines.

## 📜 License
MIT License. See [LICENSE](LICENSE) for details.
