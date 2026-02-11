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
- **Smart Scanning**: Automatically optimizes token usage by selectively scanning Abstract, Conclusion, and key results for large documents.

### 2. The Brain: Veritas & Prometheus
- **Veritas (Truth Scope)**: Implements **Chain-of-Verification (CoVe)** to audit research papers. It cross-references claims against citations and detects hallucinations.
- **Prometheus (Code Reactor)**: A JAX-powered optimization engine. It detects math-heavy Python code (e.g., nested loops) and transpiles it into **JAX** for up to **100x speedups** on CPU/TPU.

### 3. The Nervous System: Hybrid Parallelism
- **AsyncIO + Multiprocessing**: Handles I/O-bound API calls and CPU-bound image processing concurrently, ensuring a buttery smooth UI even during heavy workloads.

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
1. **Audit Paper**: Upload a PDF. Aletheia will extract claims and verify them against the text using CoVe.
2. **Deep Reproduction**: Upload a paper with algorithms. Aletheia will extract the math and generate a sandboxed Python simulation to verify the results.
3. **Hyper-Optimize**: Point Aletheia to a GitHub repo or upload files. It will scan for performance bottlenecks and rewrite them in JAX.

## 🛡️ Security
Aletheia includes a hardened **Security Sandbox**:
- **AST Analysis**: Blocks dangerous imports (`os`, `subprocess`, `socket`) in generated code.
- **Module Whitelisting**: Only safe libraries (`numpy`, `pandas`, `jax`, `scikit-learn`) are allowed.
- **Taint Analysis**: Tracks data flow to prevent injection attacks.

## 🤝 Contributing
We welcome contributions! Please see `CONTRIBUTING.md` for guidelines.

## 📜 License
MIT License. See [LICENSE](LICENSE) for details.
