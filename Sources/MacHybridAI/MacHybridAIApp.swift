import SwiftUI
import AppKit

/// Renders bespoke MacHybridAI icons (Dock App Icon & Menu Bar Split-Chip Icon)
/// so the app and menu bar look unmistakably like a Hybrid Compute AI Studio
/// (Apple Silicon [M] Chip + Privacy Gate Lock + Cloud [AI] Node).
public enum HybridBrandIconGenerator {
    @MainActor
    public static func makeDockIcon(size: CGFloat = 512) -> NSImage {
        let img = NSImage(size: NSSize(width: size, height: size))
        img.lockFocus()
        guard let ctx = NSGraphicsContext.current?.cgContext else {
            img.unlockFocus()
            return img
        }

        let rect = CGRect(x: 0, y: 0, width: size, height: size)
        let card = rect.insetBy(dx: size * 0.06, dy: size * 0.06)
        let radius = size * 0.22
        let path = CGPath(roundedRect: card, cornerWidth: radius, cornerHeight: radius, transform: nil)

        ctx.saveGState()
        ctx.addPath(path)
        ctx.clip()

        let cs = CGColorSpaceCreateDeviceRGB()
        let colors = [
            CGColor(red: 0.05, green: 0.09, blue: 0.18, alpha: 1.0),
            CGColor(red: 0.09, green: 0.15, blue: 0.28, alpha: 1.0),
            CGColor(red: 0.16, green: 0.10, blue: 0.30, alpha: 1.0),
        ] as CFArray
        if let grad = CGGradient(colorsSpace: cs, colors: colors, locations: [0.0, 0.55, 1.0]) {
            ctx.drawLinearGradient(
                grad,
                start: CGPoint(x: card.minX, y: card.maxY),
                end: CGPoint(x: card.maxX, y: card.minY),
                options: []
            )
        }
        ctx.restoreGState()

        ctx.addPath(path)
        ctx.setStrokeColor(CGColor(red: 0.30, green: 0.85, blue: 0.96, alpha: 0.7))
        ctx.setLineWidth(size * 0.016)
        ctx.strokePath()

        let midY = size * 0.55
        let chipSize = size * 0.25
        let chipRect = CGRect(x: size * 0.28 - chipSize / 2, y: midY - chipSize / 2, width: chipSize, height: chipSize)
        let chipPath = CGPath(roundedRect: chipRect, cornerWidth: chipSize * 0.18, cornerHeight: chipSize * 0.18, transform: nil)
        ctx.addPath(chipPath)
        ctx.setFillColor(CGColor(red: 0.06, green: 0.28, blue: 0.38, alpha: 1.0))
        ctx.fillPath()
        ctx.addPath(chipPath)
        ctx.setStrokeColor(CGColor(red: 0.22, green: 0.90, blue: 0.98, alpha: 1.0))
        ctx.setLineWidth(size * 0.018)
        ctx.strokePath()

        let cloudR = size * 0.13
        let cloudRect = CGRect(x: size * 0.72 - cloudR, y: midY - cloudR, width: cloudR * 2, height: cloudR * 2)
        ctx.setFillColor(CGColor(red: 0.24, green: 0.12, blue: 0.42, alpha: 1.0))
        ctx.fillEllipse(in: cloudRect)
        ctx.setStrokeColor(CGColor(red: 0.76, green: 0.48, blue: 1.0, alpha: 1.0))
        ctx.setLineWidth(size * 0.018)
        ctx.strokeEllipse(in: cloudRect)

        // Bridge + center Privacy Gate node
        ctx.setStrokeColor(CGColor(red: 0.98, green: 0.78, blue: 0.28, alpha: 1.0))
        ctx.setLineWidth(size * 0.02)
        ctx.move(to: CGPoint(x: chipRect.maxX, y: midY))
        ctx.addLine(to: CGPoint(x: cloudRect.minX, y: midY))
        ctx.strokePath()

        let gateR = size * 0.07
        let gateRect = CGRect(x: size * 0.5 - gateR, y: midY - gateR, width: gateR * 2, height: gateR * 2)
        ctx.setFillColor(CGColor(red: 0.10, green: 0.36, blue: 0.26, alpha: 1.0))
        ctx.fillEllipse(in: gateRect)
        ctx.setStrokeColor(CGColor(red: 0.30, green: 0.95, blue: 0.68, alpha: 1.0))
        ctx.setLineWidth(size * 0.016)
        ctx.strokeEllipse(in: gateRect)

        img.unlockFocus()
        return img
    }

    /// Creates a crisp 22x18 Menu Bar template image depicting a Split Chip [M] <-> Cloud [AI]
    /// so the menu bar icon never resembles a shield or posture app.
    @MainActor
    public static func makeMenuBarIcon() -> NSImage {
        let size = NSSize(width: 24, height: 18)
        let img = NSImage(size: size)
        img.lockFocus()
        guard let ctx = NSGraphicsContext.current?.cgContext else {
            img.unlockFocus()
            return img
        }

        ctx.setStrokeColor(NSColor.labelColor.cgColor)
        ctx.setFillColor(NSColor.labelColor.cgColor)
        ctx.setLineWidth(1.5)

        // Left: Silicon chip square
        let chipRect = CGRect(x: 1.5, y: 3.5, width: 9.0, height: 11.0)
        let chipPath = CGPath(roundedRect: chipRect, cornerWidth: 2.0, cornerHeight: 2.0, transform: nil)
        ctx.addPath(chipPath)
        ctx.strokePath()

        // Chip pins on left
        for py in [5.5, 9.0, 12.5] {
            ctx.move(to: CGPoint(x: 0.0, y: py))
            ctx.addLine(to: CGPoint(x: 1.5, y: py))
        }
        ctx.strokePath()

        // Center neural bridge line
        ctx.move(to: CGPoint(x: 10.5, y: 9.0))
        ctx.addLine(to: CGPoint(x: 14.0, y: 9.0))
        ctx.strokePath()

        // Right: Cloud AI node circle
        let cloudRect = CGRect(x: 14.0, y: 4.0, width: 9.0, height: 10.0)
        ctx.strokeEllipse(in: cloudRect)

        // Inner dot in chip & cloud
        ctx.fillEllipse(in: CGRect(x: 4.7, y: 7.7, width: 2.6, height: 2.6))
        ctx.fillEllipse(in: CGRect(x: 17.2, y: 7.7, width: 2.6, height: 2.6))

        img.unlockFocus()
        img.isTemplate = true
        return img
    }
}

