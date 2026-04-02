# Development Setup Guide

This guide covers the complete setup for developing MyFinance 4.0.

---

## Prerequisites

### Required Software
- **Python 3.10+**
- **PostgreSQL 14+**
- **Git**

### Optional but Recommended
- **uv** - Fast Python package manager
- **Docker** - For containerized development

---

## Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myfinance
DB_USER=your_user
DB_PASSWORD=your_password

# LLM API (for proxy)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token

# Streamlit Dashboard
STREAMLIT_PORT=8501
```

> **Note:** Never commit `.env` to version control.

---

## Installation

### 1. Clone and Setup Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Create database
createdb myfinance

# Run migrations (if applicable)
python -m alembic upgrade head
```

### 3. Verify Installation

```bash
# Check Python version
python --version

# Check installed packages
pip list
```

---

## Running the Application

### Telegram Gateway
```bash
python main.py
```

### Streamlit Dashboard
```bash
python -m streamlit run web/dashboard/main.py
```

---

## Testing

### Run All Tests
```bash
python -m pytest
```

### Run Specific Test File
```bash
python -m pytest tests/test_accounting_agent.py
```

### Run Specific Test Class
```bash
python -m pytest tests/test_accounting_agent.py::TestAccountingAgent -v
```

### Run Specific Test Method
```bash
python -m pytest tests/test_accounting_agent.py::TestAccountingAgent::test_parse_expense -v
```

### Run with Coverage
```bash
python -m pytest --cov=. --cov-report=term-missing
```

---

## Linting & Code Quality

### Lint with Ruff
```bash
ruff check .
```

### Fix Auto-Fixable Issues
```bash
ruff check --fix .
```

### Format with Black
```bash
black .
```

### Type Checking with MyPy
```bash
python -m mypy .
```

---

## Development Workflow

### Code Style Guidelines
- **Language:** Python 3.10+
- **Style:** PEP 8 + Black (max line length 88)
- **Type Hints:** Required for all function signatures
- **Docstrings:** Google-style for public APIs

### Import Order (PEP 8)
```python
# 1. Standard library
import os
import json
from typing import Optional

# 2. Third-party
import requests
from pydantic import BaseModel

# 3. Local application
from agents import OCRAgent
from core import processor
```

### Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| Functions/variables | snake_case | `get_balance()` |
| Classes | PascalCase | `AccountingAgent` |
| Constants | UPPER_SNAKE | `MAX_RETRIES` |
| Private methods | prefix `_` | `_validate_sql()` |

---

## Troubleshooting

### Common Issues

#### Database Connection Failed
- Check PostgreSQL is running: `pg_isready`
- Verify credentials in `.env`
- Ensure database exists: `psql -l`

#### Import Errors
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`

#### LLM API Errors
- Verify API keys in `.env`
- Check network connectivity
- Review rate limits

#### Test Failures
- Check database is accessible
- Ensure all dependencies installed
- Run with verbose: `pytest -v`

---

## Additional Resources

- [AGENTS.md](../AGENTS.md) - Agent guidelines and architecture
- [README.md](../README.md) - Project overview
- [Coding Standards](./coding-standards.md) - Detailed code style

---

*Last updated: 2026-03-31*
