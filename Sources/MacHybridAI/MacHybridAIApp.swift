import SwiftUI
import AppKit

/// Renders bespoke MacHybridAI icons (Dock App Icon & Menu Bar Split-Chip Icon)
/// so the app and menu bar look unmistakably like a Hybrid Compute AI Studio
/// (Apple Silicon [M] Chip + Privacy Gate Lock + Cloud [AI] Node).
public enum HybridBrandIconGenerator {
    @MainActor private static var cachedDockIcon: NSImage?
    @MainActor private static var cachedMenuBarIcon: NSImage?

    @MainActor
    public static func makeDockIcon(size: CGFloat = 512) -> NSImage {
        if size == 512, let cachedDockIcon {
            return cachedDockIcon
        }
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
        if size == 512 {
            cachedDockIcon = img
        }
        return img
    }

    /// Creates a crisp 22x18 Menu Bar template image depicting a Split Chip [M] <-> Cloud [AI]
    /// so the menu bar icon never resembles a shield or posture app.
    @MainActor
    public static func makeMenuBarIcon() -> NSImage {
        if let cachedMenuBarIcon {
            return cachedMenuBarIcon
        }
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
        cachedMenuBarIcon = img
        return img
    }
}

/// Apple HIG Liquid Glass surface modifier using native macOS vibrancy materials,
/// continuous squircle geometry, and a 1pt specular highlight rim.
extension View {
    func appleLiquidGlassCard(
        cornerRadius: CGFloat = 14,
        tint: Color = .cyan,
        tintOpacity: Double = 0.06,
        borderOpacity: Double = 0.16
    ) -> some View {
        self
            .background(
                ZStack {
                    RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                        .fill(.ultraThinMaterial)
                    RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                        .fill(
                            LinearGradient(
                                colors: [
                                    tint.opacity(tintOpacity),
                                    Color.white.opacity(0.02),
                                ],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                }
            )
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .strokeBorder(
                        LinearGradient(
                            colors: [
                                Color.white.opacity(borderOpacity + 0.08),
                                tint.opacity(borderOpacity),
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 1
                    )
            )
    }
}

/// Custom SwiftUI Brand Emblem showing the Split-Compute Silicon Chip + Privacy Gate + Cloud AI.
struct HybridBrandEmblemView: View {
    var body: some View {
        HStack(spacing: 4) {
            ZStack {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
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
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .strokeBorder(Color.cyan.opacity(0.6), lineWidth: 1)
                    )

                HStack(spacing: 3) {
                    Image(systemName: "memorychip.fill")
                        .font(.system(size: 11, weight: .bold))
                        .symbolRenderingMode(.hierarchical)
                        .foregroundStyle(.cyan)
                    Image(systemName: "arrow.left.and.right")
                        .font(.system(size: 8, weight: .black))
                        .foregroundStyle(.yellow)
                    Image(systemName: "sparkles")
                        .font(.system(size: 11, weight: .bold))
                        .symbolRenderingMode(.hierarchical)
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

    // Prompt History Storage (Local Mac vs iCloud Drive vs Google Drive) & Auto-Delete Policy
    @Published var historyStorage: HistoryStorageOption = .localMac
    @Published var historyRetention: HistoryRetentionOption = .days30
    @Published var conversations: [ChatConversationModel] = []
    @Published var activeConversationId: String = ""
    @Published var historySearchQuery: String = ""
    @Published var redactPIIOnShare: Bool = true
    @Published var lastSharedFileURL: URL? = nil
    @Published var lastShareStatusMessage: String = ""
    @Published var googleDrivePathDisplay: String = ""

    // Provider configuration fields
    @Published var localBackend: LocalBackendOption = AppleFoundationModelsEngine.checkAvailability().available ? .appleFoundationModels : .mlx
    @Published var allowUnverifiedHuggingFace: Bool = false
    @Published var isShowingHuggingFaceWarningAlert: Bool = false
    @Published var localModelDir: String = ""
    @Published var appleFMStatus: AppleFoundationModelsEngine.AvailabilityReport = AppleFoundationModelsEngine.checkAvailability()
    @Published var geminiModel: String = "gemini-3.8-flash"
    @Published var antigravityAgent: String = "antigravity-preview-05-2026"
    @Published var anthropicModel: String = "claude-sonnet-4-5"
    @Published var anthropicBaseURL: String = "https://api.anthropic.com/v1"
    @Published var localModel: String = "gemma4:26b"
    @Published var localEndpoint: String = "http://127.0.0.1:11434/v1"
    @Published var openAIBaseURL: String = "https://api.openai.com/v1"
    @Published var openAIModel: String = "gpt-4.1"
    @Published var customProviderProtocol: CustomCloudProtocolOption = .openai
    @Published var customProviderAuthHeader: String = "Authorization"
    @Published var cloudApiKeyInput: String = ""
    @Published var providerSyncStatus: String = ""
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

    // Privacy Gate live inspector & Interactive Approval Gate
    @Published var inspectorInput: String = "Prepared for Sam Reyes (sam.reyes@meridian.io), phone (415) 555-2671, SSN 123-45-6789."
    @Published var inspectorAudit: GuardianAuditModel?
    @Published var approveBeforeCloudDispatch: Bool = false
    @Published var isShowingSanitizationApproval: Bool = false
    @Published var pendingSanitizedDraft: String = ""
    @Published var lastVisionOCRSourceFile: String = ""

    // Quick Ask Spotlight HUD & On-Device Voice Dictation
    @Published var isShowingQuickAskSpotlight: Bool = false
    @Published var quickAskPrompt: String = ""
    @Published var isVoiceDictating: Bool = false

    @Published var selectedSection: MainWorkspaceSection = .chat
    @Published var hardwareProfile: MacHardwareProfileModel?
    @Published var latestBenchmark: HardwareBenchmarkResultModel?
    @Published var isBenchmarking: Bool = false
    @Published var lastPullResult: ModelPullResultModel?
    @Published var isPullingModelId: String?
    @Published var customPullModelId: String = "google/gemma-3-4b-it"

    private let historyStore = PromptHistoryStore()

    init() {
        NSApplication.shared.applicationIconImage = HybridBrandIconGenerator.makeDockIcon()
        self.googleDrivePathDisplay = historyStore.googleDriveDirectoryURL.path
        loadSavedHistory()
        runInspector()
        updateComposerLiveAudit()
        // Start the persistent Python daemon eagerly so the first chat send has no cold-start delay.
        BackendBridge.shared.ensureDaemonStarted()
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

    func setLocalBackend(_ backend: LocalBackendOption) {
        self.localBackend = backend
        let raw = backend.rawValue
        Task.detached(priority: .utility) {
            BackendBridge.shared.updateBackendConfig(body: ["local_backend": raw])
        }
    }

    func setLocalModelDir(_ dirPath: String) {
        self.localModelDir = dirPath
        let trimmed = dirPath.trimmingCharacters(in: .whitespacesAndNewlines)
        Task.detached(priority: .utility) {
            BackendBridge.shared.updateBackendConfig(body: ["local_model_dir": trimmed])
        }
    }

    func setAllowUnverifiedHuggingFace(_ allow: Bool) {
        self.allowUnverifiedHuggingFace = allow
        Task.detached(priority: .utility) {
            BackendBridge.shared.updateBackendConfig(
                body: [
                    "allow_unverified_huggingface": allow,
                    "huggingface_override_acknowledged": allow,
                    "persist_security_settings": true,
                ]
            )
            let updatedProfile = BackendBridge.shared.fetchHardwareProfile()
            await MainActor.run {
                self.hardwareProfile = updatedProfile
            }
        }
    }

    func activateDownloadedModel(_ model: CachedModelStatusModel) {
        if model.backend == "mlx_local_dir" {
            self.localBackend = .mlx
            self.localModelDir = model.localPath
            self.localModel = model.modelId
            Task.detached(priority: .utility) {
                BackendBridge.shared.updateBackendConfig(
                    body: [
                        "local_backend": "mlx",
                        "local_model_dir": model.localPath,
                        "local_model": model.modelId,
                    ]
                )
            }
        } else {
            self.localBackend = .mlx
            self.localModelDir = ""
            self.localModel = model.modelId
            Task.detached(priority: .utility) {
                BackendBridge.shared.updateBackendConfig(
                    body: [
                        "local_backend": "mlx",
                        "local_model_dir": "",
                        "local_model": model.modelId,
                    ]
                )
            }
        }
    }

    func convertFirstPartyModel(_ repoId: String, qBits: Int = 4) {
        let cleaned = repoId.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty, isPullingModelId == nil else { return }
        isPullingModelId = cleaned
        Task.detached(priority: .userInitiated) {
            let res = BackendBridge.shared.convertFirstPartyLocalModel(repoId: cleaned, qBits: qBits)
            let updatedProfile = BackendBridge.shared.fetchHardwareProfile()
            await MainActor.run {
                self.lastPullResult = res
                self.hardwareProfile = updatedProfile
                self.isPullingModelId = nil
                if res.ok {
                    self.localBackend = .mlx
                    self.setLocalModelDir(res.modelId)
                }
            }
        }
    }

    func applyCloudProviderPreset(_ provider: CloudProviderOption) {
        self.cloudProvider = provider
        switch provider {
        case .gemini:
            if geminiModel.isEmpty { geminiModel = provider.defaultModel }
        case .anthropic:
            anthropicBaseURL = provider.defaultBaseURL
            if anthropicModel.isEmpty { anthropicModel = provider.defaultModel }
        case .openai:
            openAIBaseURL = provider.defaultBaseURL
            openAIModel = provider.defaultModel
            customProviderProtocol = .openai
            customProviderAuthHeader = "Authorization"
        case .openRouter, .xai, .groq, .deepseek, .mistral, .perplexity, .together:
            openAIBaseURL = provider.defaultBaseURL
            openAIModel = provider.defaultModel
            customProviderProtocol = .openai
            customProviderAuthHeader = "Authorization"
        case .openAICompatible:
            if openAIBaseURL.isEmpty { openAIBaseURL = provider.defaultBaseURL }
            if openAIModel.isEmpty { openAIModel = provider.defaultModel }
        case .antigravity, .m365Copilot, .consensus:
            break
        }
        syncCloudProviderConfiguration()
    }

    func syncCloudProviderConfiguration() {
        let fields: [String: String] = [
            "cloud_provider": cloudProvider.rawValue,
            "gemini_model": geminiModel,
            "antigravity_agent": antigravityAgent,
            "anthropic_model": anthropicModel,
            "anthropic_base_url": anthropicBaseURL,
            "openai_base_url": openAIBaseURL,
            "openai_model": openAIModel,
            "custom_provider_protocol": customProviderProtocol.rawValue,
            "custom_provider_auth_header": customProviderAuthHeader,
            "m365_model": m365Model,
        ]
        var apiKeys: [String: String] = [:]
        let trimmedKey = cloudApiKeyInput.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedKey.isEmpty {
            apiKeys[cloudProvider.rawValue] = trimmedKey
            if cloudProvider == .openAICompatible {
                apiKeys["openai"] = trimmedKey
            }
        }
        BackendBridge.shared.syncCloudProviderConfigAsync(fields: fields, apiKeys: apiKeys)
        let keyNote = trimmedKey.isEmpty
            ? "using \(cloudProvider.apiKeyEnvName) from environment"
            : "in-memory API key loaded (never saved to disk)"
        providerSyncStatus = "Active Cloud AI: \(cloudProvider.shortName) (\(keyNote))"
        cloudApiKeyInput = ""
    }

    func runBenchmark(for modelId: String? = nil) {
        guard !isBenchmarking else { return }
        isBenchmarking = true
        let target = modelId ?? localModel
        Task.detached(priority: .userInitiated) {
            let bench = BackendBridge.shared.runHardwareBenchmark(modelId: target)
            let updatedProfile = BackendBridge.shared.fetchHardwareProfile()
            await MainActor.run {
                self.latestBenchmark = bench
                self.hardwareProfile = updatedProfile
                self.isBenchmarking = false
            }
        }
    }

    func verifyOrPullModel(_ modelId: String, allowDownload: Bool = false) {
        guard isPullingModelId == nil else { return }
        isPullingModelId = modelId
        Task.detached(priority: .userInitiated) {
            let res = BackendBridge.shared.pullOrVerifyLocalModel(modelId: modelId, allowDownload: allowDownload)
            let updatedProfile = BackendBridge.shared.fetchHardwareProfile()
            await MainActor.run {
                self.lastPullResult = res
                self.hardwareProfile = updatedProfile
                self.isPullingModelId = nil
                if res.isComplete {
                    self.selectRecommendedModel(res.modelId)
                }
            }
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

    var activeSharedFolderPath: String {
        historyStore.sharedDirectoryURL(for: historyStorage).path
    }

    var isICloudAvailable: Bool {
        historyStore.isICloudAvailable()
    }

    var isGoogleDriveAvailable: Bool {
        historyStore.isGoogleDriveAvailable()
    }

    func chooseCustomGoogleDriveFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.title = "Choose Google Drive (or Cloud Drive) Folder"
        panel.message = "Select your synced Google Drive / My Drive folder to store and share MacHybridAI prompts."
        let cloudStorage = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/CloudStorage", isDirectory: true)
        if FileManager.default.fileExists(atPath: cloudStorage.path) {
            panel.directoryURL = cloudStorage
        }
        if panel.runModal() == .OK, let selectedURL = panel.url {
            historyStore.setCustomGoogleDriveDirectory(selectedURL)
            googleDrivePathDisplay = historyStore.googleDriveDirectoryURL.path
            historyStorage = .googleDrive
            updateHistorySettings()
        }
    }

    func resetGoogleDriveFolderToAutoDetect() {
        historyStore.setCustomGoogleDriveDirectory(nil)
        googleDrivePathDisplay = historyStore.googleDriveDirectoryURL.path
        if historyStorage == .googleDrive {
            updateHistorySettings()
        }
    }

    /// Presents the native macOS Share sheet (with iCloud Collaborate / AirDrop / Mail / Messages / Google Drive) for an exported cloud file.
    func presentNativeSharePicker(for fileURL: URL, preferICloudCollaborate: Bool = false) {
        if preferICloudCollaborate,
           let cloudService = NSSharingService(named: .cloudSharing),
           cloudService.canPerform(withItems: [fileURL]) {
            cloudService.perform(withItems: [fileURL])
            return
        }
        let picker = NSSharingServicePicker(items: [fileURL])
        if let anchorView = NSApp.keyWindow?.contentView {
            let anchorRect = NSRect(
                x: max(20, anchorView.bounds.midX - 40),
                y: max(20, anchorView.bounds.maxY - 60),
                width: 80,
                height: 24
            )
            picker.show(relativeTo: anchorRect, of: anchorView, preferredEdge: .minY)
        } else {
            NSWorkspace.shared.activateFileViewerSelecting([fileURL])
        }
    }

    /// Exports a full conversation to the selected cloud drive (`iCloud Drive`, `Google Drive`, or `Local`) and opens native sharing.
    func shareConversation(
        _ conversation: ChatConversationModel,
        destination: HistoryStorageOption? = nil,
        redactPII: Bool? = nil,
        preferICloudCollaborate: Bool = false,
        revealInFinderOnly: Bool = false
    ) {
        let targetStorage = destination ?? historyStorage
        let shouldRedact = redactPII ?? redactPIIOnShare
        guard let exportedURL = historyStore.exportShareableConversation(
            conversation,
            to: targetStorage,
            redactPII: shouldRedact
        ) else {
            lastShareStatusMessage = "Could not write shareable file to \(targetStorage.title)."
            return
        }
        lastSharedFileURL = exportedURL
        let privacyTag = shouldRedact ? "PII-redacted" : "full"
        lastShareStatusMessage = "Saved \(privacyTag) Markdown to \(targetStorage.title): \(exportedURL.lastPathComponent)"

        if revealInFinderOnly {
            NSWorkspace.shared.activateFileViewerSelecting([exportedURL])
        } else {
            presentNativeSharePicker(
                for: exportedURL,
                preferICloudCollaborate: preferICloudCollaborate && targetStorage == .iCloudDrive
            )
        }
    }

    /// Exports a single prompt or response bubble to the active cloud drive and opens native macOS sharing.
    func shareMessage(
        _ message: ChatMessageModel,
        conversationTitle: String,
        destination: HistoryStorageOption? = nil,
        redactPII: Bool? = nil
    ) {
        let targetStorage = destination ?? historyStorage
        let shouldRedact = redactPII ?? redactPIIOnShare
        guard let exportedURL = historyStore.exportShareableMessage(
            message,
            conversationTitle: conversationTitle,
            to: targetStorage,
            redactPII: shouldRedact
        ) else {
            lastShareStatusMessage = "Could not export message to \(targetStorage.title)."
            return
        }
        lastSharedFileURL = exportedURL
        let privacyTag = shouldRedact ? "PII-redacted" : "full"
        lastShareStatusMessage = "Saved \(privacyTag) snippet to \(targetStorage.title): \(exportedURL.lastPathComponent)"
        presentNativeSharePicker(for: exportedURL, preferICloudCollaborate: false)
    }

    func copyConversationMarkdown(_ conversation: ChatConversationModel, redactPII: Bool? = nil) {
        let shouldRedact = redactPII ?? redactPIIOnShare
        let md = historyStore.renderMarkdown(for: conversation, redactPII: shouldRedact)
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(md, forType: .string)
        lastShareStatusMessage = "Copied \(shouldRedact ? "PII-redacted" : "full") Markdown to clipboard."
    }

    func revealSharedFileInFinder(_ fileURL: URL? = nil) {
        if let url = fileURL ?? lastSharedFileURL {
            NSWorkspace.shared.activateFileViewerSelecting([url])
        } else {
            openSharedFolderInFinder()
        }
    }

    func openSharedFolderInFinder() {
        let dir = historyStore.sharedDirectoryURL(for: historyStorage)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        NSWorkspace.shared.open(dir)
    }

    func openInGoogleDriveWeb(conversation: ChatConversationModel? = nil) {
        let targetURL: URL?
        if let conv = conversation {
            targetURL = historyStore.exportShareableConversation(
                conv,
                to: .googleDrive,
                redactPII: redactPIIOnShare
            )
            if let exported = targetURL {
                lastSharedFileURL = exported
                lastShareStatusMessage = "Synced to Google Drive: \(exported.lastPathComponent) — opening Google Drive web search."
            }
        } else {
            targetURL = lastSharedFileURL
        }
        if let fileURL = targetURL, let webURL = PromptHistoryStore.googleDriveWebSearchURL(for: fileURL) {
            NSWorkspace.shared.open(webURL)
        } else if let rootURL = URL(string: "https://drive.google.com/drive/my-drive") {
            NSWorkspace.shared.open(rootURL)
        }
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
        selectedSection = .chat
    }

    func deleteConversation(_ id: String) {
        conversations.removeAll { $0.id == id }
        if activeConversationId == id {
            activeConversationId = conversations.first?.id ?? ""
        }
        historyStore.saveConversations(conversations, to: historyStorage)
        BackendBridge.shared.sendHistoryActionAsync(["action": "delete_session", "session_id": id])
    }

    func clearAllHistory() {
        conversations.removeAll()
        activeConversationId = ""
        historyStore.saveConversations([], to: historyStorage)
        BackendBridge.shared.sendHistoryActionAsync(["action": "clear_all"])
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
        BackendBridge.shared.sendHistoryActionAsync(["action": "prune_expired"])
    }

    func updateHistorySettings() {
        conversations = historyStore.applyRetentionPolicy(
            historyRetention,
            conversations: conversations,
            location: historyStorage
        )
        BackendBridge.shared.sendHistoryActionAsync([
            "action": "configure",
            "storage_location": historyStorage.rawValue,
            "retention_policy": historyRetention.rawValue,
        ])
    }

    func updateComposerLiveAudit() {
        composerLiveAudit = BackendBridge.shared.inspectPII(
            text: promptText,
            policy: guardianPolicy
        )
    }

    func requestSendChatMessage() {
        let trimmed = promptText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        if approveBeforeCloudDispatch && computeMode != .local {
            updateComposerLiveAudit()
            pendingSanitizedDraft = composerLiveAudit?.sanitizedText ?? trimmed
            isShowingSanitizationApproval = true
        } else {
            sendChatMessage(approvedSanitizedPrompt: nil)
        }
    }

    func sendChatMessage(approvedSanitizedPrompt: String? = nil) {
        let trimmed = promptText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        isShowingSanitizationApproval = false
        isRunning = true

        if conversations.isEmpty || !conversations.contains(where: { $0.id == activeConversationId }) {
            startNewChat()
        }

        let currentSessionId = activeConversationId
        let mode = computeMode
        let provider = cloudProvider
        let policy = guardianPolicy
        let files = attachedFiles
        let approvedPrompt = approvedSanitizedPrompt
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

        // Stream tokens natively in Pure Swift on a background task, updating the placeholder bubble in real time
        Task.detached(priority: .userInitiated) {
            BackendBridge.shared.streamTask(
                prompt: trimmed,
                mode: mode,
                cloudProvider: provider,
                guardianPolicy: policy,
                attachedFiles: files,
                sessionId: currentSessionId,
                approvedSanitizedPrompt: approvedPrompt,
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
                        sessionId: currentSessionId,
                        approvedSanitizedPrompt: approvedPrompt
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

    /// Runs macOS native Vision OCR (`VNRecognizeTextRequest`) or PDFKit extraction on a user-selected
    /// screenshot, invoice, or PDF, and populates the Privacy Gate inspector with the scrubbed text.
    func importAndScrubFileViaVisionOCR() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.message = "Select an Image (.png, .jpg, .heic) or PDF to extract & scrub PII on-device via Apple Vision"
        if panel.runModal() == .OK, let url = panel.url {
            let (extracted, audit) = LocalVisionOCRScrubber.extractAndAuditFile(
                at: url,
                policy: guardianPolicy
            )
            lastVisionOCRSourceFile = url.lastPathComponent
            if !extracted.isEmpty {
                inspectorInput = extracted
                inspectorAudit = audit
            }
        }
    }

    /// Toggles on-device voice dictation using macOS native Speech / Dictation services.
    func toggleVoiceDictation() {
        isVoiceDictating.toggle()
        if isVoiceDictating {
            _ = NSApplication.shared.sendAction(Selector(("startDictation:")), to: nil, from: nil)
            updateComposerLiveAudit()
        }
    }

    /// Runs a 1-click Spotlight Quick Ask action on either `quickAskPrompt` or the current macOS Clipboard.
    func runQuickAskAction(instructionPrefix: String, mode: ComputeModeOption, provider: CloudProviderOption? = nil) {
        let baseText: String
        let trimmedQuick = quickAskPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedQuick.isEmpty {
            baseText = trimmedQuick
        } else if let clip = NSPasteboard.general.string(forType: .string), !clip.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            baseText = clip.trimmingCharacters(in: .whitespacesAndNewlines)
        } else {
            baseText = promptText
        }
        guard !baseText.isEmpty else { return }

        computeMode = mode
        if let provider {
            cloudProvider = provider
        }
        promptText = "\(instructionPrefix)\n\n\(baseText)"
        quickAskPrompt = ""
        isShowingQuickAskSpotlight = false
        selectedSection = .chat
        sendChatMessage()
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
        case .nativeSwift: return .green
        case .running: return .cyan
        case .starting: return .yellow
        case .failed: return .red
        case .notStarted: return .secondary
        }
    }

    private var statusLabel: String {
        switch daemon.state {
        case .nativeSwift: return "Engine: Pure Swift Native"
        case .running(let port): return "Engine: ready (:\(port))"
        case .starting: return "Engine: starting…"
        case .failed(let msg): return "Engine: \(msg.prefix(28))"
        case .notStarted: return "Engine: not started"
        }
    }
}

struct MainDashboardView: View {
    @ObservedObject var vm: HybridAppViewModel

    private var activeWindowTitle: String {
        switch vm.selectedSection {
        case .chat:
            return vm.activeConversation?.title ?? "MacHybridAI"
        case .history:
            return "History & Cloud"
        case .privacyGate:
            return "Privacy Gate"
        }
    }

    private var activeWindowSubtitle: String {
        switch vm.selectedSection {
        case .chat:
            return "\(vm.localBackend.trustBadge) · \(vm.historyStorage.title) · Zero Cloud History"
        case .history:
            return "\(vm.conversations.count) saved conversation\(vm.conversations.count == 1 ? "" : "s") · \(vm.historyRetention.displayName)"
        case .privacyGate:
            return "On-Device PII Guardian (\(vm.guardianPolicy.displayName))"
        }
    }

    var body: some View {
        NavigationSplitView {
            List {
                Section("Workspace") {
                    ForEach(MainWorkspaceSection.allCases, id: \.self) { section in
                        Button {
                            vm.selectedSection = section
                        } label: {
                            Label(section.title, systemImage: section.iconName)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.vertical, 2)
                        }
                        .buttonStyle(.plain)
                        .listRowBackground(
                            vm.selectedSection == section
                                ? RoundedRectangle(cornerRadius: 6, style: .continuous).fill(Color.accentColor.opacity(0.22))
                                : RoundedRectangle(cornerRadius: 6, style: .continuous).fill(Color.clear)
                        )
                    }
                }

                Section("Conversations (\(vm.conversations.count))") {
                    ForEach(vm.filteredConversations) { conv in
                        Button {
                            vm.selectConversation(conv.id)
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(conv.title)
                                    .font(.callout)
                                    .lineLimit(1)
                                    .foregroundStyle(.primary)
                                HStack(spacing: 4) {
                                    Image(systemName: conv.storageLocation.iconName)
                                        .font(.caption2)
                                    Text(conv.expirationSummary)
                                        .font(.caption2)
                                }
                                .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 2)
                        }
                        .buttonStyle(.plain)
                        .listRowBackground(
                            (vm.selectedSection == .chat && conv.id == vm.activeConversationId)
                                ? RoundedRectangle(cornerRadius: 6, style: .continuous).fill(Color.accentColor.opacity(0.22))
                                : RoundedRectangle(cornerRadius: 6, style: .continuous).fill(Color.clear)
                        )
                        .contextMenu {
                            Button("Open Conversation") {
                                vm.selectConversation(conv.id)
                            }
                            Divider()
                            Button("\(vm.historyStorage.shareActionLabel) (Redacted)") {
                                vm.shareConversation(conv, redactPII: true)
                            }
                            Button("\(vm.historyStorage.shareActionLabel) (Full)") {
                                vm.shareConversation(conv, redactPII: false)
                            }
                            if vm.isICloudAvailable {
                                Button("Share iCloud Drive Link…") {
                                    vm.shareConversation(conv, destination: .iCloudDrive, redactPII: vm.redactPIIOnShare, preferICloudCollaborate: true)
                                }
                            }
                            if vm.isGoogleDriveAvailable {
                                Button("Save & Reveal in Google Drive") {
                                    vm.shareConversation(conv, destination: .googleDrive, redactPII: vm.redactPIIOnShare, revealInFinderOnly: true)
                                }
                                Button("Open in Google Drive Web…") {
                                    vm.openInGoogleDriveWeb(conversation: conv)
                                }
                            }
                            Button("Copy Redacted Markdown") {
                                vm.copyConversationMarkdown(conv, redactPII: true)
                            }
                            Divider()
                            Button("Delete Conversation", role: .destructive) {
                                vm.deleteConversation(conv.id)
                            }
                        }
                    }
                }
            }
            .listStyle(.sidebar)
            .searchable(text: $vm.historySearchQuery, placement: .sidebar, prompt: "Filter conversations")
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 0) {
                    Divider()
                    HStack(spacing: 8) {
                        DaemonStatusView()
                        Spacer()
                        SettingsLink {
                            Label("Settings…", systemImage: "gearshape")
                                .font(.caption)
                        }
                        .buttonStyle(.borderless)
                        .help("Open MacHybridAI Settings (⌘,)")
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                }
                .background(.bar)
            }
            .navigationSplitViewColumnWidth(min: 220, ideal: 250, max: 320)
        } detail: {
            Group {
                switch vm.selectedSection {
                case .chat:
                    HybridChatTabView(vm: vm)
                case .history:
                    PromptHistoryAndICloudTabView(vm: vm)
                case .privacyGate:
                    PrivacyGateTabView(vm: vm)
                }
            }
            .frame(minWidth: 740, minHeight: 580)
            .navigationTitle(activeWindowTitle)
            .navigationSubtitle(activeWindowSubtitle)
            .toolbar {
                ToolbarItemGroup(placement: .primaryAction) {
                    Picker("Compute Mode", selection: $vm.computeMode) {
                        ForEach(ComputeModeOption.allCases, id: \.self) { option in
                            Text(option.title).tag(option)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 240)
                    .help("Switch between Fully Local (⌘1), Smart Auto (⌘2), and Hybrid (⌘3)")

                    SettingsLink {
                        Label(
                            vm.allowUnverifiedHuggingFace
                                ? "HF Bypass"
                                : (vm.localBackend == .appleFoundationModels ? "Apple-Signed" : "Strict"),
                            systemImage: vm.allowUnverifiedHuggingFace
                                ? "exclamationmark.triangle.fill"
                                : (vm.localBackend == .appleFoundationModels ? "checkmark.seal.fill" : "lock.shield.fill")
                        )
                        .foregroundStyle(vm.allowUnverifiedHuggingFace ? .orange : .green)
                    }
                    .help("Model Supply-Chain Security & Preferences (⌘,)")

                    if let activeConv = vm.activeConversation, !activeConv.messages.isEmpty {
                        Menu {
                            Button {
                                vm.shareConversation(activeConv, redactPII: true)
                            } label: {
                                Label("\(vm.historyStorage.shareActionLabel) (PII Redacted)", systemImage: "lock.shield")
                            }

                            Button {
                                vm.shareConversation(activeConv, redactPII: false)
                            } label: {
                                Label("\(vm.historyStorage.shareActionLabel) (Full Content)", systemImage: "doc.text")
                            }

                            Divider()

                            if vm.isICloudAvailable {
                                Button {
                                    vm.shareConversation(
                                        activeConv,
                                        destination: .iCloudDrive,
                                        redactPII: vm.redactPIIOnShare,
                                        preferICloudCollaborate: true
                                    )
                                } label: {
                                    Label("Share via iCloud Drive Link…", systemImage: "icloud.and.arrow.up")
                                }
                            }

                            Button {
                                vm.shareConversation(
                                    activeConv,
                                    destination: .googleDrive,
                                    redactPII: vm.redactPIIOnShare,
                                    revealInFinderOnly: true
                                )
                            } label: {
                                Label("Save & Reveal in Google Drive", systemImage: "folder.badge.person.crop")
                            }

                            Button {
                                vm.openInGoogleDriveWeb(conversation: activeConv)
                            } label: {
                                Label("Open & Share in Google Drive Web…", systemImage: "safari")
                            }

                            Divider()

                            Button {
                                vm.copyConversationMarkdown(activeConv, redactPII: true)
                            } label: {
                                Label("Copy Redacted Markdown", systemImage: "doc.on.doc")
                            }

                            Button {
                                vm.openSharedFolderInFinder()
                            } label: {
                                Label("Open Shared Cloud Folder in Finder", systemImage: "folder")
                            }
                        } label: {
                            Label("Share", systemImage: "square.and.arrow.up")
                        }
                        .help("Share conversation via \(vm.historyStorage.title) (⇧⌘S)")
                    }

                    Button {
                        vm.startNewChat()
                        vm.selectedSection = .chat
                    } label: {
                        Label("New Chat", systemImage: "square.and.pencil")
                    }
                    .help("New Conversation (⌘N)")

                    Button {
                        vm.isShowingQuickAskSpotlight = true
                    } label: {
                        Label("Quick Ask", systemImage: "sparkle.magnifyingglass")
                    }
                    .help("Quick Ask Spotlight (⌘K)")

                    SettingsLink {
                        Label("Settings", systemImage: "gearshape")
                    }
                    .help("Open Preferences (⌘,)")
                }
            }
        }
        .sheet(isPresented: $vm.isShowingSanitizationApproval) {
            SanitizationApprovalSheetView(vm: vm)
        }
        .sheet(isPresented: $vm.isShowingQuickAskSpotlight) {
            QuickAskSpotlightModalView(vm: vm)
        }
    }
}

/// Interactive Sanitization Diff Preview Sheet ("Approve Before Cloud Dispatch")
struct SanitizationApprovalSheetView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                HybridBrandEmblemView()
                VStack(alignment: .leading, spacing: 2) {
                    Text("Inspect & Approve Sanitized Cloud Payload")
                        .font(.headline.bold())
                    Text("Station 2 Privacy Gate has masked sensitive tokens on this Mac. Review or edit the payload before Station 3 cloud dispatch.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text("Zero Cloud History (store=false)")
                    .font(.caption2.bold())
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(Capsule().fill(Color.green.opacity(0.18)))
                    .foregroundStyle(.green)
            }

            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Label("Original Local Draft (Stays on This Mac)", systemImage: "lock.laptopcomputer")
                        .font(.caption.bold())
                        .foregroundStyle(.cyan)
                    ScrollView {
                        Text(vm.promptText)
                            .font(.system(.caption, design: .monospaced))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(8)
                    }
                    .frame(height: 130)
                    .background(RoundedRectangle(cornerRadius: 8).fill(Color.black.opacity(0.28)))
                }

                VStack(alignment: .leading, spacing: 6) {
                    Label("Editable Sanitized Payload (Sent to \(vm.cloudProvider.displayName))", systemImage: "key.viewfinder")
                        .font(.caption.bold())
                        .foregroundStyle(.orange)
                    TextEditor(text: $vm.pendingSanitizedDraft)
                        .font(.system(.caption, design: .monospaced))
                        .frame(height: 130)
                        .padding(4)
                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.orange.opacity(0.10)))
                }
            }

            if let audit = vm.composerLiveAudit, !audit.entities.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Redacted Stand-In Tokens (\(audit.entities.count)) — Restored Locally at Station 4:")
                        .font(.caption2.bold())
                        .foregroundStyle(.secondary)
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(audit.entities) { entity in
                                HStack(spacing: 4) {
                                    Text(entity.category)
                                        .font(.system(size: 9, weight: .bold))
                                    Text(entity.maskedPreview)
                                        .font(.system(size: 9, design: .monospaced))
                                    Image(systemName: "arrow.right")
                                        .font(.system(size: 8))
                                    Text(entity.replacementToken)
                                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                                        .foregroundStyle(.cyan)
                                }
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Capsule().fill(Color.white.opacity(0.08)))
                            }
                        }
                    }
                }
            }

            Divider()

            HStack {
                Button("Cancel") {
                    vm.isShowingSanitizationApproval = false
                }
                Spacer()
                Button("Run 100% Locally Instead") {
                    vm.computeMode = .local
                    vm.isShowingSanitizationApproval = false
                    vm.sendChatMessage(approvedSanitizedPrompt: nil)
                }
                .buttonStyle(.bordered)
                Button("Approve & Dispatch to Cloud") {
                    let approved = vm.pendingSanitizedDraft
                    vm.sendChatMessage(approvedSanitizedPrompt: approved)
                }
                .buttonStyle(.borderedProminent)
                .tint(Color(red: 0.20, green: 0.65, blue: 0.75))
            }
        }
        .padding(20)
        .frame(width: 680)
    }
}

