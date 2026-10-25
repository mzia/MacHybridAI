import SwiftUI
import AppKit

@MainActor
final class HybridAppViewModel: ObservableObject {
    @Published var computeMode: ComputeModeOption = .hybrid
    @Published var cloudProvider: CloudProviderOption = .gemini
    @Published var guardianPolicy: GuardianPolicyOption = .reversibleMask

    // Provider configuration fields
    @Published var geminiModel: String = "gemini-3.8-flash"
    @Published var antigravityAgent: String = "antigravity-preview-05-2026"
    @Published var localModel: String = "gemma4:26b"
    @Published var localEndpoint: String = "http://127.0.0.1:11434/v1"
    @Published var openAIBaseURL: String = "https://api.openai.com/v1"
    @Published var openAIModel: String = "gpt-4.1"
    @Published var m365Port: String = "4141"
    @Published var m365Model: String = "gpt-5.5-think-deeper"
    @Published var m365InteractiveApproval: Bool = true
    @Published var m365AvoidThrottling: Bool = true

    // Composer & Task Execution
    @Published var promptText: String = "Rework the Meridian model for Contact: Sam Reyes (sam.reyes@meridian.io, 415-555-2671). Benchmark against comparable deals and update the IC deck."
    @Published var attachedFiles: [String] = []
    @Published var isRunning: Bool = false
    @Published var lastResult: TaskResultModel?

    // Privacy Gate live inspector
    @Published var inspectorInput: String = "Prepared for Sam Reyes (sam.reyes@meridian.io), phone (415) 555-2671, SSN 123-45-6789."
    @Published var inspectorAudit: GuardianAuditModel?
    @Published var selectedTab: Int = 0

    init() {
        runInspector()
        executeTask()
    }

    func executeTask() {
        let trimmed = promptText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        isRunning = true
        let mode = computeMode
        let provider = cloudProvider
        let policy = guardianPolicy
        let files = attachedFiles

        let result = BackendBridge.shared.runTask(
            prompt: trimmed,
            mode: mode,
            cloudProvider: provider,
            guardianPolicy: policy,
            attachedFiles: files
        )
        self.lastResult = result
        self.isRunning = false
    }

    func runInspector() {
        self.inspectorAudit = BackendBridge.shared.inspectPII(
            text: inspectorInput,
            policy: guardianPolicy
        )
    }

    func attachFileViaPanel() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = true
        if panel.runModal() == .OK {
            for url in panel.urls {
                if !attachedFiles.contains(url.path) {
                    attachedFiles.append(url.path)
                }
            }
        }
    }
}

struct MainDashboardView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 10) {
                    Image(systemName: "shield.lefthalf.filled.badge.checkmark")
                        .font(.system(size: 22, weight: .semibold))
                        .foregroundStyle(Color(red: 0.57, green: 0.86, blue: 0.89))
                    VStack(alignment: .leading, spacing: 2) {
                        Text("MacHybridAI")
                            .font(.headline)
                        Text("Perplexity-Style Hybrid Compute")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.bottom, 6)

                Picker("Section", selection: $vm.selectedTab) {
                    Label("Computer & Relay", systemImage: "laptopcomputer.and.icloud").tag(0)
                    Label("Privacy Gate (PII)", systemImage: "lock.shield").tag(1)
                    Label("AI Providers & M365", systemImage: "slider.horizontal.3").tag(2)
                }
                .pickerStyle(.radioGroup)

                Spacer()

                // Where the work runs summary card
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Circle()
                            .fill(vm.computeMode == .local ? Color.cyan : Color.green)
                            .frame(width: 8, height: 8)
                        Text(vm.computeMode.title.uppercased())
                            .font(.caption.bold())
                            .foregroundStyle(Color(red: 0.57, green: 0.86, blue: 0.89))
                    }
                    Text(vm.computeMode.subtitle)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.05)))
            }
            .padding(14)
            .frame(minWidth: 220)
        } detail: {
            Group {
                if vm.selectedTab == 0 {
                    ComputerRelayTabView(vm: vm)
                } else if vm.selectedTab == 1 {
                    PrivacyGateTabView(vm: vm)
                } else {
                    ProvidersConfigTabView(vm: vm)
                }
            }
            .frame(minWidth: 760, minHeight: 580)
        }
    }
}

