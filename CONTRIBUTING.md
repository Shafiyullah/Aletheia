# Contributing to Aletheia

Thank you for your interest in contributing to Aletheia! We are building the future of neuro-symbolic AI verification.

## Getting Started

1.  **Fork** the repository.
2.  **Clone** your fork: `git clone https://github.com/Shafiyullah/Aletheia.git`
3.  **Install dependencies**: `pip install -r requirements.txt`
4.  **Create a branch** for your feature: `git checkout -b feature/amazing-feature`

## Development Guidelines

### Code Style
- We use **Python 3.12+**.
- Follow **PEP 8** guidelines.
- Use type hints (`typing`) for all function signatures.

### Architecture
- **Core Logic**: Keep all business logic in `core/`.
- **UI**: Keep `app.py` focused on Streamlit rendering.
- **Async**: Use `core/async_utils.py` for all heavy I/O or CPU tasks.

### Testing
- Run tests before submitting a PR: `pytest`
- Add new tests for new features in `tests/`.

## Pull Request Process

1.  Ensure all tests pass.
2.  Update `README.md` if you change functionality.
3.  Submit a Pull Request with a clear description of changes.

## License
By contributing, you agree that your contributions will be licensed under the project's MIT License.