/// Custom SwiftUI Brand Emblem showing the Split-Compute Silicon Chip + Privacy Gate + Cloud AI.
struct HybridBrandEmblemView: View {
    var body: some View {
        HStack(spacing: 4) {
            ZStack {
                RoundedRectangle(cornerRadius: 6)
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(red: 0.08, green: 0.25, blue: 0.36),
                                Color(red: 0.22, green: 0.12, blue: 0.38),
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 36, height: 32)
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(Color.cyan.opacity(0.6), lineWidth: 1)
                    )

                HStack(spacing: 3) {
                    Image(systemName: "memorychip.fill")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.cyan)
                    Image(systemName: "arrow.left.and.right")
                        .font(.system(size: 8, weight: .black))
                        .foregroundStyle(.yellow)
                    Image(systemName: "sparkles")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.purple)
                }
            }
        }
    }
}

@MainActor
final class HybridAppViewModel: ObservableObject {
    @Published var computeMode: ComputeModeOption = .hybrid
    @Published var cloudProvider: CloudProviderOption = .gemini
    @Published var guardianPolicy: GuardianPolicyOption = .reversibleMask

    // Prompt History Storage (Local Mac vs iCloud Drive) & Auto-Delete Policy
    @Published var historyStorage: HistoryStorageOption = .localMac
    @Published var historyRetention: HistoryRetentionOption = .days30
    @Published var conversations: [ChatConversationModel] = []
    @Published var activeConversationId: String = ""
    @Published var historySearchQuery: String = ""

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

    // Chat Composer & Task Execution
    @Published var promptText: String = "Rework the Meridian model for Contact: Sam Reyes (sam.reyes@meridian.io, 415-555-2671). Benchmark against comparable deals and update the IC deck."
    @Published var attachedFiles: [String] = []
    @Published var isRunning: Bool = false
    @Published var lastResult: TaskResultModel?
    @Published var composerLiveAudit: GuardianAuditModel?

    // Privacy Gate live inspector
    @Published var inspectorInput: String = "Prepared for Sam Reyes (sam.reyes@meridian.io), phone (415) 555-2671, SSN 123-45-6789."
    @Published var inspectorAudit: GuardianAuditModel?
    @Published var selectedTab: Int = 0
    @Published var hardwareProfile: MacHardwareProfileModel?

    private let historyStore = PromptHistoryStore()

    init() {
        NSApplication.shared.applicationIconImage = HybridBrandIconGenerator.makeDockIcon()
        loadSavedHistory()
        runInspector()
        updateComposerLiveAudit()
        // Start the persistent Python daemon eagerly so the first chat send has no cold-start delay.
        if let backendDir = BackendBridge.shared.resolveBackendDirectory() {
            let pythonCandidates = ["/opt/homebrew/bin/python3", "/usr/bin/python3"]
            let py = pythonCandidates.first { FileManager.default.fileExists(atPath: $0) } ?? "/usr/bin/python3"
            DaemonManager.shared.ensureRunning(backendDir: backendDir, pythonPath: py)
        }
        refreshHardwareProfile()
        if conversations.isEmpty {
            startNewChat()
            sendChatMessage()
        }
    }

    func refreshHardwareProfile() {
        Task.detached(priority: .userInitiated) {
            let profile = BackendBridge.shared.fetchHardwareProfile()
            await MainActor.run {
                self.hardwareProfile = profile
                if self.localModel == "gemma4:26b" || self.localModel.isEmpty {
                    self.localModel = profile.selectedLocalModel
                }
            }
        }
    }

    func selectRecommendedModel(_ modelId: String) {
        self.localModel = modelId
        Task.detached(priority: .utility) {
            BackendBridge.shared.updateBackendConfig(body: ["local_model": modelId])
        }
    }

    var activeConversation: ChatConversationModel? {
        conversations.first(where: { $0.id == activeConversationId }) ?? conversations.first
    }

    var filteredConversations: [ChatConversationModel] {
        let q = historySearchQuery.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !q.isEmpty else { return conversations }
        return conversations.filter { conv in
            conv.title.lowercased().contains(q) ||
            conv.messages.contains(where: { $0.content.lowercased().contains(q) })
        }
    }

    var activeHistoryFilePath: String {
        historyStore.fileURL(for: historyStorage).path
    }

    func loadSavedHistory() {
        let loaded = historyStore.loadConversations(from: historyStorage)
        self.conversations = loaded
        if let first = loaded.first, activeConversationId.isEmpty {
            activeConversationId = first.id
        }
    }

    func startNewChat() {
        let now = Date()
        let newChat = ChatConversationModel(
            title: "New Hybrid Chat",
            createdAt: now,
            updatedAt: now,
            storageLocation: historyStorage,
            retentionPolicy: historyRetention,
            expiresAt: historyRetention.computeExpiryDate(from: now),
            messages: []
        )
        conversations.insert(newChat, at: 0)
        activeConversationId = newChat.id
        historyStore.saveConversations(conversations, to: historyStorage)
    }

    func selectConversation(_ id: String) {
        activeConversationId = id
        selectedTab = 0
    }

