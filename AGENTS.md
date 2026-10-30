# MacHybridAI Agent Rules & CI Success Criteria

## Mandatory CI & PR Success Criteria

1. **Always Run Local CI Checks Before Committing or Pushing**:
   Before creating a commit or pushing to a remote branch, execute every check that runs in `.github/workflows/ci.yml` and `.github/workflows/security.yml` and verify zero errors:
   - **Python Unit Tests & Privacy Gate**:
     ```bash
     PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
     ```
   - **Python Linter (Ruff)**:
     ```bash
     ruff check backend/machybrid/ backend/tests/
     ```
   - **Python SAST (Bandit)**:
     ```bash
     bandit -r backend/machybrid -ll -ii
     ```
   - **macOS Swift 6 Release Build & Unit Tests**:
     ```bash
     swift build -c release && swift test -v
     ```

2. **Passing GitHub PR Checks Are Required for Task Completion**:
   - Whenever opening or updating a Pull Request, monitor all GitHub Actions workflows and CodeQL/security checks to completion:
     ```bash
     gh pr checks <PR_NUMBER> --watch
     ```
   - A PR or coding task is **not complete** until all CI, unit test, build/packaging, and CodeQL security checks report `SUCCESS` (`✓`) on GitHub.
   - If any check fails on GitHub Actions, immediately inspect the failure logs/annotations (`gh run view --log-failed` or `gh api repos/<owner>/<repo>/check-runs/<id>/annotations`), fix the issue locally, re-run local CI, push the fix, and re-verify until 100% green.

3. **Security & CodeQL Hygiene**:
   - Never construct filesystem paths directly from unvalidated HTTP/CLI request parameters (`py/path-injection`); validate against strict allowlists and/or resolve against enumerated directory entries.
   - Annotate audited `subprocess` calls with `# nosec` only when arguments are static system binaries without shell invocation.
