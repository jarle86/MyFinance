# Troubleshooting Guide

Solutions to common issues in MyFinance 4.0.

---

## Database Issues

### "Connection refused" Error

**Symptom:** `psycopg2.OperationalError: connection refused`

**Causes:**
- PostgreSQL not running
- Wrong host/port
- Firewall blocking connection

**Solutions:**
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# Start PostgreSQL (Linux)
sudo systemctl start postgresql

# Check PostgreSQL status
sudo systemctl status postgresql
```

### "Database does not exist" Error

**Symptom:** `psycopg2.OperationalError: database "myfinance" does not exist`

**Solutions:**
```bash
# Create database
createdb myfinance

# Or using psql
psql -U postgres -c "CREATE DATABASE myfinance;"
```

### "Authentication failed" Error

**Symptom:** `psycopg2.OperationalError: FATAL: password authentication failed`

**Solutions:**
1. Check credentials in `.env` file
2. Verify user exists: `psql -U postgres -c "\du"`
3. Update `pg_hba.conf` if needed

---

## LLM/API Issues

### "API key not found" Error

**Symptom:** `KeyError: OPENAI_API_KEY` or similar

**Solutions:**
1. Check `.env` file exists in project root
2. Verify API keys are set correctly
3. Restart application after updating `.env`

### "Rate limit exceeded" Error

**Symptom:** `RateLimitError: Too many requests`

**Solutions:**
1. Wait before retrying
2. Check API quotas
3. Implement retry with backoff

### "Model not found" Error

**Symptom:** `ProviderModelNotFoundError`

**Solutions:**
1. Verify model name in configuration
2. Check model availability in your provider
3. Update to a valid model ID

---

## Application Issues

### Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'xxx'`

**Solutions:**
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep <package-name>
```

### Port Already in Use

**Symptom:** `OSError: [Errno 48] Address already in use`

**Solutions:**
```bash
# Find process using port
lsof -i :8501  # for Streamlit
lsof -i :8000  # for proxy

# Kill process
kill <PID>

# Or use different port
STREAMLIT_PORT=8502 python -m streamlit run web/dashboard/main.py
```

---

## Testing Issues

### Tests Won't Run

**Symptom:** `ERROR: no tests collected`

**Solutions:**
```bash
# Check test file naming
ls tests/

# Run with verbose to see what's happening
python -m pytest -v

# Verify pytest is installed
pip list | grep pytest
```

### Database Tests Failing

**Symptom:** Tests pass locally but fail in CI

**Solutions:**
1. Use test database
2. Mock database connections
3. Check test environment variables

---

## Telegram Bot Issues

### "Bot token invalid" Error

**Symptom:** Telegram API returns error

**Solutions:**
1. Get fresh token from @BotFather
2. Check token in `.env`
3. Verify no extra spaces/newlines

### "Message not delivered" Issue

**Symptom:** Bot sends but user doesn't receive

**Solutions:**
1. Check bot has been started by user
2. Verify chat ID is correct
3. Check bot permissions

---

## Code Quality Issues

### Ruff Lint Errors

**Solutions:**
```bash
# Check specific errors
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Black Formatting Errors

**Solutions:**
```bash
# Check formatting
black --check .

# Format code
black .
```

### MyPy Type Errors

**Solutions:**
```bash
# Run type checker
python -m mypy .

# Ignore specific errors (use sparingly)
# type: ignore[error-code]
```

---

## General Debug Tips

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Environment
```python
import os
print(os.environ.get('DB_HOST'))
```

### Verbose Testing
```bash
pytest -v --tb=long
```

---

## Processor Issues

### "No Response" from Bot

**Symptom:** User sends message but bot doesn't respond.

**Causes:**
- Agent initialization failed silently
- Empty response from ChatAgent
- Database connection issues

**Solutions:**
```python
# Check processor logs for errors
# Look for: "Intent: registro <- 'message'"
# Check for: "Error initializing Processor agents"

# Test processor manually
from core.processor import get_processor
p = get_processor()
result = p.process("test message", user_id=uuid)
print(result.response, result.action)
```

### Intent Classification Issues

**Symptom:** "gaste dinero" classified as chat instead of registro.

**Solutions:**
1. Check TASK_CLASSIFY in sistema_config database
2. Review classification logs: `Intent: chat <- 'gaste dinero...'`
3. Update keywords to include: "gast", "gasté", "pagué", "pagar"

### Empty Chat Responses

**Symptom:** Bot responds with empty message.

**Solution:** Fallback now implemented - should show default message.

---

## Getting Help

If issues persist:
1. Check [AGENTS.md](../AGENTS.md) for architecture details
2. Review [README.md](../README.md) for project overview
3. Check system logs: `journalctl -u myfinance`

---

*Last updated: 2026-04-01*