struct ComputerRelayTabView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header & Mode Pill Switcher
                HStack(alignment: .center) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Run Computer tasks locally on your Mac.")
                            .font(.title2.bold())
                        Text("Keep sensitive files on your Mac. Run a task fully local, or split it between local and cloud models with Privacy Gate.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Picker("Mode", selection: $vm.computeMode) {
                        ForEach(ComputeModeOption.allCases, id: \.self) { option in
                            Text(option.title).tag(option)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 220)
                    .onChange(of: vm.computeMode) { _, _ in
                        vm.executeTask()
                    }
                }

                // Task Composer Box
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Label("Your Task", systemImage: "checklist")
                            .font(.caption.bold())
                            .foregroundStyle(.secondary)
                        Spacer()
                        if vm.computeMode == .hybrid {
                            Picker("Cloud Model", selection: $vm.cloudProvider) {
                                ForEach(CloudProviderOption.allCases, id: \.self) { provider in
                                    Text(provider.displayName).tag(provider)
                                }
                            }
                            .frame(width: 320)
                        }
                    }

                    TextEditor(text: $vm.promptText)
                        .font(.body)
                        .frame(height: 76)
                        .scrollContentBackground(.hidden)
                        .padding(8)
                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.black.opacity(0.25)))

                    if !vm.attachedFiles.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(vm.attachedFiles, id: \.self) { path in
                                    HStack(spacing: 4) {
                                        Image(systemName: "doc.text.fill")
                                        Text((path as NSString).lastPathComponent)
                                            .font(.caption)
                                        Button {
                                            vm.attachedFiles.removeAll { $0 == path }
                                        } label: {
                                            Image(systemName: "xmark.circle.fill")
                                        }
                                        .buttonStyle(.plain)
                                    }
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(Capsule().fill(Color.cyan.opacity(0.2)))
                                }
                            }
                        }
                    }

                    HStack {
                        Button {
                            vm.attachFileViaPanel()
                        } label: {
                            Label("Attach Private Mac File", systemImage: "plus.circle")
                        }

                        Spacer()

                        Button {
                            vm.executeTask()
                        } label: {
                            Label(
                                vm.computeMode == .local ? "Run Fully Local on Mac" : "Run Hybrid with Privacy Gate",
                                systemImage: "arrow.up.circle.fill"
                            )
                            .font(.headline)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(Color(red: 0.25, green: 0.68, blue: 0.75))
                    }
                }
                .padding(16)
                .background(
                    RoundedRectangle(cornerRadius: 14)
                        .fill(Color.white.opacity(0.04))
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .stroke(Color.white.opacity(0.12), lineWidth: 1)
                        )
                )

                if let result = vm.lastResult {
                    // Telemetry & Execution Receipt Row
                    HStack(alignment: .top, spacing: 16) {
                        // Execution Receipt ("Where the work ran")
                        VStack(alignment: .leading, spacing: 8) {
                            Label("Where the work ran", systemImage: "checkmark.shield.fill")
                                .font(.caption.bold())
                                .foregroundStyle(Color(red: 0.57, green: 0.86, blue: 0.89))

                            Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 6) {
                                GridRow {
                                    Text("Model").foregroundStyle(.secondary).font(.caption)
                                    Text(result.receipt.localModelUsed).font(.caption.bold())
                                }
                                GridRow {
                                    Text("Agent").foregroundStyle(.secondary).font(.caption)
                                    Text(result.receipt.localAgentLocation).font(.caption.bold())
                                }
                                GridRow {
                                    Text("Cloud models").foregroundStyle(.secondary).font(.caption)
                                    Text(result.receipt.cloudModelsUsed).font(.caption.bold())
                                }
                                GridRow {
                                    Text("Privacy Gate").foregroundStyle(.secondary).font(.caption)
                                    Text(
                                        result.receipt.piiFlaggedCount > 0
                                            ? "\(result.receipt.piiFlaggedCount) PII masked · \(result.receipt.piiRestoredCount) restored"
                                            : "0 PII flagged"
                                    )
                                    .font(.caption.bold())
                                    .foregroundStyle(result.receipt.piiFlaggedCount > 0 ? .orange : .green)
                                }
                            }
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.04)))

                        // Apple Silicon Telemetry Card
                        VStack(alignment: .leading, spacing: 8) {
                            Label("This Mac Telemetry (\(result.telemetry.chipBrand))", systemImage: "cpu")
                                .font(.caption.bold())
                                .foregroundStyle(.secondary)

                            HStack(spacing: 18) {
                                TelemetryMetricPill(label: "CPU", value: "\(result.telemetry.cpuPercent)%")
                                TelemetryMetricPill(label: "Memory", value: "\(result.telemetry.memoryPercent)%")
                                TelemetryMetricPill(label: "Metal GPU", value: "\(result.telemetry.gpuPercent)%")
                                TelemetryMetricPill(label: "Tokens", value: "\(result.telemetry.tokensProcessed)")
                            }
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.04)))
                    }

                    // Station-by-Station Relay Timeline
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Station-by-Station Execution Timeline")
                            .font(.headline)

                        ForEach(result.stations) { station in
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: iconForStation(station.stationId))
                                    .font(.system(size: 16, weight: .semibold))
                                    .foregroundStyle(colorForStation(station.locality))
                                    .frame(width: 28, height: 28)
                                    .background(Circle().fill(colorForStation(station.locality).opacity(0.15)))

                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Text(station.label.uppercased())
                                            .font(.caption.bold())
                                            .foregroundStyle(colorForStation(station.locality))
                                        Text("· \(station.durationMs) ms")
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                        Spacer()
                                        ForEach(station.badges, id: \.self) { badge in
                                            Text(badge)
                                                .font(.caption2.bold())
                                                .padding(.horizontal, 8)
                                                .padding(.vertical, 2)
                                                .background(Capsule().fill(Color.white.opacity(0.08)))
                                        }
                                    }
                                    Text(station.title)
                                        .font(.subheadline.bold())
                                    Text(station.detail)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .padding(12)
                            .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.03)))
                        }
                    }

                    // Sanitized Cloud Prompt vs Final Restored Result
                    if let cloudPrompt = result.cloudPromptSent {
                        VStack(alignment: .leading, spacing: 6) {
                            Label("What Reached the Cloud (Sanitized by Privacy Gate)", systemImage: "eye.slash.fill")
                                .font(.caption.bold())
                                .foregroundStyle(.orange)
                            Text(cloudPrompt)
                                .font(.system(.caption, design: .monospaced))
                                .padding(10)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(RoundedRectangle(cornerRadius: 8).fill(Color.orange.opacity(0.08)))
                        }
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Label("Final Output on This Mac (Real Values Restored)", systemImage: "doc.richtext")
                            .font(.caption.bold())
                            .foregroundStyle(.green)
                        Text(result.finalOutput)
                            .font(.body)
                            .textSelection(.enabled)
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.05)))
                    }
                }
            }
            .padding(24)
        }
    }

    private func iconForStation(_ id: String) -> String {
        switch id {
        case "this_mac": return "desktopcomputer"
        case "privacy_gate": return "lock.shield.fill"
        case "cloud": return "icloud.fill"
        default: return "checkmark.circle.fill"
        }
    }

    private func colorForStation(_ locality: String) -> Color {
        switch locality {
        case "local": return Color(red: 0.57, green: 0.86, blue: 0.89)
        case "shield": return .orange
        case "cloud": return .purple
        default: return .green
        }
    }
}