    func deleteConversation(_ id: String) {
        conversations.removeAll { $0.id == id }
        if activeConversationId == id {
            activeConversationId = conversations.first?.id ?? ""
        }
        historyStore.saveConversations(conversations, to: historyStorage)
        _ = BackendBridge.shared.invokePythonJSON(
            method: "POST",
            path: "/v1/history",
            body: ["action": "delete_session", "session_id": id]
        )
    }

    func clearAllHistory() {
        conversations.removeAll()
        activeConversationId = ""
        historyStore.saveConversations([], to: historyStorage)
        _ = BackendBridge.shared.invokePythonJSON(
            method: "POST",
            path: "/v1/history",
            body: ["action": "clear_all"]
        )
        startNewChat()
    }

    func pruneExpiredHistoryNow() {
        conversations = historyStore.applyRetentionPolicy(
            historyRetention,
            conversations: conversations,
            location: historyStorage
        )
        if !conversations.contains(where: { $0.id == activeConversationId }) {
            activeConversationId = conversations.first?.id ?? ""
        }
        _ = BackendBridge.shared.invokePythonJSON(
            method: "POST",
            path: "/v1/history",
            body: ["action": "prune_expired"]
        )
    }

    func updateHistorySettings() {
        conversations = historyStore.applyRetentionPolicy(
            historyRetention,
            conversations: conversations,
            location: historyStorage
        )
        _ = BackendBridge.shared.invokePythonJSON(
            method: "POST",
            path: "/v1/history",
            body: [
                "action": "configure",
                "storage_location": historyStorage.rawValue,
                "retention_policy": historyRetention.rawValue,
            ]
        )
    }

    func updateComposerLiveAudit() {
        composerLiveAudit = BackendBridge.shared.inspectPII(
            text: promptText,
            policy: guardianPolicy
        )
    }

    func sendChatMessage() {
        let trimmed = promptText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        isRunning = true

        if conversations.isEmpty || !conversations.contains(where: { $0.id == activeConversationId }) {
            startNewChat()
        }

        let currentSessionId = activeConversationId
        let mode = computeMode
        let provider = cloudProvider
        let policy = guardianPolicy
        let files = attachedFiles
        let now = Date()

        // Add user message immediately so the UI shows it while waiting
        let userMsg = ChatMessageModel(
            role: "user",
            content: trimmed,
            createdAt: now,
            computeMode: mode.rawValue,
            cloudProvider: provider.rawValue,
            sanitizedCloudPrompt: nil,
            piiMaskedCount: 0,
            piiRestoredCount: 0,
            stations: [],
            receipt: nil,
            telemetry: nil,
            cloudZeroRetention: true
        )

        // Streaming placeholder — content fills in token by token
        let streamingId = UUID().uuidString
        let streamingMsg = ChatMessageModel(
            id: streamingId,
            role: "assistant",
            content: "",
            createdAt: now,
            computeMode: mode.rawValue,
            cloudProvider: provider.rawValue,
            sanitizedCloudPrompt: nil,
            piiMaskedCount: 0,
            piiRestoredCount: 0,
            stations: [],
            receipt: nil,
            telemetry: nil,
            cloudZeroRetention: true,
            isStreaming: true
        )

        if let idx = conversations.firstIndex(where: { $0.id == currentSessionId }) {
            if conversations[idx].title == "New Hybrid Chat" {
                let firstLine = trimmed.components(separatedBy: .newlines).first ?? trimmed
                conversations[idx].title = String(firstLine.prefix(46))
            }
            conversations[idx].messages.append(userMsg)
            conversations[idx].messages.append(streamingMsg)
        }
        promptText = ""
        attachedFiles.removeAll()
        updateComposerLiveAudit()

        // Stream tokens on a background task, update the placeholder bubble in real time
        Task.detached(priority: .userInitiated) {
            BackendBridge.shared.streamTask(
                prompt: trimmed,
                mode: mode,
                cloudProvider: provider,
                attachedFiles: files,
                sessionId: currentSessionId,
                onToken: { token in
                    Task { @MainActor in
                        guard let convIdx = self.conversations.firstIndex(where: { $0.id == currentSessionId }),
                              let msgIdx = self.conversations[convIdx].messages.firstIndex(where: { $0.id == streamingId })
                        else { return }
                        self.conversations[convIdx].messages[msgIdx].content += token
                    }
                },
                onReceipt: { receiptPayload in
                    let decodedReceipt: ExecutionReceiptModel? = {
                        guard let recDict = receiptPayload["receipt"],
                              let recData = try? JSONSerialization.data(withJSONObject: recDict) else { return nil }
                        return try? JSONDecoder().decode(ExecutionReceiptModel.self, from: recData)
                    }()
                    let decodedStations: [StationStepModel] = {
                        guard let stList = receiptPayload["stations"],
                              let stData = try? JSONSerialization.data(withJSONObject: stList),
                              let list = try? JSONDecoder().decode([StationStepModel].self, from: stData) else { return [] }
                        return list
                    }()
                    let decodedTelemetry: TelemetryModel? = {
                        guard let telDict = receiptPayload["telemetry"],
                              let telData = try? JSONSerialization.data(withJSONObject: telDict) else { return nil }
                        return try? JSONDecoder().decode(TelemetryModel.self, from: telData)
                    }()
                    let cloudSent = receiptPayload["cloud_prompt_sent"] as? String

                    Task { @MainActor in
                        if let convIdx = self.conversations.firstIndex(where: { $0.id == currentSessionId }),
                           let msgIdx = self.conversations[convIdx].messages.firstIndex(where: { $0.id == streamingId }) {
                            self.conversations[convIdx].messages[msgIdx].isStreaming = false
                            if let decodedReceipt {
                                self.conversations[convIdx].messages[msgIdx].receipt = decodedReceipt
                            }
                            if !decodedStations.isEmpty {
                                self.conversations[convIdx].messages[msgIdx].stations = decodedStations
                            }
                            if let decodedTelemetry {
                                self.conversations[convIdx].messages[msgIdx].telemetry = decodedTelemetry
                            }
                            if let cloudSent {
                                self.conversations[convIdx].messages[msgIdx].sanitizedCloudPrompt = cloudSent
                            }
                        }
                        self.isRunning = false
                        self.historyStore.saveConversations(self.conversations, to: self.historyStorage)
                    }
                }
            )

            // Fallback: if streaming returned nothing (daemon not available), use blocking path
            await MainActor.run {
                guard let convIdx = self.conversations.firstIndex(where: { $0.id == currentSessionId }),
                      let msgIdx = self.conversations[convIdx].messages.firstIndex(where: { $0.id == streamingId }),
                      self.conversations[convIdx].messages[msgIdx].content.isEmpty
                else { return }

                // content is empty — streaming failed, fall back to runTask
                Task.detached(priority: .userInitiated) {
                    let result = BackendBridge.shared.runTask(
                        prompt: trimmed,
                        mode: mode,
                        cloudProvider: provider,
                        guardianPolicy: policy,
                        attachedFiles: files,
                        sessionId: currentSessionId
                    )
                    await MainActor.run {
                        self.lastResult = result
                        if let convIdx = self.conversations.firstIndex(where: { $0.id == currentSessionId }),
                           let msgIdx = self.conversations[convIdx].messages.firstIndex(where: { $0.id == streamingId }) {
                            self.conversations[convIdx].messages[msgIdx].content = result.finalOutput
                            self.conversations[convIdx].messages[msgIdx].isStreaming = false
                            self.conversations[convIdx].messages[msgIdx].stations = result.stations
                            self.conversations[convIdx].messages[msgIdx].receipt = result.receipt
                            self.conversations[convIdx].messages[msgIdx].telemetry = result.telemetry
                        }
                        self.isRunning = false
                        self.historyStore.saveConversations(self.conversations, to: self.historyStorage)
                    }
                }
            }
        }
    }
    func executeTask() {
        if promptText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
           let lastPrompt = activeConversation?.messages.last(where: { $0.role == "user" })?.content {
            promptText = lastPrompt
        }
        sendChatMessage()
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

// MARK: - Daemon status chip

/// Small inline status chip shown in the sidebar footer.
struct DaemonStatusView: View {
    @ObservedObject private var daemon = DaemonManager.shared

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(statusColor)
                .frame(width: 6, height: 6)
            Text(statusLabel)
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(statusColor)
        }
    }

