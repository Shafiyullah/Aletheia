# Aletheia: Distributed Enterprise Code Audit & Optimization Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

**Aletheia** is an enterprise-grade secure code audit and optimization platform. It adopts a **Distributed Microservice Architecture**, moving beyond LLM "guesses" by integrating formal mathematical solvers (**Z3**) and deterministic security analysis across partitioned services.

> *"Do not trust. Formally Verify."* - Aletheia Principle

## 🏗️ System Architecture

Aletheia is orchestrated as a high-availability microservice stack via **Docker Compose**:

| Component | Responsibility | Technology |
| :--- | :--- | :--- |
| **Frontend** | Pure stateless REST client viewer | Streamlit |
| **API Backend** | Secure REST gatekeeper & JWT Auth | FastAPI / Uvicorn |
| **Task Worker** | Long-running formal Z3 proofs | Celery |
| **Logic Engine** | CFG Taint Analysis & JAX Optimizers | Python 3.12 |
| **Datastore** | Persistent relational audit logs | PostgreSQL 15 |
| **Message Broker** | Asynchronous task distribution | Redis 7 |

## 🚀 Key Features

### 1. Formal Behavioral Equivalence (Z3 Solver)
Aletheia guarantees that optimizations (like JAX conversions) never change your code's original logic.
- **SMT-Solver Verification**: Uses the **Microsoft Z3 Solver** (via CrossHair) to perform symbolic execution proofs.
- **Safety Guarantee**: Every optimization is mathematically proven behaviorally identical for all possible inputs before delivery.

### 2. Multi-Stage Deterministic Security
No reliance on LLMs for safety. Aletheia enforces a multi-heuristic security firewall:
- **Bandit Deep Scans**: Programmatic AST analysis for secrets, SQLi, and shell exploits.
- **Real Taint Tracking**: CFG-based source-to-sink variable propagation analysis.
- **Statistical Output Engine**: Chi-squared uniformity and Serial Correlation tests for character anomaly detection.

### 3. Distributed Async Processing
The API is non-blocking. Heavy verifications are offloaded to **Celery Workers** with **Redis** persistence, ensuring a snappy user experience and fault-tolerant task execution.

## ⚡ Deployment (Production Mode)

Ensure you have **Docker** and **Docker Compose** installed.

```bash
# 1. Clone & Enter
git clone https://github.com/Shafiyullah/Aletheia.git
cd Aletheia

# 2. Boot the entire stack
docker compose up --build
```

Access the dashboard at **localhost:8501**.

### Initial Credentials
- **Username**: `enterprise_admin`
- **Password**: `secure_hyper_admin123!`

## 🛡️ Security Boundaries
Aletheia uses a Zero-Trust architecture:
- **JWT Authentication**: All API endpoints require signed JSON Web Tokens with Bcrypt-hashed credentials.
- **Security Sandbox**: Optimized code executes inside restricted Python sandboxes with strictly whitelisted modules (`numpy`, `pandas`, `jax`, `scipy`).
- **Deterministic Firewall**: Blocks prompt injections and data leaks before they reach the UI based on mathematical entropy bounds.

## 🤝 Contributing
For production scaling and feature requests, please see `CONTRIBUTING.md`.

## 📜 License
MIT License. See [LICENSE](LICENSE) for details.