struct TelemetryMetricPill: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.headline.monospacedDigit())
        }
    }
}

struct PrivacyGateTabView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("On-Device Privacy Gate (PII Guardian)")
                    .font(.title2.bold())
                Text("Inspect how personal information, credentials, and financial identifiers are masked on your Mac before any cloud model is called—and automatically restored when results return.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                Picker("Guardian Policy", selection: $vm.guardianPolicy) {
                    ForEach(GuardianPolicyOption.allCases, id: \.self) { pol in
                        Text(pol.displayName).tag(pol)
                    }
                }
                .onChange(of: vm.guardianPolicy) { _, _ in
                    vm.runInspector()
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("Sample Input Containing Sensitive Data:")
                        .font(.caption.bold())
                    TextEditor(text: $vm.inspectorInput)
                        .font(.body)
                        .frame(height: 90)
                        .padding(8)
                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.black.opacity(0.25)))
                        .onChange(of: vm.inspectorInput) { _, _ in
                            vm.runInspector()
                        }
                }

                if let audit = vm.inspectorAudit {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Sanitized Text (Safe for Cloud Models)", systemImage: "shield.checkered")
                            .font(.caption.bold())
                            .foregroundStyle(.orange)
                        Text(audit.sanitizedText)
                            .font(.system(.body, design: .monospaced))
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(RoundedRectangle(cornerRadius: 8).fill(Color.orange.opacity(0.1)))
                    }

                    if let restored = audit.restoredPreview {
                        VStack(alignment: .leading, spacing: 8) {
                            Label("Restored Output on This Mac", systemImage: "arrow.uturn.backward.circle.fill")
                                .font(.caption.bold())
                                .foregroundStyle(.green)
                            Text(restored)
                                .font(.system(.body, design: .monospaced))
                                .padding(12)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(RoundedRectangle(cornerRadius: 8).fill(Color.green.opacity(0.1)))
                        }
                    }

                    Text("Flagged Entities (\(audit.piiCount))")
                        .font(.headline)

                    ForEach(audit.entities) { entity in
                        HStack {
                            Text(entity.category)
                                .font(.caption.bold())
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(Capsule().fill(Color.orange.opacity(0.2)))
                            Text(entity.maskedPreview)
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                            Image(systemName: "arrow.right")
                                .font(.caption)
                            Text(entity.replacementToken)
                                .font(.system(.caption, design: .monospaced).bold())
                                .foregroundStyle(.cyan)
                            Spacer()
                            Text("Confidence: \(Int(entity.confidence * 100))%")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        .padding(10)
                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.white.opacity(0.04)))
                    }
                }
            }
            .padding(24)
        }
    }
}

