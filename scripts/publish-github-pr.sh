#!/usr/bin/env bash
set -euo pipefail

# Automates publishing MacHybridAI to GitHub (mzia/MacHybridAI) with:
# 1. Minimal initial commit on `main`
# 2. All generated application, engine, test, and CI/security code on `feat/initial-hybrid-ai-app`
# 3. Opening a Pull Request (`feat/initial-hybrid-ai-app` -> `main`) so all generated code
#    undergoes native GitHub CI, Unit Testing, and Security Testing before merging to `main`.

cd "$(dirname "$0")/.."
REPO_NAME="${1:-MacHybridAI}"
BRANCH_NAME="feat/initial-hybrid-ai-app"

if ! gh auth status >/dev/null 2>&1; then
  echo "==> Authenticating GitHub CLI (gh) via browser..."
  printf "\n" | gh auth login -h github.com --skip-ssh-key -w
fi

GH_USER="$(gh api user -q .login)"
echo "==> Authenticated as GitHub user: ${GH_USER}"

if ! gh repo view "${GH_USER}/${REPO_NAME}" >/dev/null 2>&1; then
  echo "==> Creating public open-source GitHub repository ${GH_USER}/${REPO_NAME}..."
  gh repo create "${GH_USER}/${REPO_NAME}" \
    --public \
    --description "macOS Hybrid Compute AI App with On-Device PII Guardian (Privacy Gate), Google Antigravity, Gemini, Local Models, OpenAI Extension & M365 Copilot Proxy"
fi

REMOTE_URL="git@github.com:${GH_USER}/${REPO_NAME}.git"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "${REMOTE_URL}"
else
  git remote add origin "${REMOTE_URL}"
fi

echo "==> Pushing base branch 'main' and feature branch '${BRANCH_NAME}' via SSH..."
git push -u origin main
git push -u origin "${BRANCH_NAME}"

echo "==> Creating Pull Request (${BRANCH_NAME} -> main)..."
gh pr create \
  --base main \
  --head "${BRANCH_NAME}" \
  --title "feat: MacHybridAI macOS Hybrid Compute App, Privacy Gate PII Guardian, Antigravity/Gemini & M365 Copilot Proxy" \
  --body "## Summary
- Implements **MacHybridAI**, a native SwiftUI macOS application and Python Hybrid Compute engine inspired by Perplexity Hybrid Compute.
- **On-Device Privacy Gate (\`PIIGuardian\` & \`PIIVault\`)**: Automatically flags and masks PII (Names, Emails, Phone Numbers, SSNs, Luhn-validated Credit Cards, Secrets/API Keys, IPv4, custom terms) with reversible stand-in tokens (\`[PERSON_1]\`, \`[EMAIL_1]\`, etc.) before cloud calls and restores real values locally on your Mac.
- **Default Cloud & Local Providers**: Google Gemini (\`gemini-3.8-flash\` Interactions API), Google Antigravity (\`antigravity-preview-05-2026\` & \`google-antigravity\` SDK \`LocalAgentConfig\`, \`LiteRTAgentConfig\`, \`LocalOpenAIAgentConfig\`), OpenAI Extension API, and local models (LiteRT Metal GPU / Ollama / LM Studio).
- **M365 Copilot Proxy Integration (\`cramt/m365-copilot-proxy\`)**: Built-in proxy process manager, model catalog (\`gpt-5.5-think-deeper\`, \`gpt-6.1-sol\`, \`claude-sonnet-4.6\`), and prompt-emulated Markdown-fence + shell-routing tool calling.
- **Native GitHub CI, Unit Testing & Security Scanning**: Includes \`.github/workflows/ci.yml\` and \`.github/workflows/security.yml\` (CodeQL SAST for Python & Swift, Dependency Review, Bandit SAST, and PII Zero-Leak Regression Gate)."
