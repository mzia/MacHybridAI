import SwiftUI
import AppKit

/// Native macOS Settings / Preferences Window (`⌘,`), structured per Apple Human Interface Guidelines
/// with a standard macOS `TabView` icon toolbar and grouped `Form` panes.
struct MacHybridSettingsView: View {
    @ObservedObject var vm: HybridAppViewModel
    @AppStorage("appAppearance") private var appAppearanceRaw: String = AppAppearanceOption.system.rawValue

    private var appearanceBinding: Binding<AppAppearanceOption> {
        Binding(
            get: { AppAppearanceOption(rawValue: appAppearanceRaw) ?? .system },
            set: { appAppearanceRaw = $0.rawValue }
        )
    }

    var body: some View {
        TabView {
            generalPane
                .tabItem {
                    Label("General", systemImage: "gearshape")
                }

            localAndSecurityPane
                .tabItem {
                    Label("Local & Security", systemImage: "lock.shield")
                }

            cloudProvidersPane
                .tabItem {
                    Label("Cloud AI", systemImage: "cloud")
                }

            privacyGatePane
                .tabItem {
                    Label("Privacy Gate", systemImage: "key.viewfinder")
                }

            hardwarePane
                .tabItem {
                    Label("Hardware", systemImage: "memorychip")
                }
        }
        .frame(width: 720, height: 560)
    }

    // MARK: - 1. General & History

