# MyFinance 4.0 Documentation

Comprehensive documentation for the MyFinance AI-powered personal finance OS.

---

## 📁 Documentation Structure

```
docs/
├── architecture/       # System architecture docs
│   ├── agent-architecture.md  # ⚠️ REDIRECT to AGENTS.md
│   └── system-design.md
├── flows/             # User and system flows
│   ├── agent-flows.md
│   ├── user-flows.md
│   ├── routes.md
│   └── decision-trees.md
├── data-models/       # Database and data models
│   ├── schemas.md
│   └── erd.md
├── guides/            # User guides
│   ├── setup.md       # Development setup
│   ├── troubleshooting.md
│   └── faq.md
├── development/       # Development docs
│   ├── coding-standards.md
│   ├── testing.md
│   └── deployment.md
├── README.md         # This file
└── REGLAS.md        # Golden Rules (Spanish)
```

> **Note:** The main agent documentation is in `AGENTS.md` (project root).

---

## 🚀 Getting Started

### 1. Clone and Setup

```bash
# Clone repository
git clone <repo-url>
cd MyFinance4.0

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env ONLY with infrastructure credentials (DB, Telegram, Ollama)
```

### 2. Configure (Rule #2)

- **Infrastructure**: Edit `.env` for database and provider tokens.
- **Application**: All agent settings (Models, Tasks, Thresholds) are in the `sistema_config` database table (managed via Dashboard).

### 3. Run

```bash
# Telegram bot gateway
python main.py

# Streamlit admin dashboard
python -m streamlit run web/dashboard/main.py
```

---

## 🔧 Development Commands

### Testing
```bash
python -m pytest
python -m pytest --cov=. --cov-report=term-missing
```

### Linting & Formatting
```bash
ruff check .
ruff check --fix .
black .
```

### Type Checking
```bash
python -m mypy .
```

---

## 📖 Key Documentation

| Topic | File | Description |
|-------|------|-------------|
| **Core Roadmap** | `../../AGENTS.md` | **Source of Truth** for 6-agent architecture |
| System Design | `architecture/system-design.md` | High-level topology and routes |
| Processing Routes | `flows/routes.md` | Detailed A-F processing routes |
| Golden Rules | `REGLAS.md` | Project development standards (Spanish) |
| Setup Guide | `development/setup.md` | Detailed environment installation |

---

*Last updated: 2026-04-02*