/// Spotlight-style Floating Quick Ask HUD (`⌘K`) with 1-Click Split-Compute Actions on Clipboard or Prompt
struct QuickAskSpotlightModalView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: "sparkle.magnifyingglass")
                    .font(.title2)
                    .foregroundStyle(.cyan)
                VStack(alignment: .leading, spacing: 2) {
                    Text("MacHybridAI Quick Ask Spotlight")
                        .font(.headline.bold())
                    Text("Type a prompt or leave blank to act directly on your current macOS Clipboard with automatic on-device PII scrubbing.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    vm.isShowingQuickAskSpotlight = false
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }

            TextField("Ask anything or leave empty to process macOS Clipboard...", text: $vm.quickAskPrompt)
                .textFieldStyle(.roundedBorder)
                .font(.body)

            HStack(spacing: 8) {
                Button {
                    vm.runQuickAskAction(
                        instructionPrefix: "Summarize the following content privately on this Mac:",
                        mode: .local
                    )
                } label: {
                    Label("Summarize Privately (Local)", systemImage: "memorychip.fill")
                }
                .buttonStyle(.borderedProminent)
                .tint(.cyan)

                Button {
                    vm.runQuickAskAction(
                        instructionPrefix: "Refactor, improve, and analyze the following (with PII masked):",
                        mode: .hybrid
                    )
                } label: {
                    Label("Sanitize & Analyze (Hybrid)", systemImage: "key.viewfinder")
                }
                .buttonStyle(.borderedProminent)
                .tint(.purple)

                Button {
                    vm.runQuickAskAction(
                        instructionPrefix: "Compare perspectives and synthesize a consensus executive recommendation for:",
                        mode: .hybrid,
                        provider: .consensus
                    )
                } label: {
                    Label("Multi-Cloud Consensus Arena", systemImage: "sparkles.rectangle.stack.fill")
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(20)
        .frame(width: 620)
    }
}

struct HybridChatTabView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        VStack(spacing: 0) {
            // Slim macOS Context Strip (Title & Compute Mode live in the native window toolbar)
            HStack(spacing: 10) {
                Label(
                    vm.computeMode == .local
                        ? "100% On-Device (\(vm.localBackend.trustBadge))"
                        : "Privacy Gate Active · Zero Cloud History",
                    systemImage: vm.computeMode == .local ? "lock.shield.fill" : "checkmark.shield.fill"
                )
                .font(.caption)
                .foregroundStyle(.green)

                Spacer()

                if vm.computeMode != .local {
                    Picker("Cloud Provider", selection: $vm.cloudProvider) {
                        ForEach(CloudProviderOption.allCases, id: \.self) { provider in
                            Text(provider.displayName).tag(provider)
                        }
                    }
                    .controlSize(.small)
                    .frame(width: 280)
                    .onChange(of: vm.cloudProvider) { _, newProvider in
                        vm.applyCloudProviderPreset(newProvider)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(.bar)

            Divider()

            // Multi-Turn Chat Stream
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if !vm.lastShareStatusMessage.isEmpty {
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                            Text(vm.lastShareStatusMessage)
                                .font(.caption)
                                .lineLimit(1)
                            Spacer()
                            if let sharedURL = vm.lastSharedFileURL {
                                Button("Share Sheet…") {
                                    vm.presentNativeSharePicker(for: sharedURL)
                                }
                                .controlSize(.small)
                                Button("Reveal in Finder") {
                                    vm.revealSharedFileInFinder(sharedURL)
                                }
                                .controlSize(.small)
                                if vm.historyStorage == .googleDrive {
                                    Button("Google Drive Web") {
                                        vm.openInGoogleDriveWeb()
                                    }
                                    .controlSize(.small)
                                }
                            }
                            Button {
                                vm.lastShareStatusMessage = ""
                            } label: {
                                Image(systemName: "xmark")
                                    .font(.caption2)
                            }
                            .buttonStyle(.plain)
                            .foregroundStyle(.secondary)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(RoundedRectangle(cornerRadius: 10).fill(Color.green.opacity(0.10)))
                    }

                    if let conv = vm.activeConversation, !conv.messages.isEmpty {
                        ForEach(conv.messages) { msg in
                            ChatBubbleRowView(message: msg)
                                .equatable()
                                .contextMenu {
                                    Button("Share \(msg.role == "user" ? "Prompt" : "Response") via \(vm.historyStorage.title) (Redacted)…") {
                                        vm.shareMessage(msg, conversationTitle: conv.title, redactPII: true)
                                    }
                                    Button("Share \(msg.role == "user" ? "Prompt" : "Response") (Full)…") {
                                        vm.shareMessage(msg, conversationTitle: conv.title, redactPII: false)
                                    }
                                    Divider()
                                    Button("Copy Text") {
                                        NSPasteboard.general.clearContents()
                                        NSPasteboard.general.setString(msg.content, forType: .string)
                                    }
                                }
                        }
                    } else {
                        VStack(spacing: 10) {
                            HybridBrandEmblemView()
                            Text("Start a Hybrid or Local Chat")
                                .font(.title3.bold())
                            Text("Your prompts can be saved locally on your Mac, in iCloud Drive, or in Google Drive—and shared directly from MacHybridAI with automatic Privacy Gate PII redaction. Cloud AI calls always run with store=false.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                                .frame(maxWidth: 500)
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

                    if vm.computeMode != .local {
                        Toggle("Inspect Before Cloud", isOn: $vm.approveBeforeCloudDispatch)
                            .toggleStyle(.checkbox)
                            .font(.caption2.bold())
                            .help("Preview and edit the Station 2 sanitized payload before it leaves your Mac")
                    }

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
                                    Image(systemName: "doc.viewfinder.fill")
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
                    .help("Attach local Mac file, PDF, or screenshot (Vision OCR + BM25 RAG processed on-device)")

                    Button {
                        vm.toggleVoiceDictation()
                    } label: {
                        Image(systemName: vm.isVoiceDictating ? "waveform.circle.fill" : "mic.circle.fill")
                            .font(.system(size: 22))
                            .foregroundStyle(vm.isVoiceDictating ? .orange : .cyan)
                    }
                    .buttonStyle(.plain)
                    .help("On-Device Voice Dictation (transcribed locally & scrubbed by Privacy Gate)")

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
                        vm.requestSendChatMessage()
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "paperplane.fill")
                                .symbolRenderingMode(.hierarchical)
                            Text(vm.computeMode == .local ? "Send Local" : (vm.computeMode == .auto ? "Send Auto" : "Send Hybrid"))
                                .font(.subheadline.bold())
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color(red: 0.20, green: 0.65, blue: 0.75))
                    .keyboardShortcut(.return, modifiers: .command)
                    .help("Send prompt (⌘Return)")
                }
            }
            .padding(16)
            .background(.ultraThinMaterial)
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

// MARK: - Rich Markdown Message Renderer

/// Renders structured Markdown blocks (headings, fenced code blocks with 1-click Copy,
/// bullet/numbered/task lists, tables, blockquotes, and inline bold/italic/code/links)
/// following Apple macOS Human Interface Guidelines.
struct MarkdownMessageView: View {
    let markdown: String
    var isCompact: Bool = false

    var body: some View {
        let blocks = MarkdownBlockParser.parse(markdown)
        if blocks.isEmpty {
            Text(" ")
                .font(isCompact ? .caption2 : .body)
        } else {
            VStack(alignment: .leading, spacing: isCompact ? 6 : 10) {
                ForEach(Array(blocks.enumerated()), id: \.offset) { _, block in
                    renderBlock(block)
                }
            }
            .textSelection(.enabled)
        }
    }

    @ViewBuilder
    private func renderBlock(_ block: MarkdownBlock) -> some View {
        switch block {
        case .heading(let level, let text):
            Text(MarkdownBlockParser.inlineAttributedString(text))
                .font(headingFont(for: level))
                .foregroundStyle(.primary)
                .padding(.top, level <= 2 ? 4 : 2)

        case .paragraph(let text):
            Text(MarkdownBlockParser.inlineAttributedString(text))
                .font(isCompact ? .caption : .body)
                .fixedSize(horizontal: false, vertical: true)

        case .codeBlock(let language, let code):
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Label(language.isEmpty ? "code" : language, systemImage: "terminal.fill")
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundStyle(.cyan)
                    Spacer()
                    Button {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(code, forType: .string)
                    } label: {
                        Label("Copy", systemImage: "doc.on.doc")
                            .font(.system(size: 10, weight: .semibold))
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                    .help("Copy code block to clipboard")
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.white.opacity(0.05))

                Divider()

                ScrollView(.horizontal, showsIndicators: true) {
                    Text(code)
                        .font(.system(isCompact ? .caption2 : .callout, design: .monospaced))
                        .foregroundStyle(Color(red: 0.90, green: 0.95, blue: 1.0))
                        .textSelection(.enabled)
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(Color.black.opacity(0.38))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .strokeBorder(Color.cyan.opacity(0.24), lineWidth: 1)
            )

        case .bulletList(let items):
            VStack(alignment: .leading, spacing: 5) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        if item.hasPrefix("[x] ") || item.hasPrefix("[X] ") {
                            Image(systemName: "checkmark.square.fill")
                                .font(.system(size: 12))
                                .foregroundStyle(.green)
                            Text(MarkdownBlockParser.inlineAttributedString(String(item.dropFirst(4))))
                                .font(isCompact ? .caption : .body)
                        } else if item.hasPrefix("[ ] ") {
                            Image(systemName: "square")
                                .font(.system(size: 12))
                                .foregroundStyle(.secondary)
                            Text(MarkdownBlockParser.inlineAttributedString(String(item.dropFirst(4))))
                                .font(isCompact ? .caption : .body)
                        } else {
                            Text("•")
                                .font(.system(size: isCompact ? 11 : 14, weight: .bold))
                                .foregroundStyle(.cyan)
                            Text(MarkdownBlockParser.inlineAttributedString(item))
                                .font(isCompact ? .caption : .body)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }
            .padding(.leading, 4)

        case .orderedList(let items):
            VStack(alignment: .leading, spacing: 5) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(item.marker)
                            .font(.system(size: isCompact ? 11 : 13, weight: .bold, design: .monospaced))
                            .foregroundStyle(.cyan)
                            .frame(minWidth: 20, alignment: .trailing)
                        Text(MarkdownBlockParser.inlineAttributedString(item.text))
                            .font(isCompact ? .caption : .body)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .padding(.leading, 4)

        case .blockquote(let text):
            HStack(spacing: 10) {
                RoundedRectangle(cornerRadius: 2, style: .continuous)
                    .fill(Color.cyan.opacity(0.8))
                    .frame(width: 3)
                Text(MarkdownBlockParser.inlineAttributedString(text))
                    .font(isCompact ? .caption : .body)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.vertical, 4)
            .padding(.horizontal, 8)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.white.opacity(0.03))
            )

        case .table(let headers, let rows):
            ScrollView(.horizontal, showsIndicators: false) {
                Grid(alignment: .leading, horizontalSpacing: 14, verticalSpacing: 6) {
                    GridRow {
                        ForEach(Array(headers.enumerated()), id: \.offset) { _, header in
                            Text(MarkdownBlockParser.inlineAttributedString(header))
                                .font(.caption.bold())
                                .foregroundStyle(.cyan)
                                .padding(.vertical, 4)
                        }
                    }
                    Divider()
                    ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                        GridRow {
                            ForEach(0..<headers.count, id: \.self) { colIdx in
                                let cell = colIdx < row.count ? row[colIdx] : ""
                                Text(MarkdownBlockParser.inlineAttributedString(cell))
                                    .font(.caption)
                                    .padding(.vertical, 2)
                            }
                        }
                    }
                }
                .padding(10)
            }
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(Color.white.opacity(0.04))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.10), lineWidth: 1)
            )

        case .divider:
            Divider()
                .padding(.vertical, 2)
        }
    }

    private func headingFont(for level: Int) -> Font {
        if isCompact {
            return .caption.bold()
        }
        switch level {
        case 1: return .title2.bold()
        case 2: return .title3.bold()
        case 3: return .headline.bold()
        default: return .subheadline.bold()
        }
    }
}

