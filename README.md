# MacHybridAI

**Run Computer tasks locally on your Mac—or pair cloud models with local work protected by an on-device Privacy Gate.**

`MacHybridAI` is an open-source macOS AI Hybrid Compute application inspired by [Perplexity Hybrid Compute](https://www.perplexity.ai/hub/products/hybrid-compute). It combines a native **SwiftUI macOS Desktop & Menu Bar App** with a **Python Hybrid Compute & Google Antigravity Engine** that runs tasks either **100% on-device** or in **Hybrid Mode** with automatic PII redaction and local restoration.

---

## Download & Install for macOS (Apple Silicon `arm64` · macOS 14+)

[![Download MacHybridAI .dmg](https://img.shields.io/badge/Download_macOS_Installer-.dmg_(Recommended)-0ea5e9?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/mzia/MacHybridAI/releases/latest/download/MacHybridAI-latest.dmg)
[![Download MacHybridAI .pkg](https://img.shields.io/badge/Download_Package_Installer-.pkg-6366f1?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/mzia/MacHybridAI/releases/latest/download/MacHybridAI-latest.pkg)
[![Latest Release](https://img.shields.io/github/v/release/mzia/MacHybridAI?style=for-the-badge&color=10b981)](https://github.com/mzia/MacHybridAI/releases/latest)

Pre-built, self-contained native macOS installation packages (embedding both the SwiftUI macOS App and the Python Hybrid Compute Engine) are available on [**GitHub Releases**](https://github.com/mzia/MacHybridAI/releases/latest):

| Package Format | Direct 1-Click Download | How to Install |
| :--- | :--- | :--- |
| **macOS Disk Image (`.dmg`)** *(Recommended)* | [**`MacHybridAI-latest.dmg`**](https://github.com/mzia/MacHybridAI/releases/latest/download/MacHybridAI-latest.dmg) | Double-click `.dmg` and drag `MacHybridAI.app` into `/Applications` |
| **macOS Installer Package (`.pkg`)** | [**`MacHybridAI-latest.pkg`**](https://github.com/mzia/MacHybridAI/releases/latest/download/MacHybridAI-latest.pkg) | Double-click `.pkg` to run the guided macOS Installer targeting `/Applications` |
| **Zipped App Bundle (`.app.zip`)** | [**`MacHybridAI-latest-macos-arm64.app.zip`**](https://github.com/mzia/MacHybridAI/releases/latest/download/MacHybridAI-latest-macos-arm64.app.zip) | Unzip and move `MacHybridAI.app` to `/Applications` |
| **SHA-256 Checksums** | [**`SHA256SUMS.txt`**](https://github.com/mzia/MacHybridAI/releases/latest/download/SHA256SUMS.txt) | Verify download integrity (`shasum -a 256 -c SHA256SUMS.txt`) |

#### First-Launch Note (Open-Source Ad-Hoc Signed Build)
Because this open-source release is ad-hoc signed, if macOS Gatekeeper prompts on first launch after installing to `/Applications`, clear the quarantine attribute once and launch:
```bash
xattr -cr /Applications/MacHybridAI.app && open /Applications/MacHybridAI.app
```

---

## Hybrid Agentic CLI (`machybrid` / `mh`) — Antigravity-Style Terminal Agent

Use MacHybridAI directly from your terminal as an autonomous coding & computer agent—just like Google Antigravity (`agy`), but running **Hybrid Split-Compute** with on-device PII & secret redaction before any cloud call:

```bash
# 1. Install `machybrid` and `mh` into ~/.local/bin (zero pip required)
chmod +x scripts/install_cli.sh && ./scripts/install_cli.sh

# 2. Launch the interactive Hybrid Agentic REPL (with /mode, /provider, /plan, /approve, /hardware, /receipt)
machybrid

# 3. One-shot autonomous agent tasks with ANY Cloud AI behind the Privacy Gate
machybrid --mode hybrid --provider anthropic "Audit auth.py and fix edge cases"
machybrid --mode hybrid --provider openai --approve-cloud "Refactor billing.py"
machybrid --mode local "Summarize sensitive notes.txt privately on Apple Silicon"
machybrid --mode hybrid --provider consensus "Compare architectures for caching" --plan

# 4. Drop-in OpenAI-compatible privacy proxy for Cursor / Zed / Continue.dev
machybrid proxy --port 8765
```

---

## Documentation, Manual (`man`) & Wiki

Full setup and usage documentation is available in the [**MacHybridAI Wiki**](wiki/Home.md) and the UNIX manual page ([`man/MacHybridAI.1`](man/MacHybridAI.1) — view via `man ./man/MacHybridAI.1`):

| Main Wiki Section | Topics Covered |
| :--- | :--- |
| [**1. MacHybridAI User Manual & Architecture (`wiki/Home.md`)**](wiki/Home.md) | 4-Station Split-Compute pipeline, Desktop Studio, `M⇄AI` Menu Bar HUD, Compute Modes (`Fully Local`, `Hybrid`, `Auto`), and `MacHybridAI(1)` `man` reference |
| [**2. Installation & Setup Guide (`wiki/Installation-and-Setup.md`)**](wiki/Installation-and-Setup.md) | Native `.dmg` / `.pkg` installation, building from source (`./bundle.sh` / `./package.sh`), and environment configuration |
| [**3. Apple Silicon Hardware Profiler & Local Models (`wiki/Apple-Silicon-Hardware-Profiler-and-Local-Models.md`)**](wiki/Apple-Silicon-Hardware-Profiler-and-Local-Models.md) | Metal GPU working-set sizing, 1-Click Metal Benchmark (`TTFT`, `Prefill/Decode tok/s`), HuggingFace shard verification, and Thermal/RAM guardrails |
| [**4. Privacy Gate & Zero-Cloud History (`wiki/Privacy-Gate-and-Zero-Cloud-History.md`)**](wiki/Privacy-Gate-and-Zero-Cloud-History.md) | On-device PII masking (`[PERSON_1]`, `[EMAIL_1]`, etc.), local `PIIVault` restoration, encrypted Local/iCloud history, and Execution Receipts |
| [**5. Optional Cloud Provider: M365 Copilot Proxy (`wiki/M365-Copilot-Proxy-Setup-and-Usage.md`)**](wiki/M365-Copilot-Proxy-Setup-and-Usage.md) | Optional integration with [`cramt/m365-copilot-proxy`](https://github.com/mzia/MacHybridAI/blob/main/wiki/M365-Copilot-Proxy-Setup-and-Usage.md) (`m365-proxy`), Entra MFA sign-in, and `<tools>` markdown-fence tool calling |

---

## Key Features

### 1. Apple Silicon Hardware Profiler, Metal Benchmark & Thermal/RAM Guardrail
- **Hardware-Aware Model Sizing (`HardwareProfiler`)**: Automatically detects Apple Silicon SoC topology (Performance + Efficiency CPU cores, GPU cores via `IOAccelerator` `ioreg`, Unified Memory, and Metal `max_recommended_working_set_size`).
- **Local Cache Shard Validator**: Verifies HuggingFace cache completeness (`model.safetensors` / `model.safetensors.index.json` shards) before calling `mlx_lm.load()` so uncached multi-GB models never hang inference.
- **1-Click Apple Silicon Benchmark (`/v1/hardware/benchmark`)**: Measures live **Time-to-First-Token (TTFT ms)**, **Prefill tok/s**, **Decode tok/s**, and **Peak Metal Memory (GB)** directly from the SwiftUI Hardware Optimizer panel or Menu Bar popover.
- **Thermal & Unified Memory Pressure Guardrail**: Monitors thermal state (`nominal`, `fair`, `serious`, `critical`) and unified memory pressure, automatically stepping down to a compact 4-bit model (`mlx-community/gemma-3-4b-it-4bit`) if memory usage exceeds 85% or thermal pressure spikes.
- **Native `MenuBarExtra` Quick-Prompt HUD**: Always-accessible macOS menu bar item (`M⇄AI`) with live GPU/RAM/Thermal badges, PII mask counter, 1-click Metal benchmark, and instant Local/Hybrid chat.

### 2. Two Ways to Run Computer: Fully Local or Hybrid
- **Fully Local Mode (`local`)**: Both the model and the agent directing the task run on your Mac (via `google-antigravity` `LiteRTAgentConfig` on Apple Silicon Metal GPU, `LocalOpenAIAgentConfig` with Ollama/LM Studio, or native on-device processing). **Nothing leaves your Mac.**
- **Hybrid Mode (`hybrid`)**:
  1. **This Mac**: Local agent processes private files on your Mac.
  2. **Privacy Gate (PII Guardian)**: Scans prompts and file context on-device, masking personal information (Names, Emails, Phone Numbers, SSNs, Luhn-validated Credit Cards, API Keys/Secrets, IPv4 addresses, and custom sensitive terms) with reversible stand-in tokens (`[PERSON_1]`, `[EMAIL_1]`, `[PHONE_1]`, etc.).
  3. **Cloud Models**: Cloud models perform research and reasoning using the stand-in tokens only.
  4. **Result**: Local and cloud work are combined on your Mac and stand-in tokens are automatically restored to their real values from the local in-memory `PIIVault`.

### 3. Universal Cloud AI & Local Architecture (Compatible with Any Cloud AI Service)
- **Built-In Native & Preset Cloud Providers (All Protected by Station 2 Privacy Gate)**:
  - **OpenAI (`openai`)**: Native `gpt-4.1`, `gpt-4o`, `o3-mini`, `o4-mini` with `store: false` and `X-No-Store: true`.
  - **Anthropic Claude (`anthropic`)**: Native Anthropic Messages API (`POST /v1/messages`) supporting `claude-sonnet-4-5`, `claude-opus-4-1`, `claude-haiku-4-5`, and automatic OpenAI-to-Anthropic tool conversion.
  - **Google Gemini (`gemini-3.8-flash`) & Google Antigravity (`antigravity-preview-05-2026`)**: Powered by the `google-genai` (>= 2.3.0) Interactions API (`store=False`) and `google-antigravity` SDK.
  - **1-Click Cloud Presets**: **OpenRouter** (300+ models), **xAI Grok**, **Groq LPU**, **DeepSeek**, **Mistral AI**, **Perplexity Sonar**, and **Together AI**.
  - **Microsoft 365 Copilot Proxy ([`cramt/m365-copilot-proxy`](https://github.com/cramt/m365-copilot-proxy))**: Managed local proxy (`http://127.0.0.1:4141/v1`) with temporary chat locked (`disableMemory=1`) and `<tools>` Markdown-fence tool calling.
  - **Custom Any Cloud AI (`openai_compatible`)**: Point to **Azure OpenAI** (`?api-version=` preserved), AWS Bedrock / Vertex gateways, vLLM, LiteLLM, or any OpenAI (`/chat/completions`) or Anthropic (`/v1/messages`) endpoint with custom auth headers (`Authorization`, `x-api-key`, `api-key`).
  - **Multi-Cloud Consensus Arena (`consensus`)**: Dispatch the same Station 2 sanitized payload concurrently across **Gemini + Claude + OpenAI** and synthesize locally on-device with `PIIVault` restoration.
  - **Drop-In OpenAI-Compatible Local Proxy**: Point Cursor, Continue.dev, Zed, or any OpenAI SDK client to `http://127.0.0.1:<port>/v1` (`machybrid-auto`, `machybrid-local`, `machybrid-openai`, `machybrid-claude`, `machybrid-consensus`) for automatic on-device PII scrubbing, local BM25 RAG, Vision OCR redaction, and SHA-256 cryptographic privacy receipts.

---

## Architecture Diagram

![MacHybridAI 4-Station Local & Hybrid Split-Compute Architecture](wiki/assets/machybridai-architecture.png)

```mermaid
flowchart LR
    Task["User Task & Private Mac Files"] --> Mode{"Compute Mode"}
    Mode -- "Fully Local" --> MacLocal["This Mac (LiteRT Metal / Ollama)\nNothing leaves this Mac"]
    MacLocal --> Result["Final Result & Execution Receipt"]

    Mode -- "Hybrid" --> MacStage["1. This Mac: Local File Analysis"]
    MacStage --> Gate["2. Privacy Gate (PIIGuardian)\nMasks [PERSON_1], [EMAIL_1], [PHONE_1]"]
    Gate --> Cloud["3. Cloud Reasoning\nGemini 3.8 / Antigravity / M365 Proxy / OpenAI Ext"]
    Cloud --> Restore["4. Local PIIVault Restoration on This Mac"]
    Restore --> Result
```

---

## Quick Start on macOS

### 1. Run Unit & Security Tests
```bash
# Run Python Hybrid Engine & Privacy Gate tests
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v

# Build and test the native SwiftUI macOS application
swift build
swift test -v
```

### 2. Package and Launch `MacHybridAI.app`
```bash
chmod +x bundle.sh package.sh
./bundle.sh
open MacHybridAI.app
```

### 3. Build Distributable `.pkg` and `.dmg` Installers
```bash
./package.sh
ls -lh dist/
```

---

## GitHub Workflow & PR Governance
All code committed to this repository follows a strict Pull Request workflow targeting `main` and is verified by native GitHub Actions:
- **CI & Unit Testing (`.github/workflows/ci.yml`)**: Runs Python matrix unit tests (`3.11`, `3.12` on `ubuntu-latest` and `macos-14`) and macOS Swift 6 build, `swift test`, `.app` bundling, and `.pkg`/`.dmg` verification.
- **Security Scanning (`.github/workflows/security.yml`)**: Runs GitHub **CodeQL SAST** (`python` & `swift`), **GitHub Dependency Review**, **Bandit SAST**, and the **Privacy Gate Zero-PII-Leak Regression Suite**.

## License
MIT License — see [LICENSE](LICENSE).