    private var statusColor: Color {
        switch daemon.state {
        case .running: return .cyan
        case .starting: return .yellow
        case .failed: return .red
        case .notStarted: return .secondary
        }
    }

    private var statusLabel: String {
        switch daemon.state {
        case .running(let port): return "Engine: ready (:\(port))"
        case .starting: return "Engine: starting…"
        case .failed(let msg): return "Engine: \(msg.prefix(28))"
        case .notStarted: return "Engine: not started"
        }
    }
}

struct MainDashboardView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 12) {
                // Distinct MacHybridAI Split-Compute Brand Header
                HStack(spacing: 10) {
                    HybridBrandEmblemView()
                    VStack(alignment: .leading, spacing: 1) {
                        Text("MacHybridAI")
                            .font(.headline.bold())
                        Text("Local Chip + Privacy Gate + Cloud")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.bottom, 2)

                Button {
                    vm.startNewChat()
                    vm.selectedTab = 0
                } label: {
                    Label("New Hybrid Chat", systemImage: "plus.bubble.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Color(red: 0.18, green: 0.62, blue: 0.74))

                Picker("View", selection: $vm.selectedTab) {
                    Label("Hybrid Chat", systemImage: "bubble.left.and.text.bubble.right.fill").tag(0)
                    Label("History & iCloud Sync", systemImage: "clock.arrow.circlepath").tag(1)
                    Label("Privacy Gate (PII)", systemImage: "key.viewfinder").tag(2)
                    Label("AI Providers & M365", systemImage: "memorychip").tag(3)
                }
                .pickerStyle(.radioGroup)

                Divider()

                // Saved Prompt History Sidebar List
                HStack {
                    Label("Saved Chats (\(vm.conversations.count))", systemImage: vm.historyStorage.iconName)
                        .font(.caption.bold())
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(vm.historyRetention.shortBadge)
                        .font(.system(size: 10, weight: .semibold))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(Color.cyan.opacity(0.18)))
                }

                ScrollView {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(vm.filteredConversations) { conv in
                            HStack(spacing: 6) {
                                Button {
                                    vm.selectConversation(conv.id)
                                } label: {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(conv.title)
                                            .font(.caption.bold())
                                            .lineLimit(1)
                                            .foregroundStyle(.primary)
                                        HStack(spacing: 4) {
                                            Image(systemName: conv.storageLocation.iconName)
                                                .font(.system(size: 9))
                                            Text(conv.expirationSummary)
                                                .font(.system(size: 9))
                                        }
                                        .foregroundStyle(.secondary)
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                }
                                .buttonStyle(.plain)

                                Button {
                                    vm.deleteConversation(conv.id)
                                } label: {
                                    Image(systemName: "trash")
                                        .font(.system(size: 10))
                                        .foregroundStyle(.secondary)
                                }
                                .buttonStyle(.plain)
                                .help("Delete this conversation from \(conv.storageLocation.title)")
                            }
                            .padding(8)
                            .background(
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(
                                        conv.id == vm.activeConversationId
                                            ? Color.cyan.opacity(0.18)
                                            : Color.white.opacity(0.03)
                                    )
                            )
                        }
                    }
                }

                Spacer(minLength: 4)

                // Quick History Storage & Auto-Delete Controls Card
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Image(systemName: "externaldrive.badge.icloud")
                            .foregroundStyle(.cyan)
                        Text("History Storage & Auto-Delete")
                            .font(.caption2.bold())
                    }

