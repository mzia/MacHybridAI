# Apple Silicon Hardware Profiler, Metal Benchmark & Local Models

`MacHybridAI` includes a native **Apple Silicon Hardware Profiler (`HardwareProfiler`)** and **MLX Inference Engine (`MLXProvider`)** designed to maximize token generation throughput (`tok/s`) while preventing unified memory swap thrashing.

---

## 1. Zero-Root Apple Silicon Hardware Profiling

When `MacHybridAI` starts (or when you open **AI Providers & M365** -> **Apple Silicon Hardware & Local Model Optimizer**), it queries macOS kernel & Metal APIs with **zero `sudo`/root privileges**:

- **SoC & CPU Topology**: Detects chip brand (e.g., `Apple M5 Pro`), total logical cores, Performance/Super cores (`hw.perflevel0.physicalcpu`), and Efficiency cores (`hw.perflevel1.physicalcpu`).
- **Metal GPU Architecture & Utilization**: Queries `ioreg -r -d 1 -c IOAccelerator -a` (`PerformanceStatistics`) for GPU core count, live **Device Utilization %**, **Renderer Utilization %**, **Tiler Utilization %**, and **Allocated Metal VRAM (GB)**.
- **Metal Working-Set Budget**: Queries `mlx.core.device_info()` for `max_recommended_working_set_size` (e.g., `37.44 GB` on a 48 GB Mac) and `max_buffer_length` (`28.08 GB`), reserving ~12% headroom for macOS `WindowServer` and long-context KV caches.

---

## 2. Hardware-Matched Local Model Catalog

`HardwareProfiler` recommends and auto-selects models based on your Mac's Metal working-set budget and local HuggingFace cache (`~/.cache/huggingface/hub`):

| Model ID | Parameters & Quant | Est. Metal Footprint | Expected Speed (M-Series Pro/Max) | Recommended KV Cache | Best Use Case |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`mlx-community/gemma-3-4b-it-4bit`** | 4B · 4-bit | ~2.6 GB | 90–140 tok/s | FP16 (`None`) | Fast interactive chat, Station 1 file extraction, low-RAM fallback |
| **`mlx-community/Qwen2.5-3B-Instruct-4bit`** | 3B · 4-bit | ~2.0 GB | 110–160 tok/s | FP16 (`None`) | Ultra-lightweight background agent & 8–16 GB Macs |
| **`mlx-community/gemma-3-12b-it-4bit`** | 12B · 4-bit | ~7.2 GB | 45–65 tok/s | 8-bit | Balanced daily driver on 16–36 GB Macs |
| **`mlx-community/Qwen2.5-Coder-14B-Instruct-4bit`** | 14B · 4-bit | ~8.5 GB | 40–58 tok/s | 8-bit | Local code analysis & refactoring on 24+ GB Macs |
| **`mlx-community/gemma-4-26b-it-4bit`** | 26B · 4-bit | ~15.5 GB | 32–45 tok/s | 8-bit | High-accuracy local reasoning on 36–48 GB Macs |
| **`lmstudio-community/gemma-4-31B-it-MLX-4bit`** | 31B · 4-bit | ~18.2 GB | 28–40 tok/s | 8-bit | Deep local reasoning sweet-spot on 48 GB Macs |
| **`lmstudio-community/gemma-4-31B-it-MLX-8bit`** | 31B · 8-bit | ~33.5 GB | 14–22 tok/s | 4-bit | Maximum precision on 48–128 GB Max/Ultra Macs |

---

## 3. Local Cache Shard Validator & In-App Model Downloader

Large MLX models are split across multiple `.safetensors` shards indexed by `model.safetensors.index.json`. If a previous download was interrupted, calling `mlx_lm.load()` directly can hang while attempting to download missing multi-GB shards.

`MacHybridAI` prevents this automatically:
1. Before loading any model, `HardwareProfiler.inspect_hf_model_cache()` verifies `config.json` and every `.safetensors` shard in the local snapshot directory.
2. In the **AI Providers & M365** tab, each model displays either:
   - **`Cached & Verified`** (green badge) — ready for instant on-device execution, or
   - **`Weights Not Downloaded`** (orange badge) — click **"Download / Verify"** in the UI (or copy the `huggingface-cli download <model_id>` command) to pull or repair missing shards.

---

## 4. 1-Click Apple Silicon Metal Benchmark

Click **"Run 1-Click Benchmark"** in the **AI Providers & M365** tab (or **"Benchmark"** in the `M⇄AI` Menu Bar popover) to run a live on-device benchmark measuring:
- **TTFT (ms)**: Time-to-First-Token latency in milliseconds
- **Prefill (tok/s)**: Prompt processing throughput
- **Decode (tok/s)**: Token generation speed
- **Peak Metal (GB)**: Peak wired Metal GPU memory used during generation

---

## 5. Automatic Thermal & Unified Memory Pressure Guardrail

`MacHybridAI` continuously monitors macOS thermal state (`nominal`, `fair`, `serious`, `critical`) and unified memory usage:
- If unified memory usage reaches **`>= 85%`**, available memory drops below the active model's footprint, or thermal state enters **`serious` / `critical`**, `HardwareProfiler.evaluate_guardrail()` automatically steps down from large models (`>= 12B`) to the compact 4-bit model (`mlx-community/gemma-3-4b-it-4bit`) and displays an orange **Guardrail Active** banner in the UI.
