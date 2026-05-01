# Aletheia: Distributed Enterprise Code Audit & Optimization Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-65%20passed-brightgreen)](.)

**Aletheia** is an enterprise-grade secure code audit and optimization platform. It adopts a **Distributed Microservice Architecture**, moving beyond LLM "guesses" by integrating formal mathematical solvers (**Z3**) and deterministic security analysis across partitioned services.

> *"Do not trust. Formally Verify."* - Aletheia Principle

## 🏗️ System Architecture

Aletheia is orchestrated as a high-availability microservice stack via **Docker Compose**:

| Component | Responsibility | Technology |
| :--- | :--- | :--- |
| **Frontend** | Pure stateless REST client viewer | Streamlit |
| **API Backend** | Secure REST gatekeeper & JWT Auth | FastAPI / Uvicorn |
| **Task Worker** | Long-running formal Z3 proofs | Celery |
| **Logic Engine** | CFG Taint Analysis & JAX Optimizers | Python 3.14 |
| **Datastore** | Persistent relational audit logs | PostgreSQL 15 |
| **Message Broker** | Asynchronous task distribution | Redis 7 |

## 🚀 Key Features

### 1. Formal Behavioral Equivalence (Z3 Solver)
Aletheia guarantees that optimizations (like JAX conversions) never change your code's original logic.
- **SMT-Solver Verification**: Uses the **Microsoft Z3 Solver** (via CrossHair) to perform symbolic execution proofs.
- **Safety Guarantee**: Every optimization is mathematically proven behaviorally identical for all possible inputs before delivery.
- **Race-Condition-Free**: Each verification runs in an isolated temporary directory, ensuring safe concurrent execution across multiple workers.

### 2. Multi-Stage Deterministic Security
No reliance on LLMs for safety. Aletheia enforces a defense-in-depth security model:
- **Hardened AST Scanner**: Comprehensive ban lists covering 20+ dangerous modules, 15+ unsafe builtins, and 12+ restricted dunder attributes to block sandbox escape vectors.
- **Subprocess Isolation**: Untrusted code executes in isolated child processes with stripped environment variables and strict timeouts — never `exec()`'d in the host process.
- **Bandit Deep Scans**: Programmatic AST analysis for secrets, SQLi, and shell exploits.
- **Real Taint Tracking**: CFG-based source-to-sink variable propagation analysis.
- **Statistical Output Firewall**: Multi-heuristic engine using Shannon entropy, Chi-squared uniformity, KL-divergence, Simpson's diversity, and Serial Correlation to detect encoded payloads and secret leaks with near-zero false positives.

### 3. Distributed Async Processing
The API is non-blocking. Heavy verifications are offloaded to **Celery Workers** with **Redis** persistence, ensuring a snappy user experience and fault-tolerant task execution.
- Endpoints use synchronous definitions so FastAPI runs DB-bound work in a threadpool, keeping the ASGI event loop unblocked.
- Celery workers use fresh event loops per task with proper resource cleanup.

## ⚡ Deployment

### Production Mode (Docker)

Ensure you have **Docker** and **Docker Compose** installed.

```bash
# 1. Clone & Enter
git clone https://github.com/Shafiyullah/Aletheia.git
cd Aletheia

# 2. Configure environment
cp .env.example .env
# Edit .env and set required variables (see below)

# 3. Boot the entire stack
docker compose up --build
```

Access the dashboard at **`localhost:8501`**.

### Local Development

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the API
uvicorn api:app --reload

# 4. Run the frontend (separate terminal)
streamlit run app.py
```

## 🔐 Environment Variables

| Variable | Required | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Yes | Google Gemini API key for AI features |
| `ALETHEIA_SECRET_KEY` | Production | JWT signing key. Auto-generated in dev if unset. |
| `ADMIN_PASSWORD` | Production | Initial admin password. Auto-generated in dev if unset (check console logs). |
| `DATABASE_URL` | Docker | PostgreSQL connection string. Defaults to SQLite locally. |
| `REDIS_URL` | Docker | Redis connection string. Defaults to `redis://localhost:6379/0`. |
| `ALLOWED_ORIGINS` | Optional | Comma-separated CORS origins. Defaults to `http://localhost:8501`. |
| `ENV` | Optional | Set to `PROD` to enforce strict secret requirements. |

> **Note**: In development mode, if `ADMIN_PASSWORD` is not set, a secure random password is generated and printed to the console on first startup. Check the API logs.

## 🛡️ Security Boundaries

Aletheia uses a Zero-Trust architecture:

- **JWT Authentication**: All API endpoints require signed JSON Web Tokens with Bcrypt-hashed credentials. Tokens are timezone-aware and use configurable expiration.
- **No Hardcoded Secrets**: All credentials are sourced from environment variables. The application fails securely in production if required secrets are missing.
- **Restricted CORS**: API access is restricted to configured frontend origins only (no wildcard `*` in any environment).
- **Subprocess Sandbox**: Untrusted code executes in isolated child processes with stripped environments and 10-second timeouts.
- **Input Validation**: All API inputs are bounded by Pydantic field constraints to prevent resource exhaustion.
- **Deterministic Firewall**: Blocks prompt injections and data leaks before they reach the UI based on mathematical entropy bounds.

## 🧪 Testing

Run the full test suite:

```bash
python -m pytest tests/ -v
```

**Current status: 65 tests passing.**

## 🤝 Contributing
For production scaling and feature requests, please see `CONTRIBUTING.md`.

## 📜 License
MIT License. See [LICENSE](LICENSE) for details.
