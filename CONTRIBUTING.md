# Contributing to MacHybridAI

Thank you for contributing to **MacHybridAI**!

## Mandatory Pull Request & Testing Policy
1. **No Direct Commits to `main`**: All generated or human-written code changes must be developed on a feature branch (e.g., `feat/...` or `fix/...`) and submitted via a Pull Request to `main`.
2. **Native GitHub CI, Unit Testing & Security Checks**: Every PR must pass:
   - Python Hybrid Compute & PII Guardian unit tests (`backend/tests/`)
   - SwiftUI macOS build & XCTest suite (`Tests/MacHybridAITests/`)
   - GitHub CodeQL SAST (`python` & `swift`), Dependency Review, and Bandit security scans.

## Local Development on macOS
```bash
# 1. Run Python Backend Unit & Security Tests
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v

# 2. Build & Test Native SwiftUI macOS App
swift build
swift test -v

# 3. Package MacHybridAI.app Bundle
./bundle.sh
open MacHybridAI.app
```