                    Picker("Save To", selection: $vm.historyStorage) {
                        ForEach(HistoryStorageOption.allCases, id: \.self) { opt in
                            Text(opt.title).tag(opt)
                        }
                    }
                    .controlSize(.small)
                    .onChange(of: vm.historyStorage) { _, _ in
                        vm.updateHistorySettings()
                    }

                    Picker("Retention", selection: $vm.historyRetention) {
                        ForEach(HistoryRetentionOption.allCases, id: \.self) { ret in
                            Text(ret.displayName).tag(ret)
                        }
                    }
                    .controlSize(.small)
                    .onChange(of: vm.historyRetention) { _, _ in
                        vm.updateHistorySettings()
                    }

                    HStack(spacing: 4) {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 6, height: 6)
                        Text("Cloud AI History: ZERO (store=false)")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(.green)
                    }

                    // Daemon status indicator
                    DaemonStatusView()
                }
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.05)))
            }
            .padding(12)
            .frame(minWidth: 255)
        } detail: {
            Group {
                if vm.selectedTab == 0 {
                    HybridChatTabView(vm: vm)
                } else if vm.selectedTab == 1 {
                    PromptHistoryAndICloudTabView(vm: vm)
                } else if vm.selectedTab == 2 {
                    PrivacyGateTabView(vm: vm)
                } else {
                    ProvidersConfigTabView(vm: vm)
                }
            }
            .frame(minWidth: 780, minHeight: 620)
        }
    }
}

struct HybridChatTabView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        VStack(spacing: 0) {
            // Top Chat Header Bar
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(vm.activeConversation?.title ?? "Hybrid Compute Chat")
                        .font(.headline.bold())
                    HStack(spacing: 8) {
                        Label(
                            "Saved to: \(vm.historyStorage.title)",
                            systemImage: vm.historyStorage.iconName
                        )
                        .font(.caption2)
                        .foregroundStyle(.cyan)

                        Text("·")
                            .foregroundStyle(.secondary)

                        Text(vm.historyRetention.displayName)
                            .font(.caption2)
                            .foregroundStyle(.secondary)

                        Text("·")
                            .foregroundStyle(.secondary)

                        Label("Nothing saved in Cloud AI history", systemImage: "nosign")
                            .font(.caption2.bold())
                            .foregroundStyle(.green)
                    }
                }

                Spacer()

                if vm.computeMode == .hybrid {
                    Picker("Cloud", selection: $vm.cloudProvider) {
                        ForEach(CloudProviderOption.allCases, id: \.self) { provider in
                            Text(provider.displayName).tag(provider)
                        }
                    }
                    .frame(width: 270)
                }

                Picker("Mode", selection: $vm.computeMode) {
                    ForEach(ComputeModeOption.allCases, id: \.self) { option in
                        Text(option.title).tag(option)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 190)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .background(Color.white.opacity(0.03))

            Divider()

            // Multi-Turn Chat Stream
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let conv = vm.activeConversation, !conv.messages.isEmpty {
                        ForEach(conv.messages) { msg in
                            ChatBubbleRowView(message: msg)
                        }
                    } else {
                        VStack(spacing: 10) {
                            HybridBrandEmblemView()
                            Text("Start a Hybrid or Local Chat")
                                .font(.title3.bold())
                            Text("Your prompts can be saved locally on your Mac or in iCloud Drive with your chosen auto-delete schedule. Cloud AI calls always run with store=false so nothing remains in any Cloud AI provider's history.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                                .frame(maxWidth: 480)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 60)
                    }
                }
                .padding(20)
            }

            Divider()

            // Bottom Chat Composer Bar
            VStack(alignment: .leading, spacing: 8) {
                // Live Privacy Gate & Storage Bar
                HStack(spacing: 10) {
                    if vm.computeMode == .local {
                        Label("Fully Local Mode: 100% on Apple Silicon Metal", systemImage: "memorychip.fill")
                            .font(.caption2.bold())
                            .foregroundStyle(.cyan)
                    } else if let liveAudit = vm.composerLiveAudit, liveAudit.piiFlagged {
                        Label(
                            "Privacy Gate Ready: \(liveAudit.piiCount) sensitive item(s) (\(liveAudit.categories.joined(separator: ", "))) will be masked before cloud call",
                            systemImage: "key.viewfinder"
                        )
                        .font(.caption2.bold())
                        .foregroundStyle(.orange)
                    } else {
                        Label("Privacy Gate Active: 0 PII detected in draft", systemImage: "checkmark.circle.fill")
                            .font(.caption2)
                            .foregroundStyle(.green)
                    }

                    Spacer()

                    Text("Cloud AI Retention: OFF (Stateless)")
                        .font(.caption2.bold())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(Color.green.opacity(0.15)))
                        .foregroundStyle(.green)
                }

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

                HStack(alignment: .bottom, spacing: 10) {
                    Button {
                        vm.attachFileViaPanel()
                    } label: {
                        Image(systemName: "paperclip.circle.fill")
                            .font(.system(size: 22))
                            .foregroundStyle(.cyan)
                    }
                    .buttonStyle(.plain)
                    .help("Attach local Mac file (processed on-device)")

                    TextEditor(text: $vm.promptText)
                        .font(.body)
                        .frame(height: 58)
                        .scrollContentBackground(.hidden)
                        .padding(8)
                        .background(RoundedRectangle(cornerRadius: 10).fill(Color.black.opacity(0.28)))
                        .onChange(of: vm.promptText) { _, _ in
                            vm.updateComposerLiveAudit()
                        }

                    Button {
                        vm.sendChatMessage()
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "paperplane.fill")
                            Text(vm.computeMode == .local ? "Send Local" : "Send Hybrid")
                                .font(.subheadline.bold())
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color(red: 0.20, green: 0.65, blue: 0.75))
                }
            }
            .padding(16)
            .background(Color.white.opacity(0.03))
        }
    }
}

// MARK: - Streaming cursor