    private var generalPane: some View {
        Form {
            Section("Appearance & Defaults") {
                Picker("Appearance", selection: appearanceBinding) {
                    ForEach(AppAppearanceOption.allCases, id: \.self) { opt in
                        Text(opt.displayName).tag(opt)
                    }
                }
                .pickerStyle(.segmented)

                Picker("Default Compute Mode", selection: $vm.computeMode) {
                    ForEach(ComputeModeOption.allCases, id: \.self) { option in
                        Text(option.title).tag(option)
                    }
                }

                Text(vm.computeMode.subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Prompt History Storage, Cloud Sharing & Auto-Delete") {
                Picker("Save Conversations To", selection: $vm.historyStorage) {
                    ForEach(HistoryStorageOption.allCases, id: \.self) { opt in
                        Label(opt.title, systemImage: opt.iconName).tag(opt)
                    }
                }
                .onChange(of: vm.historyStorage) { _, _ in
                    vm.updateHistorySettings()
                }

                if vm.historyStorage == .googleDrive {
                    HStack {
                        Text(vm.googleDrivePathDisplay)
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                        Spacer()
                        Button("Choose Folder…") {
                            vm.chooseCustomGoogleDriveFolder()
                        }
                        .controlSize(.small)
                    }
                }

                Toggle("Redact PII Automatically Before Sharing", isOn: $vm.redactPIIOnShare)

                HStack {
                    Text("Shared Exports Folder")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("Open in Finder") {
                        vm.openSharedFolderInFinder()
                    }
                    .controlSize(.small)
                }

                Picker("Auto-Delete Retention", selection: $vm.historyRetention) {
                    ForEach(HistoryRetentionOption.allCases, id: \.self) { ret in
                        Text(ret.displayName).tag(ret)
                    }
                }
                .onChange(of: vm.historyRetention) { _, _ in
                    vm.updateHistorySettings()
                }

                LabeledContent("Cloud AI History") {
                    Label("ZERO (store=false · Temporary Chat)", systemImage: "checkmark.shield.fill")
                        .font(.caption.bold())
                        .foregroundStyle(.green)
                }
            }

            Section("Native Compute Engine") {
                LabeledContent("Runtime Architecture") {
                    DaemonStatusView()
                }
                Text("MacHybridAI.app runs 100% natively in Swift on macOS with zero Python background daemon.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
    }

    // MARK: - 2. Local Runtime & Supply-Chain Security

    private var localAndSecurityPane: some View {
        Form {
            Section("On-Device Local Runtime") {
                Picker("Local Inference Backend", selection: $vm.localBackend) {
                    ForEach(LocalBackendOption.allCases, id: \.self) { backend in
                        Text(backend.displayName).tag(backend)
                    }
                }
                .onChange(of: vm.localBackend) { _, newBackend in
                    vm.setLocalBackend(newBackend)
                }

                HStack(spacing: 8) {
                    Image(systemName: vm.appleFMStatus.available ? "checkmark.seal.fill" : "info.circle")
                        .foregroundStyle(vm.appleFMStatus.available ? .green : .secondary)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(vm.appleFMStatus.modelName)
                            .font(.caption.bold())
                        Text(vm.appleFMStatus.reason)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            Section("Model Supply-Chain Protection") {
                HStack(spacing: 10) {
                    Image(systemName: vm.allowUnverifiedHuggingFace ? "exclamationmark.triangle.fill" : "lock.shield.fill")
                        .foregroundStyle(vm.allowUnverifiedHuggingFace ? .orange : .green)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(
                            vm.allowUnverifiedHuggingFace
                                ? "WARNING: Unverified Hugging Face Bypass ACTIVE"
                                : "Strict Supply-Chain Protection ACTIVE (Default)"
                        )
                        .font(.caption.bold())
                        .foregroundStyle(vm.allowUnverifiedHuggingFace ? .orange : .green)
                        Text(
                            vm.allowUnverifiedHuggingFace
                                ? "Community Hugging Face repos (e.g. mlx-community/*) are allowed. Remote Python code (trust_remote_code=False) and pickle/executable files remain hard-blocked."
                                : "Only Apple-signed Foundation Models, verified local directories, first-party publishers, or SHA-256 lockfile-pinned models are allowed."
                        )
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Toggle(
                        "Allow Unverified Hugging Face",
                        isOn: Binding(
                            get: { vm.allowUnverifiedHuggingFace },
                            set: { desired in
                                if desired {
                                    vm.isShowingHuggingFaceWarningAlert = true
                                } else {
                                    vm.setAllowUnverifiedHuggingFace(false)
                                }
                            }
                        )
                    )
                    .labelsHidden()
                    .toggleStyle(.switch)
                }

                LabeledContent("Hard Security Locks") {
                    Text("trust_remote_code=False · .py/.bin/.pt/.pkl Blocked")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Section("Local Model Directory & Endpoints") {
                HStack(spacing: 8) {
                    TextField("Verified Local Model Directory (skips Hugging Face Hub)", text: $vm.localModelDir)
                        .onChange(of: vm.localModelDir) { _, newDir in
                            vm.setLocalModelDir(newDir)
                        }
                    Button("Choose…") {
                        chooseLocalModelDirectory()
                    }
                }

                TextField("Active Local Model ID (MLX / LiteRT / Ollama)", text: $vm.localModel)
                    .onChange(of: vm.localModel) { _, newValue in
                        vm.selectRecommendedModel(newValue)
                    }

                TextField("Local OpenAI-Compatible Endpoint", text: $vm.localEndpoint)
            }
        }
        .formStyle(.grouped)
        .alert(
            "Security Warning: Bypass Hugging Face Supply-Chain Protection?",
            isPresented: $vm.isShowingHuggingFaceWarningAlert
        ) {
            Button("I Accept the Risk — Enable Bypass", role: .destructive) {
                vm.setAllowUnverifiedHuggingFace(true)
            }
            Button("Cancel (Keep Strict Protection)", role: .cancel) {
                vm.setAllowUnverifiedHuggingFace(false)
            }
        } message: {
            Text(
                "Enabling this setting allows loading unverified third-party community Hugging Face models (such as mlx-community/* or lmstudio-community/*).\n\n"
                + "These repositories are NOT signed by Apple and could be modified by community contributors. "
                + "MacHybridAI still enforces trust_remote_code=False and blocks .py/.bin/.pt/.pkl files, but weights and chat templates are not Apple-signed.\n\n"
                + "For maximum security, use Apple Foundation Models (macOS 26+) or a verified local directory instead."
            )
        }
    }

    // MARK: - 3. Cloud AI Providers & Local Proxy

    private var cloudProvidersPane: some View {
        Form {
            Section("Active Cloud AI Provider (Behind Station 2 Privacy Gate)") {
                Picker("Cloud Provider", selection: $vm.cloudProvider) {
                    ForEach(CloudProviderOption.allCases, id: \.self) { provider in
                        Text(provider.displayName).tag(provider)
                    }
                }
                .onChange(of: vm.cloudProvider) { _, newProvider in
                    vm.applyCloudProviderPreset(newProvider)
                }

                HStack(spacing: 8) {
                    SecureField(
                        "In-Memory API Key for \(vm.cloudProvider.shortName) (or set \(vm.cloudProvider.apiKeyEnvName))",
                        text: $vm.cloudApiKeyInput
                    )
                    Button("Load Key (RAM Only)") {
                        vm.syncCloudProviderConfiguration()
                    }
                }

                if !vm.providerSyncStatus.isEmpty {
                    Label(vm.providerSyncStatus, systemImage: "checkmark.circle.fill")
                        .font(.caption)
                        .foregroundStyle(.green)
                }
            }

            Section("OpenAI, OpenRouter, xAI Grok, Groq, DeepSeek, Mistral, Perplexity, Together & Custom") {
                Picker("Wire Protocol", selection: $vm.customProviderProtocol) {
                    ForEach(CustomCloudProtocolOption.allCases, id: \.self) { proto in
                        Text(proto.displayName).tag(proto)
                    }
                }
                TextField("Base URL (e.g. https://api.openai.com/v1)", text: $vm.openAIBaseURL)
                TextField("Model Identifier (e.g. gpt-4.1, o3-mini, grok-3)", text: $vm.openAIModel)
                TextField("Auth Header (Authorization, x-api-key, or api-key)", text: $vm.customProviderAuthHeader)
            }

            Section("Anthropic Claude (Native /v1/messages)") {
                TextField("Claude Model (e.g. claude-sonnet-4-5)", text: $vm.anthropicModel)
                TextField("Anthropic Base URL", text: $vm.anthropicBaseURL)
            }

            Section("Google Gemini & Antigravity (Stateless store=false)") {
                TextField("Gemini Model", text: $vm.geminiModel)
                TextField("Antigravity Agent ID", text: $vm.antigravityAgent)
            }

            Section("Microsoft 365 Copilot Proxy (Temporary Chat Locked)") {
                TextField("Loopback Port", text: $vm.m365Port)
                TextField("M365 Model", text: $vm.m365Model)
                Toggle("Interactive Browser SSO/MFA Approval", isOn: $vm.m365InteractiveApproval)
                Toggle("Avoid PerUserThrottled Reserve Guard", isOn: $vm.m365AvoidThrottling)
            }

            Section("IDE Privacy Proxy (/v1/chat/completions)") {
                HStack {
                    Text("Point Cursor, Continue.dev, or Zed to MacHybridAI's local loopback proxy.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("Copy Base URL") {
                        let portStr: String
                        if case .running(let p) = DaemonManager.shared.state {
                            portStr = "\(p)"
                        } else {
                            portStr = "8765"
                        }
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString("http://127.0.0.1:\(portStr)/v1", forType: .string)
                    }
                }
            }
        }
        .formStyle(.grouped)
    }

    // MARK: - 4. Privacy Gate

    private var privacyGatePane: some View {
        Form {
            Section("Station 2 PII Guardian Policy") {
                Picker("Masking Policy", selection: $vm.guardianPolicy) {
                    ForEach(GuardianPolicyOption.allCases, id: \.self) { policy in
                        Text(policy.displayName).tag(policy)
                    }
                }
                .onChange(of: vm.guardianPolicy) { _, _ in
                    vm.runInspector()
                    vm.updateComposerLiveAudit()
                }

                Toggle("Approve Sanitized Prompt Before Cloud Dispatch", isOn: $vm.approveBeforeCloudDispatch)
            }

            Section("Zero-Knowledge Architecture") {
                LabeledContent("PIIVault Scope") {
                    Text("RAM-Only on this Mac (cleared on quit)")
                        .foregroundStyle(.secondary)
                }
                LabeledContent("Cloud Retention") {
                    Text("Disabled (store=false, X-No-Store: true)")
                        .foregroundStyle(.green)
                }
                LabeledContent("Audit Receipts") {
                    Text("SHA-256 outbound payload digest on every turn")
                        .foregroundStyle(.secondary)
                }
            }
        }
        .formStyle(.grouped)
    }

    // MARK: - 5. Apple Silicon Hardware & Model Cache

    private var hardwarePane: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Apple Silicon Hardware Profiler")
                            .font(.headline)
                        Text("Live Metal working-set budget, thermal guardrail, and local model cache status.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button {
                        vm.refreshHardwareProfile()
                    } label: {
                        Label("Re-Profile", systemImage: "arrow.clockwise")
                    }
                    Button {
                        vm.runBenchmark(for: vm.localModel)
                    } label: {
                        Label(vm.isBenchmarking ? "Benchmarking…" : "Run Benchmark", systemImage: "speedometer")
                    }
                    .disabled(vm.isBenchmarking)
                }

                if let hw = vm.hardwareProfile {
                    GroupBox("\(hw.chipBrand) · \(hw.unifiedMemoryGb) GB Unified Memory") {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack(spacing: 16) {
                                Label("\(hw.cpuCoresTotal) CPU (\(hw.cpuCoresPerformance)P+\(hw.cpuCoresEfficiency)E)", systemImage: "cpu")
                                Label("\(hw.gpuCores)-Core GPU", systemImage: "sparkles.tv")
                                Label(String(format: "Metal Budget: %.1f GB", hw.metalWorkingSetGb), systemImage: "memorychip")
                            }
                            .font(.caption)

                            HStack(spacing: 16) {
                                Label("RAM Used: \(hw.memoryUsedPercent)% (\(String(format: "%.1f", hw.availableMemoryGb)) GB free)", systemImage: "gauge.medium")
                                Label("Thermal: \(hw.thermalState.capitalized)", systemImage: "thermometer.medium")
                                    .foregroundStyle(hw.thermalState == "nominal" ? .green : .orange)
                                if let kv = hw.recommendedKvBits {
                                    Label("KV Cache: \(kv)-bit", systemImage: "bolt.horizontal.fill")
                                        .foregroundStyle(.green)
                                }
                            }
                            .font(.caption)

                            if hw.guardrailTriggered {
                                Label(hw.guardrailReason, systemImage: "exclamationmark.shield.fill")
                                    .font(.caption2.bold())
                                    .foregroundStyle(.orange)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(6)
                    }

                    if let bench = vm.latestBenchmark {
                        GroupBox("Latest Metal Benchmark — \(bench.modelId)") {
                            HStack(spacing: 16) {
                                Text(String(format: "TTFT: %.0f ms", bench.ttftMs))
                                Text(String(format: "Prefill: %.1f tok/s", bench.prefillTps))
                                Text(String(format: "Decode: %.1f tok/s", bench.decodeTps))
                                    .bold()
                                    .foregroundStyle(.green)
                                Text(String(format: "Peak: %.2f GB", bench.peakMemoryGb))
                            }
                            .font(.caption.monospaced())
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(6)
                        }
                    }

                    GroupBox("Downloaded & Usable On This Mac") {
                        VStack(alignment: .leading, spacing: 8) {
                            // 1. Apple-Signed OS Foundation Model (Always shown first)
                            HStack(spacing: 8) {
                                Image(systemName: vm.appleFMStatus.available ? "checkmark.seal.fill" : "xmark.circle")
                                    .foregroundStyle(vm.appleFMStatus.available ? .green : .secondary)
                                VStack(alignment: .leading, spacing: 2) {
                                    HStack(spacing: 6) {
                                        Text(vm.appleFMStatus.modelName)
                                            .font(.caption.bold())
                                        Text("Apple-Signed · Zero HF")
                                            .font(.caption2.bold())
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 1)
                                            .background(Capsule().fill(Color.green.opacity(0.18)))
                                            .foregroundStyle(.green)
                                    }
                                    Text(vm.appleFMStatus.reason)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(vm.appleFMStatus.available ? "USABLE" : "UNAVAILABLE")
                                    .font(.caption2.bold())
                                    .foregroundStyle(vm.appleFMStatus.available ? .green : .secondary)
                                Button(vm.localBackend == .appleFoundationModels ? "Active" : "Use") {
                                    vm.setLocalBackend(.appleFoundationModels)
                                }
                                .controlSize(.small)
                                .disabled(!vm.appleFMStatus.available)
                            }

                            if !hw.cachedModels.isEmpty {
                                Divider()
                                ForEach(hw.cachedModels) { cached in
                                    HStack(spacing: 8) {
                                        Image(systemName: cached.isUsable ? "checkmark.circle.fill" : (cached.isComplete ? "lock.trianglebadge.exclamationmark.fill" : "exclamationmark.triangle"))
                                            .foregroundStyle(cached.isUsable ? .green : (cached.isComplete ? .orange : .red))
                                        VStack(alignment: .leading, spacing: 2) {
                                            HStack(spacing: 6) {
                                                Text(cached.backend == "mlx_local_dir" ? URL(fileURLWithPath: cached.modelId).lastPathComponent : cached.modelId)
                                                    .font(.caption.bold())
                                                    .lineLimit(1)
                                                Text("\(cached.sizeGbFormatted) · \(cached.quantization)")
                                                    .font(.caption2.monospaced())
                                                    .foregroundStyle(.secondary)
                                                Text(cached.trustDisplayLabel)
                                                    .font(.caption2.bold())
                                                    .padding(.horizontal, 6)
                                                    .padding(.vertical, 1)
                                                    .background(
                                                        Capsule().fill(
                                                            cached.isUsable ? Color.cyan.opacity(0.16) : Color.orange.opacity(0.16)
                                                        )
                                                    )
                                                    .foregroundStyle(cached.isUsable ? .cyan : .orange)
                                            }
                                            Text(cached.usabilityNote.isEmpty ? cached.localPath : cached.usabilityNote)
                                                .font(.caption2)
                                                .foregroundStyle(.secondary)
                                                .lineLimit(2)
                                        }
                                        Spacer()
                                        if cached.isUsable {
                                            Text("USABLE")
                                                .font(.caption2.bold())
                                                .foregroundStyle(.green)
                                            let isActive = vm.localBackend == .mlx && (vm.localModel == cached.modelId || vm.localModelDir == cached.localPath)
                                            Button(isActive ? "Active" : "Use") {
                                                vm.activateDownloadedModel(cached)
                                            }
                                            .controlSize(.small)
                                        } else if cached.isComplete {
                                            Button(vm.isPullingModelId == cached.modelId ? "Pinning…" : "Audit & Pin SHA-256") {
                                                vm.verifyOrPullModel(cached.modelId, allowDownload: false)
                                            }
                                            .controlSize(.small)
                                            .disabled(vm.isPullingModelId != nil)
                                        } else {
                                            Text("Incomplete")
                                                .font(.caption2.bold())
                                                .foregroundStyle(.red)
                                        }
                                    }
                                    if cached.id != hw.cachedModels.last?.id {
                                        Divider()
                                    }
                                }
                            } else {
                                Divider()
                                Text("No local MLX weights downloaded yet in ~/.cache/huggingface/hub or ~/Models.")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(6)
                    }

                    GroupBox("Download & Audit MLX Models (Safe .safetensors + .json Only · Auto SHA-256 Pin)") {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack(spacing: 8) {
                                TextField("First-party repo (e.g. google/gemma-3-4b-it, Qwen/Qwen2.5-7B-Instruct)", text: $vm.customPullModelId)
                                    .textFieldStyle(.roundedBorder)
                                Button(vm.isPullingModelId == vm.customPullModelId ? "Working…" : "Download & Pin") {
                                    vm.verifyOrPullModel(vm.customPullModelId, allowDownload: true)
                                }
                                .controlSize(.small)
                                .disabled(vm.isPullingModelId != nil || vm.customPullModelId.trimmingCharacters(in: .whitespaces).isEmpty)

                                Button("Self-Quantize (4-bit → ~/Models)") {
                                    vm.convertFirstPartyModel(vm.customPullModelId, qBits: 4)
                                }
                                .controlSize(.small)
                                .disabled(vm.isPullingModelId != nil || vm.customPullModelId.trimmingCharacters(in: .whitespaces).isEmpty)
                                .help("Quantizes a verified first-party repo locally on your Mac into ~/Models/ and pins its SHA-256 checksums.")
                            }

                            if let pullRes = vm.lastPullResult {
                                HStack(spacing: 6) {
                                    Image(systemName: pullRes.ok ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                                        .foregroundStyle(pullRes.ok ? .green : .orange)
                                    Text(pullRes.message)
                                        .font(.caption2)
                                        .foregroundStyle(pullRes.ok ? .green : .orange)
                                }
                            }

                            Divider()

                            ForEach(hw.recommendations) { rec in
                                HStack(spacing: 8) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("\(rec.modelId) (\(rec.parameterCount) · \(rec.quantization) · ~\(String(format: "%.1f", rec.estimatedMemoryGb)) GB)")
                                            .font(.caption.bold())
                                        Text(rec.rationale)
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    if rec.isReadyLocally {
                                        Button(vm.isPullingModelId == rec.modelId ? "Pinning…" : "Audit & Pin") {
                                            vm.verifyOrPullModel(rec.modelId, allowDownload: false)
                                        }
                                        .controlSize(.small)
                                        .disabled(vm.isPullingModelId != nil)
                                    } else {
                                        Button(vm.isPullingModelId == rec.modelId ? "Downloading…" : "Download & Pin") {
                                            vm.verifyOrPullModel(rec.modelId, allowDownload: true)
                                        }
                                        .controlSize(.small)
                                        .disabled(!rec.fitsInMetalBudget || vm.isPullingModelId != nil)
                                    }
                                    Button(vm.localModel == rec.modelId && vm.localBackend == .mlx ? "Active" : "Use") {
                                        vm.setLocalBackend(.mlx)
                                        vm.selectRecommendedModel(rec.modelId)
                                    }
                                    .controlSize(.small)
                                    .disabled(!rec.fitsInMetalBudget || !rec.isReadyLocally)
                                }
                                if rec.id != hw.recommendations.last?.id {
                                    Divider()
                                }
                            }
                        }
                        .padding(6)
                    }
                } else {
                    ProgressView("Profiling Apple Silicon hardware…")
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding()
                }
            }
            .padding(20)
        }
    }

    private func chooseLocalModelDirectory() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.prompt = "Select Model Folder"
        panel.message = "Choose a local directory containing verified .safetensors weights and config.json (skips Hugging Face Hub)."
        if panel.runModal() == .OK, let url = panel.url {
            vm.setLocalModelDir(url.path)
        }
    }
}