struct ProvidersConfigTabView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        Form {
            Section("Default Cloud AI — Google Gemini & Antigravity") {
                TextField("Gemini Model (Interactions API)", text: $vm.geminiModel)
                TextField("Antigravity Managed Agent ID", text: $vm.antigravityAgent)
            }

            Section("On-Device Local Model (This Mac — Apple Silicon Metal)") {
                TextField("Local Model Identifier (LiteRT / Ollama)", text: $vm.localModel)
                TextField("Local OpenAI-Compatible Endpoint", text: $vm.localEndpoint)
            }

            Section("Microsoft 365 Copilot Proxy (cramt/m365-copilot-proxy)") {
                TextField("Proxy Loopback Port", text: $vm.m365Port)
                TextField("M365 Tone / Model (Recommended: gpt-5.5-think-deeper)", text: $vm.m365Model)
                Toggle("Interactive Browser SSO/MFA Approval (M365_ENABLE_INTERACTIVE_APPROVAL=1)", isOn: $vm.m365InteractiveApproval)
                Toggle("Avoid PerUserThrottled Reserve Guard (M365_AVOID_THROTTLING=1)", isOn: $vm.m365AvoidThrottling)
            }

            Section("Custom OpenAI Extension Method") {
                TextField("OpenAI-Compatible Base URL", text: $vm.openAIBaseURL)
                TextField("OpenAI-Compatible Model Name", text: $vm.openAIModel)
            }
        }
        .formStyle(.grouped)
        .padding(16)
    }
}

@main
struct MacHybridAIApp: App {
    @StateObject private var viewModel = HybridAppViewModel()

    var body: some Scene {
        WindowGroup("MacHybridAI — Hybrid Compute & Privacy Gate") {
            MainDashboardView(vm: viewModel)
                .preferredColorScheme(.dark)
        }
        .windowStyle(.titleBar)

        MenuBarExtra("MacHybridAI", systemImage: "shield.lefthalf.filled.badge.checkmark") {
            VStack(alignment: .leading, spacing: 8) {
                Text("MacHybridAI · \(viewModel.computeMode.title)")
                    .font(.headline)
                Divider()
                Button("Mode: Fully Local (On-Device Only)") {
                    viewModel.computeMode = .local
                    viewModel.executeTask()
                }
                Button("Mode: Hybrid (Privacy Gate + Cloud)") {
                    viewModel.computeMode = .hybrid
                    viewModel.executeTask()
                }
                Divider()
                Text("Cloud: \(viewModel.cloudProvider.displayName)")
                    .font(.caption)
                Divider()
                Button("Quit MacHybridAI") {
                    NSApplication.shared.terminate(nil)
                }
            }
            .padding(6)
        }
    }
}