/// Blinking "▋" cursor shown in assistant bubbles while tokens are streaming in.
/// Uses a TimelineView so no @State macro is required in the SPM build target.
struct StreamingCursorView: View {
    var body: some View {
        TimelineView(.animation(minimumInterval: 0.5)) { context in
            let phase = context.date.timeIntervalSinceReferenceDate
            let visible = Int(phase / 0.5) % 2 == 0
            Text("▋")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(.cyan.opacity(0.9))
                .opacity(visible ? 1.0 : 0.0)
        }
    }
}

struct ChatBubbleRowView: View {
    let message: ChatMessageModel

    var body: some View {
        if message.role == "user" {
            HStack {
                Spacer(minLength: 80)
                VStack(alignment: .trailing, spacing: 6) {
                    HStack(spacing: 6) {
                        if message.piiMaskedCount > 0 {
                            Text("\(message.piiMaskedCount) PII Masked by Privacy Gate")
                                .font(.system(size: 10, weight: .bold))
                                .padding(.horizontal, 7)
                                .padding(.vertical, 2)
                                .background(Capsule().fill(Color.orange.opacity(0.25)))
                                .foregroundStyle(.orange)
                        }
                        Text("You · \(message.computeMode.uppercased())")
                            .font(.caption2.bold())
                            .foregroundStyle(.secondary)
                    }

                    Text(message.content)
                        .font(.body)
                        .textSelection(.enabled)
                        .padding(12)
                        .background(
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Color(red: 0.12, green: 0.32, blue: 0.42))
                        )
                }
            }
        } else {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    HybridBrandEmblemView()
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text("MacHybridAI Assistant")
                                .font(.caption.bold())
                            if let receipt = message.receipt {
                                Text("· \(receipt.localModelUsed)")
                                    .font(.caption2)
                                    .foregroundStyle(.cyan)
                                if !receipt.nothingLeftMac {
                                    Text("+ \(receipt.cloudModelsUsed)")
                                        .font(.caption2)
                                        .foregroundStyle(.purple)
                                }
                            }
                        }
                        HStack(spacing: 6) {
                            Text("Cloud AI History Retained: None (store=false)")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundStyle(.green)
                            if message.piiRestoredCount > 0 {
                                Text("· Restored \(message.piiRestoredCount) real value(s) on this Mac")
                                    .font(.system(size: 10, weight: .semibold))
                                    .foregroundStyle(.orange)
                            }
                            if let tel = message.telemetry {
                                Text("· \(tel.chipBrand) · CPU \(tel.cpuPercent)% · GPU \(tel.gpuPercent)% · RAM \(tel.memoryPercent)% (\(tel.unifiedMemoryGb) GB)")
                                    .font(.system(size: 10, weight: .medium))
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                    Spacer()
                }

                Text(message.content.isEmpty && message.isStreaming ? " " : message.content)
                    .font(.body)
                    .textSelection(.enabled)
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(Color.white.opacity(0.05))
                    )
                    .overlay(alignment: .bottomTrailing) {
                        if message.isStreaming {
                            StreamingCursorView()
                                .padding(8)
                        }
                    }

                // Expandable 4-Station Relay & Sanitized Cloud Prompt Inspector
                if !message.stations.isEmpty || message.sanitizedCloudPrompt != nil {
                    DisclosureGroup("View 4-Station Hybrid Relay & Sanitized Cloud Prompt") {
                        VStack(alignment: .leading, spacing: 8) {
                            if let sanitized = message.sanitizedCloudPrompt {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("What Reached the Cloud (Sanitized by Privacy Gate · Not Saved by Cloud AI):")
                                        .font(.caption2.bold())
                                        .foregroundStyle(.orange)
                                    Text(sanitized)
                                        .font(.system(.caption, design: .monospaced))
                                        .textSelection(.enabled)
                                        .padding(8)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.orange.opacity(0.1)))
                                }
                            }

                            ForEach(message.stations) { station in
                                HStack(alignment: .top, spacing: 8) {
                                    Circle()
                                        .fill(station.locality == "local" ? Color.cyan : (station.locality == "shield" ? Color.orange : Color.purple))
                                        .frame(width: 8, height: 8)
                                        .padding(.top, 4)
                                    VStack(alignment: .leading, spacing: 2) {
                                        HStack {
                                            Text("\(station.label): \(station.title)")
                                                .font(.caption.bold())
                                            Spacer()
                                            Text("\(station.durationMs) ms")
                                                .font(.caption2)
                                                .foregroundStyle(.secondary)
                                        }
                                        Text(station.detail)
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                .padding(6)
                                .background(RoundedRectangle(cornerRadius: 6).fill(Color.white.opacity(0.03)))
                            }
                        }
                        .padding(.top, 6)
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 4)
                }
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color.white.opacity(0.02))
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(Color.white.opacity(0.08), lineWidth: 1)
                    )
            )
        }
    }
}

