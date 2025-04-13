# Contributing Guide

Thank you for your interest in contributing to Ekko! This guide will help you get started.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

1. Fork the repository
2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/ekko-ce.git
```

3. Add the upstream repository:
```bash
git remote add upstream https://github.com/ekkoblock/ekko-ce.git
```

4. Create a new branch:
```bash
git checkout -b feature/your-feature-name
```

## Development Setup

1. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Install pre-commit hooks:
```bash
pre-commit install
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for all public functions and classes
- Keep functions focused and small
- Add tests for new features

## Testing

Run the test suite:
```bash
python -m pytest
```

Run with coverage:
```bash
python -m pytest --cov=.
```

## Pull Request Process

1. Update documentation for any new features
2. Add tests for new functionality
3. Ensure all tests pass
4. Update the CHANGELOG.md
5. Submit a pull request with a clear description

## Feature Requests

Open an issue with the `enhancement` label and describe:
- The problem you want to solve
- Your proposed solution
- Any alternatives you've considered

## Bug Reports

When reporting bugs, include:
- Description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)

## Code Review Process

1. At least one maintainer must approve changes
2. CI checks must pass
3. Documentation must be updated
4. Tests must cover new code

## Community

- Join our [Discord](https://discord.gg/ekko)
- Follow us on [Twitter](https://twitter.com/ekkoblock)
- Read our [Blog](https://blog.ekkoblock.com)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
