# Test Directory Structure

## Directory Structure
- `unit/`: Unit tests
- `integration/`: Integration tests
- `e2e/`: End-to-end tests

## Running Tests
```bash
# All tests
pytest

# Unit tests
pytest tests/unit

# Integration tests
pytest tests/integration

# With coverage
pytest --cov=core tests/
```