struct PromptHistoryAndICloudTabView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Prompt History, iCloud Drive Sync & Auto-Delete")
                    .font(.title2.bold())
                Text("Save your prompt and chat history locally on this Mac or in your personal iCloud Drive, with automatic expiration or permanent retention. Cloud AI providers never retain your prompts.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                // Storage & Retention Configuration Card
                VStack(alignment: .leading, spacing: 14) {
                    Picker("Save Prompt History To:", selection: $vm.historyStorage) {
                        ForEach(HistoryStorageOption.allCases, id: \.self) { loc in
                            Text("\(loc.title) (\(loc.subtitle))").tag(loc)
                        }
                    }
                    .pickerStyle(.radioGroup)
                    .onChange(of: vm.historyStorage) { _, _ in
                        vm.updateHistorySettings()
                    }

                    Divider()

                    Picker("Auto-Delete Schedule:", selection: $vm.historyRetention) {
                        ForEach(HistoryRetentionOption.allCases, id: \.self) { policy in
                            Text(policy.displayName).tag(policy)
                        }
                    }
                    .onChange(of: vm.historyRetention) { _, _ in
                        vm.updateHistorySettings()
                    }

                    HStack {
                        Text("Active History File:")
                            .font(.caption.bold())
                            .foregroundStyle(.secondary)
                        Text(vm.activeHistoryFilePath)
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                        Spacer()
                        Button("Purge Expired Now") {
                            vm.pruneExpiredHistoryNow()
                        }
                        Button("Clear All Saved Prompts", role: .destructive) {
                            vm.clearAllHistory()
                        }
                    }
                }
                .padding(16)
                .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.04)))

                // Zero Cloud AI History Guarantee Card
                VStack(alignment: .leading, spacing: 8) {
                    Label("Zero Cloud AI History Guarantee (Stateless Cloud Calls)", systemImage: "checkmark.seal.fill")
                        .font(.headline)
                        .foregroundStyle(.green)
                    Text("Every cloud request from MacHybridAI enforces stateless execution so nothing remains in any Cloud AI provider's history:")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 6) {
                        GridRow {
                            Text("Google Gemini 3.8 Flash").font(.caption.bold())
                            Text("interactions.create(store=False) — Zero server-side interaction storage").font(.caption).foregroundStyle(.secondary)
                        }
                        GridRow {
                            Text("Google Antigravity").font(.caption.bold())
                            Text("Ephemeral session context — Zero persistent cloud history").font(.caption).foregroundStyle(.secondary)
                        }
                        GridRow {
                            Text("M365 Copilot Proxy").font(.caption.bold())
                            Text("Temporary Chat Mode locked (M365_SAVE_HISTORY disabled)").font(.caption).foregroundStyle(.secondary)
                        }
                        GridRow {
                            Text("OpenAI Extension API").font(.caption.bold())
                            Text("store=false + X-No-Store: true + Cache-Control: no-store").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 12).fill(Color.green.opacity(0.08)))

                // Search & Browse Saved Conversations
                HStack {
                    TextField("Search saved prompts & responses...", text: $vm.historySearchQuery)
                        .textFieldStyle(.roundedBorder)
                    Text("\(vm.filteredConversations.count) conversation(s)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                ForEach(vm.filteredConversations) { conv in
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(conv.title)
                                .font(.headline)
                            Text("\(conv.messages.count) messages · Stored in \(conv.storageLocation.title) · \(conv.expirationSummary)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Open in Chat") {
                            vm.selectConversation(conv.id)
                        }
                        Button("Delete", role: .destructive) {
                            vm.deleteConversation(conv.id)
                        }
                    }
                    .padding(12)
                    .background(RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.04)))
                }
            }
            .padding(24)
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
                    vm.updateComposerLiveAudit()
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
                        Label("Sanitized Text (Safe for Stateless Cloud Models)", systemImage: "key.viewfinder")
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
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Apple Silicon Hardware Profiler & AI Providers")
                            .font(.title2.bold())
                        Text("Live Metal working-set profiler, local model cache validator, and hardware-matched model sizing.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button {
                        vm.refreshHardwareProfile()
                    } label: {
                        Label("Re-Profile Mac Hardware", systemImage: "cpu.fill")
                    }
                }

                if let hw = vm.hardwareProfile {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(spacing: 12) {
                            Image(systemName: "memorychip.fill")
                                .font(.title2)
                                .foregroundStyle(.cyan)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(hw.chipBrand) · \(hw.unifiedMemoryGb) GB Unified Memory")
                                    .font(.headline.bold())
                                Text("\(hw.cpuCoresTotal) CPU Cores (\(hw.cpuCoresPerformance)P + \(hw.cpuCoresEfficiency)E) · \(hw.gpuCores)-Core GPU (\(hw.gpuArchitecture)) · Tier: \(hw.hardwareTier)")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text(String(format: "Metal Working Set: %.1f GB", hw.metalWorkingSetGb))
                                .font(.caption.bold())
                                .padding(.horizontal, 10)
                                .padding(.vertical, 4)
                                .background(Capsule().fill(Color.cyan.opacity(0.2)))
                                .foregroundStyle(.cyan)
                        }

                        HStack(spacing: 16) {
                            Label("CPU Busy: \(hw.cpuBusyPercent)%", systemImage: "gauge.medium")
                                .font(.caption)
                            Label("GPU Busy: \(hw.gpuBusyPercent)% (Renderer \(hw.gpuRendererPercent)%)", systemImage: "sparkles.tv")
                                .font(.caption)
                            Label(String(format: "RAM Used: %d%% (%.1f GB free)", hw.memoryUsedPercent, hw.availableMemoryGb), systemImage: "memorychip")
                                .font(.caption)
                            if let kv = hw.recommendedKvBits {
                                Label("Recommended KV Cache: \(kv)-bit", systemImage: "bolt.horizontal.fill")
                                    .font(.caption.bold())
                                    .foregroundStyle(.green)
                            }
                        }

                        Divider()

                        Text("Hardware-Matched Model Sizing & Local Cache Status")
                            .font(.subheadline.bold())

                        ForEach(hw.recommendations) { rec in
                            HStack(alignment: .top, spacing: 10) {
                                VStack(alignment: .leading, spacing: 3) {
                                    HStack(spacing: 6) {
                                        Text(rec.modelId)
                                            .font(.system(.caption, design: .monospaced).bold())
                                        Text("\(rec.parameterCount) · \(rec.quantization)")
                                            .font(.caption2.bold())
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 2)
                                            .background(Capsule().fill(Color.purple.opacity(0.2)))
                                        Text(String(format: "~%.1f GB · %@", rec.estimatedMemoryGb, rec.expectedTpsRange))
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                        if rec.isReadyLocally {
                                            Text("Cached & Verified")
                                                .font(.system(size: 9, weight: .bold))
                                                .padding(.horizontal, 6)
                                                .padding(.vertical, 2)
                                                .background(Capsule().fill(Color.green.opacity(0.22)))
                                                .foregroundStyle(.green)
                                        } else {
                                            Text("Weights Not Downloaded")
                                                .font(.system(size: 9, weight: .semibold))
                                                .padding(.horizontal, 6)
                                                .padding(.vertical, 2)
                                                .background(Capsule().fill(Color.orange.opacity(0.2)))
                                                .foregroundStyle(.orange)
                                        }
                                    }
                                    Text(rec.rationale)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                                Button(vm.localModel == rec.modelId ? "Active" : "Use Model") {
                                    vm.selectRecommendedModel(rec.modelId)
                                }
                                .controlSize(.small)
                                .disabled(!rec.fitsInMetalBudget)
                            }
                            .padding(8)
                            .background(RoundedRectangle(cornerRadius: 8).fill(Color.white.opacity(0.03)))
                        }
                    }
                    .padding(14)
                    .background(RoundedRectangle(cornerRadius: 12).fill(Color.white.opacity(0.05)))
                }

                Form {
                    Section("On-Device Local Model (This Mac — Apple Silicon Metal / MLX)") {
                        TextField("Active Local Model Identifier (MLX / LiteRT / Ollama)", text: $vm.localModel)
                            .onChange(of: vm.localModel) { _, newValue in
                                vm.selectRecommendedModel(newValue)
                            }
                        TextField("Local OpenAI-Compatible Endpoint", text: $vm.localEndpoint)
                    }

                    Section("Default Cloud AI — Google Gemini & Antigravity (Stateless store=false)") {
                        TextField("Gemini Model (Interactions API)", text: $vm.geminiModel)
                        TextField("Antigravity Managed Agent ID", text: $vm.antigravityAgent)
                    }

                    Section("Microsoft 365 Copilot Proxy (cramt/m365-copilot-proxy · Temporary Chat Locked)") {
                        TextField("Proxy Loopback Port", text: $vm.m365Port)
                        TextField("M365 Tone / Model (Recommended: gpt-5.5-think-deeper)", text: $vm.m365Model)
                        Toggle("Interactive Browser SSO/MFA Approval (M365_ENABLE_INTERACTIVE_APPROVAL=1)", isOn: $vm.m365InteractiveApproval)
                        Toggle("Avoid PerUserThrottled Reserve Guard (M365_AVOID_THROTTLING=1)", isOn: $vm.m365AvoidThrottling)
                    }

                    Section("Custom OpenAI Extension Method (store=false, X-No-Store: true)") {
                        TextField("OpenAI-Compatible Base URL", text: $vm.openAIBaseURL)
                        TextField("OpenAI-Compatible Model Name", text: $vm.openAIModel)
                    }
                }
                .formStyle(.grouped)
            }
            .padding(20)
        }
    }
}

