# Installation and Setup

`MacHybridAI` runs natively on **macOS 14.0 (Sonoma) or newer** on Apple Silicon (`M1` / `M2` / `M3` / `M4` / `M5` series Macs).

---

## Option 1: Install via Native macOS `.dmg` or `.pkg` (Recommended)

1. Download the latest installer from [GitHub Releases](https://github.com/mzia/MacHybridAI/releases/latest):
   - **Disk Image**: [`MacHybridAI-latest.dmg`](https://github.com/mzia/MacHybridAI/releases/latest/download/MacHybridAI-latest.dmg) — open the `.dmg` and drag **`MacHybridAI.app`** into `/Applications`.
   - **Package Installer**: [`MacHybridAI-latest.pkg`](https://github.com/mzia/MacHybridAI/releases/latest/download/MacHybridAI-latest.pkg) — double-click and follow the macOS Installer wizard to install into `/Applications/MacHybridAI.app`.
2. **First-Launch Gatekeeper Note** (for open-source ad-hoc signed builds):
   ```bash
   xattr -cr /Applications/MacHybridAI.app
   open /Applications/MacHybridAI.app
   ```
3. Once launched, **`MacHybridAI`** opens both:
   - The main **Hybrid Compute Studio Window**, and
   - The persistent **`M⇄AI` Menu Bar Extra** icon in your macOS menu bar.

---

## Option 2: Build & Package from Source

### Prerequisites
- **macOS 14+** with **Xcode 16+ / Swift 6 Command Line Tools** (`xcode-select --install`)
- **Python 3.11+** (`/opt/homebrew/bin/python3` recommended on Apple Silicon)

### 1. Clone the Repository & Install Python Engine
```bash
git clone https://github.com/mzia/MacHybridAI.git
cd MacHybridAI

# Install the Python backend + Apple Silicon MLX + Cloud SDKs
python3 -m pip install -e "backend[local-mlx,cloud,dev]"
```

### 2. Build Self-Contained `MacHybridAI.app`
```bash
chmod +x bundle.sh package.sh
./bundle.sh
open MacHybridAI.app
```

### 3. Build Distributable `.dmg`, `.pkg`, & `.app.zip` Installers
```bash
./package.sh
ls -lh dist/
```
This produces in `dist/`:
- `MacHybridAI-latest.dmg` & `MacHybridAI-1.1.0.dmg`
- `MacHybridAI-latest.pkg` & `MacHybridAI-1.1.0.pkg`
- `MacHybridAI-latest-macos-arm64.app.zip`
- `SHA256SUMS.txt`

---

## Configuring Cloud & Local Credentials

All cloud credentials are optional if you run in **Fully Local Mode** or use **M365 Copilot Proxy**:

| Provider | Environment Variable / Config File | Notes |
| :--- | :--- | :--- |
| **Apple Silicon Local MLX** | None required (`~/.cache/huggingface/hub`) | Uses on-device Metal GPU; auto-selects cached models |
| **M365 Copilot Proxy** | `~/.config/opencode-m365/secrets.json` or Interactive Browser SSO | See [M365 Copilot Proxy Setup & Usage](M365-Copilot-Proxy-Setup-and-Usage) |
| **Google Gemini** | `export GEMINI_API_KEY="your-key"` | Uses `google-genai` Interactions API with `store=False` |
| **Google Antigravity** | `export ANTIGRAVITY_API_KEY="your-key"` | Supports local & remote managed agents |
| **OpenAI-Compatible** | `export OPENAI_API_KEY="your-key"` | Works with OpenAI, OpenRouter, Groq, vLLM, Ollama |
