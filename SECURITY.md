# Security Policy

## On-Device Privacy Gate Architecture
`MacHybridAI` is designed with a **Secure-by-Default** hybrid compute architecture:
1. **Fully Local Mode (`local`)**: Model and agent run 100% on your Mac. Private files and prompts never leave the device.
2. **Hybrid Mode with Privacy Gate (`hybrid`)**: Before any cloud model (Google Gemini, Google Antigravity, OpenAI Extension, or M365 Copilot Proxy) is invoked, the on-device `PIIGuardian` scans prompts and file excerpts locally on your Mac, replaces sensitive entities (Person names, Emails, Phone numbers, SSNs, Luhn-validated Credit Cards, API keys/tokens, IPv4 addresses, and custom sensitive terms) with reversible stand-in tokens (`[PERSON_1]`, `[EMAIL_1]`, etc.), and restores real values locally from the in-memory `PIIVault` after cloud reasoning completes.
3. **Loopback Isolation**: The local Python Hybrid Compute daemon binds strictly to `127.0.0.1` and rejects non-loopback interfaces.

## Automated Security Testing
Every Pull Request to `main` undergoes:
- **GitHub CodeQL SAST** for both `python` and `swift`
- **GitHub Dependency Review**
- **Bandit SAST & Pip-Audit**
- **Privacy Gate Zero-PII-Leak Regression Suite**

## Reporting a Vulnerability
Please report security vulnerabilities via GitHub Private Vulnerability Reporting on this repository.
