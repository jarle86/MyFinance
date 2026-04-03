# MyFinance 4.0

## Project Briefing

MyFinance 4.0 is an AI-powered personal finance operating system designed to automate financial record-keeping through orchestrated agents. It features synchronous, direct agent communication for tasks such as intent classification, OCR invoice processing, semantic evaluation, JSON parsing, SQL validation/execution, and humanized chat interactions. Built with Python 3.10+, it emphasizes immutability, no hardcoding, and zero-shot prompts to ensure reliability and security in financial operations.

### Key Features
- **Agent Architecture**: 6 specialized agents (A1-A6) handling classification, OCR, evaluation, parsing, SQL execution, and chat.
- **No RAG/Semantic State**: Synchronous flows with direct communication.
- **Tool Calling**: Secure database operations via tools, eliminating raw SQL generation.
- **Interactive Mode**: Handles ambiguities with user confirmation.
- **Configuration**: Centralized in `sistema_config` for prompts, thresholds, and models.
- **Testing & Linting**: Comprehensive with pytest, ruff, black, and mypy.

### Getting Started
- Install dependencies: `pip install -r requirements.txt`
- Run the application: `python main.py` (Telegram gateway) or `streamlit run web/dashboard/main.py`
- Run tests: `python -m pytest`

For detailed guidelines, see [AGENTS.md](docs/AGENTS.md).

## License

MIT License

Copyright (c) 2026 MyFinance Team

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