struct ChatBubbleRowView: View, Equatable {
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

                    MarkdownMessageView(markdown: message.content)
                        .padding(12)
                        .background(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
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

                MarkdownMessageView(markdown: message.content)
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(Color.white.opacity(0.05))
                    )
                    .overlay(alignment: .bottomTrailing) {
                        if message.isStreaming {
                            StreamingCursorView()
                                .padding(8)
                        }
                    }

                // Expandable 4-Station Relay & Sanitized Cloud Prompt Inspector
                if !message.stations.isEmpty || message.sanitizedCloudPrompt != nil || message.receipt != nil {
                    DisclosureGroup("View 4-Station Hybrid Relay, Sanitized Cloud Prompt & Cryptographic Receipt") {
                        VStack(alignment: .leading, spacing: 8) {
                            if let receipt = message.receipt {
                                HStack(alignment: .center, spacing: 8) {
                                    Image(systemName: "checkmark.shield.fill")
                                        .foregroundStyle(.green)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("Zero-Knowledge Cryptographic Privacy Receipt (SHA-256)")
                                            .font(.caption2.bold())
                                            .foregroundStyle(.green)
                                        Text("Payload SHA-256: \(receipt.outboundPayloadSha256.prefix(24))… · Receipt Sig: \(receipt.receiptSignatureSha256.prefix(24))…")
                                            .font(.system(size: 10, design: .monospaced))
                                            .foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    Button("Copy Receipt") {
                                        let text = """
                                        MacHybridAI Zero-Knowledge Privacy Receipt
                                        Mode: \(receipt.modeExecuted)
                                        Local Model: \(receipt.localModelUsed)
                                        Cloud Models: \(receipt.cloudModelsUsed)
                                        PII Masked: \(receipt.piiFlaggedCount) (\(receipt.piiCategories.joined(separator: ", ")))
                                        PII Restored: \(receipt.piiRestoredCount)
                                        Cloud Zero Retention: \(receipt.cloudZeroRetention)
                                        Outbound Payload SHA-256: \(receipt.outboundPayloadSha256)
                                        Receipt Signature SHA-256: \(receipt.receiptSignatureSha256)
                                        """
                                        NSPasteboard.general.clearContents()
                                        NSPasteboard.general.setString(text, forType: .string)
                                    }
                                    .controlSize(.mini)
                                }
                                .padding(8)
                                .background(RoundedRectangle(cornerRadius: 8).fill(Color.green.opacity(0.08)))
                            }

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
            .padding(14)
            .appleLiquidGlassCard(cornerRadius: 16, tint: .cyan, tintOpacity: 0.04, borderOpacity: 0.14)
        }
    }
}

struct PromptHistoryAndICloudTabView: View {
    @ObservedObject var vm: HybridAppViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Prompt History, Cloud Drive Sync & Sharing")
                    .font(.title2.bold())
                Text("Save your prompts locally on this Mac, in iCloud Drive, or in Google Drive—and share individual prompts or full conversations directly through your cloud drive with optional Privacy Gate PII redaction. Cloud AI providers never retain your prompts.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                // Storage, Cloud Sharing & Retention Configuration Card
                VStack(alignment: .leading, spacing: 14) {
                    Picker("Save Prompt History To:", selection: $vm.historyStorage) {
                        ForEach(HistoryStorageOption.allCases, id: \.self) { loc in
                            let badge: String = {
                                switch loc {
                                case .localMac: return "Always Available"
                                case .iCloudDrive: return vm.isICloudAvailable ? "Detected" : "Not Signed In"
                                case .googleDrive: return vm.isGoogleDriveAvailable ? "Detected" : "Folder Picker Available"
                                }
                            }()
                            Text("\(loc.title) — \(badge)").tag(loc)
                        }
                    }
                    .pickerStyle(.radioGroup)
                    .onChange(of: vm.historyStorage) { _, _ in
                        vm.updateHistorySettings()
                    }

                    if vm.historyStorage == .googleDrive {
                        HStack(spacing: 10) {
                            Image(systemName: "folder.badge.person.crop")
                                .foregroundStyle(.cyan)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Google Drive Sync Folder")
                                    .font(.caption.bold())
                                Text(vm.googleDrivePathDisplay)
                                    .font(.system(.caption2, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                    .textSelection(.enabled)
                            }
                            Spacer()
                            Button("Choose Folder…") {
                                vm.chooseCustomGoogleDriveFolder()
                            }
                            .controlSize(.small)
                            Button("Auto-Detect") {
                                vm.resetGoogleDriveFolderToAutoDetect()
                            }
                            .controlSize(.small)
                        }
                        .padding(10)
                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.cyan.opacity(0.08)))
                    }

                    Divider()

                    HStack(spacing: 12) {
                        Toggle("Redact PII Before Sharing (Privacy Gate)", isOn: $vm.redactPIIOnShare)
                            .font(.caption.bold())
                        Spacer()
                        Button {
                            vm.openSharedFolderInFinder()
                        } label: {
                            Label("Open Shared Folder in Finder", systemImage: "folder")
                        }
                        .controlSize(.small)
                    }

                    if !vm.lastShareStatusMessage.isEmpty {
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                            Text(vm.lastShareStatusMessage)
                                .font(.caption)
                            Spacer()
                            if let url = vm.lastSharedFileURL {
                                Button("Share Sheet…") {
                                    vm.presentNativeSharePicker(for: url)
                                }
                                .controlSize(.small)
                                Button("Reveal in Finder") {
                                    vm.revealSharedFileInFinder(url)
                                }
                                .controlSize(.small)
                                if vm.historyStorage == .googleDrive {
                                    Button("Open Google Drive Web") {
                                        vm.openInGoogleDriveWeb()
                                    }
                                    .controlSize(.small)
                                }
                            }
                        }
                        .padding(10)
                        .background(RoundedRectangle(cornerRadius: 8).fill(Color.green.opacity(0.10)))
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
                            Text("OpenAI (GPT-4.1 / o3)").font(.caption.bold())
                            Text("store=false + X-No-Store: true + Privacy Gate PII masking").font(.caption).foregroundStyle(.secondary)
                        }
                        GridRow {
                            Text("Anthropic Claude").font(.caption.bold())
                            Text("Native /v1/messages API + Cache-Control: no-store + Privacy Gate PII masking").font(.caption).foregroundStyle(.secondary)
                        }
                        GridRow {
                            Text("M365 Copilot Proxy").font(.caption.bold())
                            Text("Temporary Chat Mode locked (M365_SAVE_HISTORY disabled)").font(.caption).foregroundStyle(.secondary)
                        }
                        GridRow {
                            Text("OpenRouter / Grok / Groq / DeepSeek / Custom").font(.caption.bold())
                            Text("Universal OpenAI or Anthropic protocol + X-No-Store: true + On-Device PII Vault").font(.caption).foregroundStyle(.secondary)
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
                    HStack(spacing: 10) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(conv.title)
                                .font(.headline)
                            Text("\(conv.messages.count) messages · Stored in \(conv.storageLocation.title) · \(conv.expirationSummary)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Menu {
                            Button("\(vm.historyStorage.shareActionLabel) (PII Redacted)") {
                                vm.shareConversation(conv, redactPII: true)
                            }
                            Button("\(vm.historyStorage.shareActionLabel) (Full Content)") {
                                vm.shareConversation(conv, redactPII: false)
                            }
                            Divider()
                            if vm.isICloudAvailable {
                                Button("Share via iCloud Drive Link…") {
                                    vm.shareConversation(conv, destination: .iCloudDrive, redactPII: vm.redactPIIOnShare, preferICloudCollaborate: true)
                                }
                            }
                            Button("Save & Reveal in Google Drive") {
                                vm.shareConversation(conv, destination: .googleDrive, redactPII: vm.redactPIIOnShare, revealInFinderOnly: true)
                            }
                            Button("Open & Share in Google Drive Web…") {
                                vm.openInGoogleDriveWeb(conversation: conv)
                            }
                            Divider()
                            Button("Copy Redacted Markdown") {
                                vm.copyConversationMarkdown(conv, redactPII: true)
                            }
                        } label: {
                            Label("Share", systemImage: "square.and.arrow.up")
                        }
                        .controlSize(.small)

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

                HStack(spacing: 12) {
                    Toggle("Inspect & Approve Sanitized Diff Before Every Cloud Call", isOn: $vm.approveBeforeCloudDispatch)
                        .font(.caption.bold())
                    Spacer()
                    Button {
                        vm.importAndScrubFileViaVisionOCR()
                    } label: {
                        Label("OCR Scrub Image / PDF (Apple Vision)", systemImage: "doc.viewfinder.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .tint(.cyan)
                }

                if !vm.lastVisionOCRSourceFile.isEmpty {
                    Label("Extracted & scrubbed on-device via Apple Vision OCR: \(vm.lastVisionOCRSourceFile)", systemImage: "checkmark.seal.fill")
                        .font(.caption2.bold())
                        .foregroundStyle(.cyan)
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
                if let hw = vm.hardwareProfile {
                    Text("\(hw.chipBrand) · \(hw.unifiedMemoryGb)GB")
                        .font(.system(size: 9, weight: .semibold, design: .monospaced))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(Color.cyan.opacity(0.2)))
                        .foregroundStyle(.cyan)
                }
            }

            if let hw = vm.hardwareProfile {
                HStack(spacing: 8) {
                    Label("GPU \(hw.gpuBusyPercent)%", systemImage: "sparkles.tv")
                        .font(.system(size: 10))
                    Label("RAM \(hw.memoryUsedPercent)%", systemImage: "memorychip")
                        .font(.system(size: 10))
                    Label(hw.guardrailTriggered ? "Guardrail" : hw.thermalState.capitalized, systemImage: "thermometer.medium")
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(hw.guardrailTriggered ? .orange : .green)
                    Spacer()
                    Button(vm.isBenchmarking ? "..." : "Benchmark") {
                        vm.runBenchmark(for: vm.localModel)
                    }
                    .controlSize(.mini)
                }
                if let bench = vm.latestBenchmark {
                    Text(String(format: "Active: %@ · %.1f tok/s · TTFT %.0fms", vm.localModel, bench.decodeTps, bench.ttftMs))
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                } else {
                    Text("Local Model: \(vm.localModel)")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
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

            HStack {
                Text("Quick Hybrid Chat:")
                    .font(.caption.bold())
                Spacer()
                if let audit = vm.composerLiveAudit, audit.piiCount > 0 {
                    Label("\(audit.piiCount) PII Masked", systemImage: "lock.shield.fill")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(.green)
                }
            }
            HStack(spacing: 6) {
                Button {
                    vm.toggleVoiceDictation()
                } label: {
                    Image(systemName: vm.isVoiceDictating ? "waveform.circle.fill" : "mic.circle.fill")
                        .font(.system(size: 16))
                        .foregroundStyle(vm.isVoiceDictating ? .orange : .cyan)
                }
                .buttonStyle(.plain)
                .help("On-Device Voice Dictation")

                TextField("Ask Local Mac or Hybrid Cloud...", text: $vm.promptText)
                    .textFieldStyle(.roundedBorder)
                    .onChange(of: vm.promptText) { _, _ in
                        vm.updateComposerLiveAudit()
                    }
                Button("Send") {
                    vm.sendChatMessage()
                }
                .buttonStyle(.borderedProminent)
            }

            HStack(spacing: 6) {
                Button("Summarize Clipboard") {
                    vm.runQuickAskAction(
                        instructionPrefix: "Summarize the following content privately on this Mac:",
                        mode: .local
                    )
                }
                .controlSize(.mini)
                Button("Sanitize & Analyze") {
                    vm.runQuickAskAction(
                        instructionPrefix: "Refactor, improve, and analyze the following (with PII masked):",
                        mode: .hybrid
                    )
                }
                .controlSize(.mini)
                Button("Consensus") {
                    vm.runQuickAskAction(
                        instructionPrefix: "Compare perspectives and synthesize a consensus recommendation for:",
                        mode: .hybrid,
                        provider: .consensus
                    )
                }
                .controlSize(.mini)
            }

            if let lastMsg = vm.activeConversation?.messages.last(where: { $0.role == "assistant" }) {
                ScrollView {
                    MarkdownMessageView(markdown: lastMsg.content, isCompact: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(maxHeight: 96)
                .padding(8)
                .background(RoundedRectangle(cornerRadius: 8, style: .continuous).fill(Color.white.opacity(0.06)))
            }

            Divider()

            HStack {
                Button("New Chat") {
                    vm.startNewChat()
                    vm.selectedSection = .chat
                }
                Spacer()
                SettingsLink {
                    Text("Settings…")
                }
                Spacer()
                Button("Open Window") {
                    NSApplication.shared.activate(ignoringOtherApps: true)
                }
                Spacer()
                Button("Quit") {
                    DaemonManager.shared.stop()
                    NSApplication.shared.terminate(nil)
                }
            }
            .font(.caption)
        }
        .padding(12)
        .frame(width: 340)
    }
}

final class MacHybridAppDelegate: NSObject, NSApplicationDelegate {
    func applicationWillTerminate(_ notification: Notification) {
        // Ensure all local MLX / Ollama models, Metal caches, m365-proxy, and the Python daemon quit with the app
        DaemonManager.shared.stop()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            for window in sender.windows {
                window.makeKeyAndOrderFront(nil)
            }
        }
        return true
    }
}

@main
enum MacHybridAIEntrypoint {
    static func main() {
        if let exitCode = AppleFoundationModelsEngine.handleHeadlessCommandIfPresent(
            arguments: CommandLine.arguments
        ) {
            exit(exitCode)
        }
        MacHybridAIApp.main()
    }
}

struct MacHybridAIApp: App {
    @NSApplicationDelegateAdaptor(MacHybridAppDelegate.self) private var appDelegate
    @StateObject private var viewModel = HybridAppViewModel()
    @AppStorage("appAppearance") private var appAppearanceRaw: String = AppAppearanceOption.system.rawValue

    private var preferredColorScheme: ColorScheme? {
        switch AppAppearanceOption(rawValue: appAppearanceRaw) ?? .system {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }

    var body: some Scene {
        WindowGroup("MacHybridAI") {
            MainDashboardView(vm: viewModel)
                .preferredColorScheme(preferredColorScheme)
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .defaultSize(width: 1120, height: 740)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("New Conversation") {
                    viewModel.startNewChat()
                    viewModel.selectedSection = .chat
                }
                .keyboardShortcut("n", modifiers: .command)

                Button("Quick Ask Spotlight…") {
                    viewModel.isShowingQuickAskSpotlight = true
                }
                .keyboardShortcut("k", modifiers: .command)

                Divider()

                Button("Attach Local File…") {
                    viewModel.attachFileViaPanel()
                }
                .keyboardShortcut("o", modifiers: .command)

                Button("Import & Scrub PDF / Image (Vision OCR)…") {
                    viewModel.importAndScrubFileViaVisionOCR()
                }
                .keyboardShortcut("o", modifiers: [.command, .shift])

                Divider()

                Button("Share Active Conversation…") {
                    if let active = viewModel.activeConversation {
                        viewModel.shareConversation(active)
                    }
                }
                .keyboardShortcut("s", modifiers: [.command, .shift])
                .disabled(viewModel.activeConversation?.messages.isEmpty ?? true)
            }

            CommandMenu("Compute") {
                Button("Fully Local Mode") {
                    viewModel.computeMode = .local
                }
                .keyboardShortcut("1", modifiers: .command)

                Button("Smart Auto Mode") {
                    viewModel.computeMode = .auto
                }
                .keyboardShortcut("2", modifiers: .command)

                Button("Hybrid Mode (Privacy Gate + Cloud)") {
                    viewModel.computeMode = .hybrid
                }
                .keyboardShortcut("3", modifiers: .command)

                Divider()

                Toggle(
                    "Approve Sanitized Prompt Before Cloud Dispatch",
                    isOn: $viewModel.approveBeforeCloudDispatch
                )

                Divider()

                Button("Re-Profile Apple Silicon Hardware") {
                    viewModel.refreshHardwareProfile()
                }
                .keyboardShortcut("r", modifiers: [.command, .shift])
            }

            CommandMenu("Navigate") {
                Button("Hybrid Chat") {
                    viewModel.selectedSection = .chat
                }
                .keyboardShortcut("1", modifiers: [.command, .option])

                Button("History & Cloud") {
                    viewModel.selectedSection = .history
                }
                .keyboardShortcut("2", modifiers: [.command, .option])

                Button("Privacy Gate Inspector") {
                    viewModel.selectedSection = .privacyGate
                }
                .keyboardShortcut("3", modifiers: [.command, .option])
            }
        }

        Settings {
            MacHybridSettingsView(vm: viewModel)
                .preferredColorScheme(preferredColorScheme)
        }

        MenuBarExtra {
            MenuBarHybridPanelView(vm: viewModel)
                .preferredColorScheme(preferredColorScheme)
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