/// Distinct Menu Bar Quick-Chat & Hybrid Compute Control Panel
struct MenuBarHybridPanelView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                HybridBrandEmblemView()
                VStack(alignment: .leading, spacing: 1) {
                    Text("MacHybridAI Studio")
                        .font(.subheadline.bold())
                    Text("Split-Compute · Zero Cloud History")
                        .font(.system(size: 10))
                        .foregroundStyle(.green)
                }
                Spacer()
            }

            Picker("Compute Mode", selection: $vm.computeMode) {
                ForEach(ComputeModeOption.allCases, id: \.self) { mode in
                    Text(mode.title).tag(mode)
                }
            }
            .pickerStyle(.segmented)

            Picker("History Storage", selection: $vm.historyStorage) {
                ForEach(HistoryStorageOption.allCases, id: \.self) { loc in
                    Text(loc.title).tag(loc)
                }
            }
            .controlSize(.small)
            .onChange(of: vm.historyStorage) { _, _ in
                vm.updateHistorySettings()
            }

            Picker("Auto-Delete", selection: $vm.historyRetention) {
                ForEach(HistoryRetentionOption.allCases, id: \.self) { ret in
                    Text(ret.shortBadge).tag(ret)
                }
            }
            .controlSize(.small)
            .onChange(of: vm.historyRetention) { _, _ in
                vm.updateHistorySettings()
            }

            Divider()

            Text("Quick Hybrid Chat:")
                .font(.caption.bold())
            HStack {
                TextField("Ask Local Mac or Hybrid Cloud...", text: $vm.promptText)
                    .textFieldStyle(.roundedBorder)
                Button("Send") {
                    vm.sendChatMessage()
                }
                .buttonStyle(.borderedProminent)
            }

            if let lastMsg = vm.activeConversation?.messages.last(where: { $0.role == "assistant" }) {
                Text(lastMsg.content)
                    .font(.caption2)
                    .lineLimit(3)
                    .padding(6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 6).fill(Color.white.opacity(0.06)))
            }

            Divider()

            HStack {
                Button("New Chat") {
                    vm.startNewChat()
                }
                Spacer()
                Button("Quit MacHybridAI") {
                    NSApplication.shared.terminate(nil)
                }
            }
            .font(.caption)
        }
        .padding(12)
        .frame(width: 320)
    }
}

@main
struct MacHybridAIApp: App {
    @StateObject private var viewModel = HybridAppViewModel()

    var body: some Scene {
        WindowGroup("MacHybridAI — Hybrid Compute Chat & Privacy Gate") {
            MainDashboardView(vm: viewModel)
                .preferredColorScheme(.dark)
        }
        .windowStyle(.titleBar)

        MenuBarExtra {
            MenuBarHybridPanelView(vm: viewModel)
        } label: {
            HStack(spacing: 4) {
                Image(nsImage: HybridBrandIconGenerator.makeMenuBarIcon())
                Text("M⇄AI")
                    .font(.system(size: 11, weight: .bold, design: .monospaced))
            }
        }
        .menuBarExtraStyle(.window)
    }
}
