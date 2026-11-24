import Foundation

public enum AppAppearanceOption: String, CaseIterable, Codable, Sendable {
    case system = "system"
    case light = "light"
    case dark = "dark"

    public var displayName: String {
        switch self {
        case .system: return "Match macOS System"
        case .light: return "Light"
        case .dark: return "Dark"
        }
    }
}

public enum MainWorkspaceSection: String, CaseIterable, Hashable, Sendable {
    case chat = "chat"
    case history = "history"
    case privacyGate = "privacy_gate"

    public var title: String {
        switch self {
        case .chat: return "Hybrid Chat"
        case .history: return "History & iCloud"
        case .privacyGate: return "Privacy Gate"
        }
    }

    public var iconName: String {
        switch self {
        case .chat: return "bubble.left.and.text.bubble.right"
        case .history: return "clock.arrow.circlepath"
        case .privacyGate: return "key.viewfinder"
        }
    }
}

public enum ComputeModeOption: String, CaseIterable, Codable, Sendable {
    case local = "local"
    case auto = "auto"
    case hybrid = "hybrid"

    public var title: String {
        switch self {
        case .local: return "Fully local"
        case .auto: return "Smart Auto"
        case .hybrid: return "Hybrid"
        }
    }

    public var subtitle: String {
        switch self {
        case .local:
            return "Model and agent run on this Mac. Nothing leaves this Mac."
        case .auto:
            return "Adaptive router keeps high-sensitivity or simple queries 100% local, and routes complex reasoning via 4-Station Hybrid."
        case .hybrid:
            return "Privacy Gate masks PII on your Mac before stateless cloud research, then restores real values."
        }
    }
}

public enum CustomCloudProtocolOption: String, CaseIterable, Codable, Sendable {
    case openai = "openai"
    case anthropic = "anthropic"

    public var displayName: String {
        switch self {
        case .openai: return "OpenAI Compatible (/chat/completions)"
        case .anthropic: return "Anthropic Messages (/v1/messages)"
        }
    }
}

public enum LocalBackendOption: String, CaseIterable, Codable, Sendable {
    case appleFoundationModels = "apple_fm"
    case mlx = "mlx"
    case litert = "litert"
    case ollama = "ollama"

    public var displayName: String {
        switch self {
        case .appleFoundationModels:
            return "Apple Foundation Models (Apple-Signed · Zero Hugging Face)"
        case .mlx:
            return "Apple Silicon MLX (Verified Local / First-Party Weights)"
        case .litert:
            return "Google LiteRT-LM (Local .litertlm Bundle)"
        case .ollama:
            return "Ollama Local Server (127.0.0.1:11434)"
        }
    }

    public var trustBadge: String {
        switch self {
        case .appleFoundationModels: return "Apple-Signed OS Model"
        case .mlx: return "Local MLX (Supply-Chain Audited)"
        case .litert: return "Local Offline Bundle"
        case .ollama: return "Local Loopback Server"
        }
    }
}

public enum CloudProviderOption: String, CaseIterable, Codable, Sendable {
    case gemini = "gemini"
    case openai = "openai"
    case anthropic = "anthropic"
    case antigravity = "antigravity"
    case m365Copilot = "m365_copilot"
    case openRouter = "openrouter"
    case xai = "xai"
    case groq = "groq"
    case deepseek = "deepseek"
    case mistral = "mistral"
    case perplexity = "perplexity"
    case together = "together"
    case openAICompatible = "openai_compatible"
    case consensus = "consensus"

    public var displayName: String {
        switch self {
        case .gemini: return "Google Gemini (gemini-3.8-flash)"
        case .openai: return "OpenAI (gpt-4.1 / o3-mini)"
        case .anthropic: return "Anthropic Claude (claude-sonnet-4-5)"
        case .antigravity: return "Google Antigravity Agent"
        case .m365Copilot: return "M365 Copilot Proxy (gpt-5.5-think-deeper)"
        case .openRouter: return "OpenRouter (300+ Cloud Models)"
        case .xai: return "xAI Grok (grok-3)"
        case .groq: return "Groq LPU (llama-3.3-70b)"
        case .deepseek: return "DeepSeek (deepseek-reasoner)"
        case .mistral: return "Mistral AI (mistral-large)"
        case .perplexity: return "Perplexity Sonar (sonar-pro)"
        case .together: return "Together AI (Llama 3.3 70B)"
        case .openAICompatible: return "Custom Any Cloud AI (OpenAI / Anthropic / Azure)"
        case .consensus: return "Multi-Cloud Consensus (Gemini + Claude + OpenAI)"
        }
    }

    public var shortName: String {
        switch self {
        case .gemini: return "Gemini"
        case .openai: return "OpenAI"
        case .anthropic: return "Claude"
        case .antigravity: return "Antigravity"
        case .m365Copilot: return "M365 Copilot"
        case .openRouter: return "OpenRouter"
        case .xai: return "xAI Grok"
        case .groq: return "Groq"
        case .deepseek: return "DeepSeek"
        case .mistral: return "Mistral"
        case .perplexity: return "Perplexity"
        case .together: return "Together"
        case .openAICompatible: return "Custom API"
        case .consensus: return "Consensus"
        }
    }

    public var defaultBaseURL: String {
        switch self {
        case .gemini, .antigravity: return "https://generativelanguage.googleapis.com"
        case .openai: return "https://api.openai.com/v1"
        case .anthropic: return "https://api.anthropic.com/v1"
        case .m365Copilot: return "http://127.0.0.1:4141/v1"
        case .openRouter: return "https://openrouter.ai/api/v1"
        case .xai: return "https://api.x.ai/v1"
        case .groq: return "https://api.groq.com/openai/v1"
        case .deepseek: return "https://api.deepseek.com/v1"
        case .mistral: return "https://api.mistral.ai/v1"
        case .perplexity: return "https://api.perplexity.ai"
        case .together: return "https://api.together.xyz/v1"
        case .openAICompatible: return "https://api.openai.com/v1"
        case .consensus: return "multi-cloud"
        }
    }

    public var defaultModel: String {
        switch self {
        case .gemini: return "gemini-3.8-flash"
        case .openai: return "gpt-4.1"
        case .anthropic: return "claude-sonnet-4-5"
        case .antigravity: return "antigravity-preview-05-2026"
        case .m365Copilot: return "gpt-5.5-think-deeper"
        case .openRouter: return "anthropic/claude-sonnet-4.5"
        case .xai: return "grok-3"
        case .groq: return "llama-3.3-70b-versatile"
        case .deepseek: return "deepseek-reasoner"
        case .mistral: return "mistral-large-latest"
        case .perplexity: return "sonar-pro"
        case .together: return "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        case .openAICompatible: return "gpt-4.1"
        case .consensus: return "gemini + anthropic + openai"
        }
    }

    public var apiKeyEnvName: String {
        switch self {
        case .gemini, .antigravity: return "GEMINI_API_KEY"
        case .openai, .openAICompatible: return "OPENAI_API_KEY"
        case .anthropic: return "ANTHROPIC_API_KEY"
        case .m365Copilot: return "M365_SECRETS_FILE"
        case .openRouter: return "OPENROUTER_API_KEY"
        case .xai: return "XAI_API_KEY"
        case .groq: return "GROQ_API_KEY"
        case .deepseek: return "DEEPSEEK_API_KEY"
        case .mistral: return "MISTRAL_API_KEY"
        case .perplexity: return "PERPLEXITY_API_KEY"
        case .together: return "TOGETHER_API_KEY"
        case .consensus: return "GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY"
        }
    }
}

public enum GuardianPolicyOption: String, CaseIterable, Codable, Sendable {
    case reversibleMask = "reversible_mask"
    case strictRedact = "strict_redact"
    case forceLocalOnPII = "force_local_on_pii"

    public var displayName: String {
        switch self {
        case .reversibleMask: return "Reversible Mask & Restore (Privacy Gate)"
        case .strictRedact: return "Strict Redact Only ([REDACTED])"
        case .forceLocalOnPII: return "Force Local Execution on PII"
        }
    }
}

public enum HistoryStorageOption: String, CaseIterable, Codable, Sendable {
    case localMac = "local"
    case iCloudDrive = "icloud"

    public var title: String {
        switch self {
        case .localMac: return "On This Mac Only"
        case .iCloudDrive: return "iCloud Drive"
        }
    }

    public var subtitle: String {
        switch self {
        case .localMac:
            return "~/Library/Application Support/MacHybridAI/history"
        case .iCloudDrive:
            return "~/Library/Mobile Documents/com~apple~CloudDocs/MacHybridAI"
        }
    }

    public var iconName: String {
        switch self {
        case .localMac: return "internaldrive.fill"
        case .iCloudDrive: return "icloud.and.arrow.up.fill"
        }
    }
}

public enum HistoryRetentionOption: String, CaseIterable, Codable, Sendable {
    case hours24 = "24h"
    case days7 = "7d"
    case days30 = "30d"
    case days90 = "90d"
    case neverDelete = "never"

    public var displayName: String {
        switch self {
        case .hours24: return "Auto-Delete After 24 Hours"
        case .days7: return "Auto-Delete After 7 Days"
        case .days30: return "Auto-Delete After 30 Days"
        case .days90: return "Auto-Delete After 90 Days"
        case .neverDelete: return "Never Delete (Keep Forever)"
        }
    }

    public var shortBadge: String {
        switch self {
        case .hours24: return "24h TTL"
        case .days7: return "7d TTL"
        case .days30: return "30d TTL"
        case .days90: return "90d TTL"
        case .neverDelete: return "Never Delete"
        }
    }

    public var ttlSeconds: TimeInterval? {
        switch self {
        case .hours24: return 24 * 3600
        case .days7: return 7 * 24 * 3600
        case .days30: return 30 * 24 * 3600
        case .days90: return 90 * 24 * 3600
        case .neverDelete: return nil
        }
    }

    public func computeExpiryDate(from baseDate: Date = Date()) -> Date? {
        guard let ttl = ttlSeconds else { return nil }
        return baseDate.addingTimeInterval(ttl)
    }
}

public struct StationStepModel: Identifiable, Codable, Sendable, Equatable {
    public var id: Int { stationIndex }
    public let stationIndex: Int
    public let stationId: String
    public let label: String
    public let locality: String
    public let title: String
    public let detail: String
    public let status: String
    public let durationMs: Int
    public let badges: [String]

    public init(
        stationIndex: Int,
        stationId: String,
        label: String,
        locality: String,
        title: String,
        detail: String,
        status: String,
        durationMs: Int,
        badges: [String]
    ) {
        self.stationIndex = stationIndex
        self.stationId = stationId
        self.label = label
        self.locality = locality
        self.title = title
        self.detail = detail
        self.status = status
        self.durationMs = durationMs
        self.badges = badges
    }

    enum CodingKeys: String, CodingKey {
        case stationIndex = "station_index"
        case stationId = "station_id"
        case label
        case locality
        case title
        case detail
        case status
        case durationMs = "duration_ms"
        case badges
    }
}

public struct ExecutionReceiptModel: Codable, Sendable, Equatable {
    public let modeExecuted: String
    public let localModelUsed: String
    public let localAgentLocation: String
    public let cloudModelsUsed: String
    public let piiFlaggedCount: Int
    public let piiRestoredCount: Int
    public let piiCategories: [String]
    public let nothingLeftMac: Bool
    public let cloudZeroRetention: Bool
    public let outboundPayloadSha256: String
    public let receiptSignatureSha256: String

    public init(
        modeExecuted: String,
        localModelUsed: String,
        localAgentLocation: String,
        cloudModelsUsed: String,
        piiFlaggedCount: Int,
        piiRestoredCount: Int,
        piiCategories: [String],
        nothingLeftMac: Bool,
        cloudZeroRetention: Bool = true,
        outboundPayloadSha256: String = "local_only_no_outbound_payload",
        receiptSignatureSha256: String = "verified_on_device"
    ) {
        self.modeExecuted = modeExecuted
        self.localModelUsed = localModelUsed
        self.localAgentLocation = localAgentLocation
        self.cloudModelsUsed = cloudModelsUsed
        self.piiFlaggedCount = piiFlaggedCount
        self.piiRestoredCount = piiRestoredCount
        self.piiCategories = piiCategories
        self.nothingLeftMac = nothingLeftMac
        self.cloudZeroRetention = cloudZeroRetention
        self.outboundPayloadSha256 = outboundPayloadSha256
        self.receiptSignatureSha256 = receiptSignatureSha256
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        modeExecuted = try container.decode(String.self, forKey: .modeExecuted)
        localModelUsed = try container.decode(String.self, forKey: .localModelUsed)
        localAgentLocation = try container.decode(String.self, forKey: .localAgentLocation)
        cloudModelsUsed = try container.decode(String.self, forKey: .cloudModelsUsed)
        piiFlaggedCount = try container.decode(Int.self, forKey: .piiFlaggedCount)
        piiRestoredCount = try container.decode(Int.self, forKey: .piiRestoredCount)
        piiCategories = try container.decode([String].self, forKey: .piiCategories)
        nothingLeftMac = try container.decode(Bool.self, forKey: .nothingLeftMac)
        cloudZeroRetention = try container.decodeIfPresent(Bool.self, forKey: .cloudZeroRetention) ?? true
        outboundPayloadSha256 = try container.decodeIfPresent(String.self, forKey: .outboundPayloadSha256) ?? "local_only_no_outbound_payload"
        receiptSignatureSha256 = try container.decodeIfPresent(String.self, forKey: .receiptSignatureSha256) ?? "verified_on_device"
    }

    enum CodingKeys: String, CodingKey {
        case modeExecuted = "mode_executed"
        case localModelUsed = "local_model_used"
        case localAgentLocation = "local_agent_location"
        case cloudModelsUsed = "cloud_models_used"
        case piiFlaggedCount = "pii_flagged_count"
        case piiRestoredCount = "pii_restored_count"
        case piiCategories = "pii_categories"
        case nothingLeftMac = "nothing_left_mac"
        case cloudZeroRetention = "cloud_zero_retention"
        case outboundPayloadSha256 = "outbound_payload_sha256"
        case receiptSignatureSha256 = "receipt_signature_sha256"
    }
}

public struct TelemetryModel: Codable, Sendable, Equatable {
    public let architecture: String
    public let chipBrand: String
    public let cpuPercent: Int
    public let memoryPercent: Int
    public let gpuPercent: Int
    public let tokensProcessed: Int
    public let unifiedMemoryGb: Int

    public init(
        architecture: String,
        chipBrand: String,
        cpuPercent: Int,
        memoryPercent: Int,
        gpuPercent: Int,
        tokensProcessed: Int,
        unifiedMemoryGb: Int
    ) {
        self.architecture = architecture
        self.chipBrand = chipBrand
        self.cpuPercent = cpuPercent
        self.memoryPercent = memoryPercent
        self.gpuPercent = gpuPercent
        self.tokensProcessed = tokensProcessed
        self.unifiedMemoryGb = unifiedMemoryGb
    }

    enum CodingKeys: String, CodingKey {
        case architecture
        case chipBrand = "chip_brand"
        case cpuPercent = "cpu_percent"
        case memoryPercent = "memory_percent"
        case gpuPercent = "gpu_percent"
        case tokensProcessed = "tokens_processed"
        case unifiedMemoryGb = "unified_memory_gb"
    }
}

public struct PIIEntityModel: Identifiable, Codable, Sendable, Equatable {
    public var id: String { "\(replacementToken)-\(start)-\(end)" }
    public let category: String
    public let replacementToken: String
    public let start: Int
    public let end: Int
    public let confidence: Double
    public let maskedPreview: String

    public init(
        category: String,
        replacementToken: String,
        start: Int,
        end: Int,
        confidence: Double,
        maskedPreview: String
    ) {
        self.category = category
        self.replacementToken = replacementToken
        self.start = start
        self.end = end
        self.confidence = confidence
        self.maskedPreview = maskedPreview
    }

    enum CodingKeys: String, CodingKey {
        case category
        case replacementToken = "replacement_token"
        case start
        case end
        case confidence
        case maskedPreview = "masked_preview"
    }
}

public struct GuardianAuditModel: Codable, Sendable, Equatable {
    public let sanitizedText: String
    public let piiFlagged: Bool
    public let piiCount: Int
    public let categories: [String]
    public let policyApplied: String
    public let forcedLocal: Bool
    public let entities: [PIIEntityModel]
    public let restoredPreview: String?
    public let restoredCount: Int?

    public init(
        sanitizedText: String,
        piiFlagged: Bool,
        piiCount: Int,
        categories: [String],
        policyApplied: String,
        forcedLocal: Bool,
        entities: [PIIEntityModel],
        restoredPreview: String?,
        restoredCount: Int?
    ) {
        self.sanitizedText = sanitizedText
        self.piiFlagged = piiFlagged
        self.piiCount = piiCount
        self.categories = categories
        self.policyApplied = policyApplied
        self.forcedLocal = forcedLocal
        self.entities = entities
        self.restoredPreview = restoredPreview
        self.restoredCount = restoredCount
    }

    enum CodingKeys: String, CodingKey {
        case sanitizedText = "sanitized_text"
        case piiFlagged = "pii_flagged"
        case piiCount = "pii_count"
        case categories
        case policyApplied = "policy_applied"
        case forcedLocal = "forced_local"
        case entities
        case restoredPreview = "restored_preview"
        case restoredCount = "restored_count"
    }
}

public struct TaskResultModel: Codable, Sendable, Equatable {
    public let taskId: String
    public let sessionId: String?
    public let prompt: String
    public let finalOutput: String
    public let cloudPromptSent: String?
    public let stations: [StationStepModel]
    public let receipt: ExecutionReceiptModel
    public let telemetry: TelemetryModel
    public let guardianAudit: GuardianAuditModel

    public init(
        taskId: String,
        sessionId: String? = nil,
        prompt: String,
        finalOutput: String,
        cloudPromptSent: String?,
        stations: [StationStepModel],
        receipt: ExecutionReceiptModel,
        telemetry: TelemetryModel,
        guardianAudit: GuardianAuditModel
    ) {
        self.taskId = taskId
        self.sessionId = sessionId
        self.prompt = prompt
        self.finalOutput = finalOutput
        self.cloudPromptSent = cloudPromptSent
        self.stations = stations
        self.receipt = receipt
        self.telemetry = telemetry
        self.guardianAudit = guardianAudit
    }

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case sessionId = "session_id"
        case prompt
        case finalOutput = "final_output"
        case cloudPromptSent = "cloud_prompt_sent"
        case stations
        case receipt
        case telemetry
        case guardianAudit = "guardian_audit"
    }
}

public struct ChatMessageModel: Identifiable, Codable, Sendable, Equatable {
    public let id: String
    public let role: String // "user" | "assistant"
    public var content: String          // var — filled incrementally during streaming
    public let createdAt: Date
    public let computeMode: String
    public let cloudProvider: String
    public var sanitizedCloudPrompt: String?   // var — attached after stream completes
    public let piiMaskedCount: Int
    public let piiRestoredCount: Int
    public var stations: [StationStepModel]    // var — attached after stream completes
    public var receipt: ExecutionReceiptModel? // var — attached after stream completes
    public var telemetry: TelemetryModel?      // var — attached after stream completes
    public let cloudZeroRetention: Bool
    /// True while the assistant message is still receiving tokens from the MLX stream.
    public var isStreaming: Bool

    public init(
        id: String = UUID().uuidString,
        role: String,
        content: String,
        createdAt: Date = Date(),
        computeMode: String = "hybrid",
        cloudProvider: String = "gemini",
        sanitizedCloudPrompt: String? = nil,
        piiMaskedCount: Int = 0,
        piiRestoredCount: Int = 0,
        stations: [StationStepModel] = [],
        receipt: ExecutionReceiptModel? = nil,
        telemetry: TelemetryModel? = nil,
        cloudZeroRetention: Bool = true,
        isStreaming: Bool = false
    ) {
        self.id = id
        self.role = role
        self.content = content
        self.createdAt = createdAt
        self.computeMode = computeMode
        self.cloudProvider = cloudProvider
        self.sanitizedCloudPrompt = sanitizedCloudPrompt
        self.piiMaskedCount = piiMaskedCount
        self.piiRestoredCount = piiRestoredCount
        self.stations = stations
        self.receipt = receipt
        self.telemetry = telemetry
        self.cloudZeroRetention = cloudZeroRetention
        self.isStreaming = isStreaming
    }
}

public struct ChatConversationModel: Identifiable, Codable, Sendable, Equatable {
    public let id: String
    public var title: String
    public let createdAt: Date
    public var updatedAt: Date
    public var storageLocation: HistoryStorageOption
    public var retentionPolicy: HistoryRetentionOption
    public var expiresAt: Date?
    public var messages: [ChatMessageModel]

    public init(
        id: String = "chat_\(UUID().uuidString.prefix(8))",
        title: String,
        createdAt: Date = Date(),
        updatedAt: Date = Date(),
        storageLocation: HistoryStorageOption = .localMac,
        retentionPolicy: HistoryRetentionOption = .days30,
        expiresAt: Date? = nil,
        messages: [ChatMessageModel] = []
    ) {
        self.id = id
        self.title = title
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.storageLocation = storageLocation
        self.retentionPolicy = retentionPolicy
        self.expiresAt = expiresAt ?? retentionPolicy.computeExpiryDate(from: updatedAt)
        self.messages = messages
    }

    public func isExpired(at date: Date = Date()) -> Bool {
        if retentionPolicy == .neverDelete {
            return false
        }
        guard let exp = expiresAt else {
            return false
        }
        return date >= exp
    }

    public var expirationSummary: String {
        if retentionPolicy == .neverDelete {
            return "Never auto-deletes"
        }
        guard let exp = expiresAt else {
            return retentionPolicy.shortBadge
        }
        let remaining = exp.timeIntervalSinceNow
        if remaining <= 0 {
            return "Expired"
        }
        let hours = Int(remaining / 3600)
        if hours < 48 {
            return "Auto-deletes in \(max(1, hours))h"
        }
        let days = Int(remaining / 86400)
        return "Auto-deletes in \(days)d"
    }
}

// MARK: - Apple Silicon Hardware Profiler & Model Sizing Models

public struct CachedModelStatusModel: Identifiable, Codable, Sendable, Equatable {
    public var id: String { modelId }
    public let modelId: String
    public let backend: String
    public let parameterCount: String
    public let quantization: String
    public let estimatedMemoryGb: Double
    public let isCached: Bool
    public let isComplete: Bool
    public let sizeBytes: Int
    public let localPath: String
    public let missingShards: Int
    public let publisherTrust: String
    public let isPinned: Bool
    public let isUsable: Bool
    public let usabilityNote: String

    public var sizeGbFormatted: String {
        guard sizeBytes > 0 else { return String(format: "~%.1f GB", estimatedMemoryGb) }
        return String(format: "%.2f GB", Double(sizeBytes) / 1_073_741_824.0)
    }

    public var trustDisplayLabel: String {
        switch publisherTrust {
        case "apple_signed": return "Apple-Signed"
        case "local_verified_dir": return "Verified Local Folder"
        case "first_party": return "First-Party"
        default: return isPinned ? "SHA-256 Pinned" : "Community HF"
        }
    }

    public init(
        modelId: String,
        backend: String,
        parameterCount: String,
        quantization: String,
        estimatedMemoryGb: Double,
        isCached: Bool,
        isComplete: Bool,
        sizeBytes: Int,
        localPath: String,
        missingShards: Int = 0,
        publisherTrust: String = "community_unverified",
        isPinned: Bool = false,
        isUsable: Bool = true,
        usabilityNote: String = ""
    ) {
        self.modelId = modelId
        self.backend = backend
        self.parameterCount = parameterCount
        self.quantization = quantization
        self.estimatedMemoryGb = estimatedMemoryGb
        self.isCached = isCached
        self.isComplete = isComplete
        self.sizeBytes = sizeBytes
        self.localPath = localPath
        self.missingShards = missingShards
        self.publisherTrust = publisherTrust
        self.isPinned = isPinned
        self.isUsable = isUsable
        self.usabilityNote = usabilityNote
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        modelId = try c.decode(String.self, forKey: .modelId)
        backend = try c.decode(String.self, forKey: .backend)
        parameterCount = try c.decode(String.self, forKey: .parameterCount)
        quantization = try c.decode(String.self, forKey: .quantization)
        estimatedMemoryGb = try c.decode(Double.self, forKey: .estimatedMemoryGb)
        isCached = try c.decode(Bool.self, forKey: .isCached)
        isComplete = try c.decode(Bool.self, forKey: .isComplete)
        sizeBytes = try c.decode(Int.self, forKey: .sizeBytes)
        localPath = try c.decode(String.self, forKey: .localPath)
        missingShards = try c.decodeIfPresent(Int.self, forKey: .missingShards) ?? 0
        publisherTrust = try c.decodeIfPresent(String.self, forKey: .publisherTrust) ?? "community_unverified"
        isPinned = try c.decodeIfPresent(Bool.self, forKey: .isPinned) ?? false
        isUsable = try c.decodeIfPresent(Bool.self, forKey: .isUsable) ?? isComplete
        usabilityNote = try c.decodeIfPresent(String.self, forKey: .usabilityNote) ?? ""
    }

    enum CodingKeys: String, CodingKey {
        case modelId = "model_id"
        case backend
        case parameterCount = "parameter_count"
        case quantization
        case estimatedMemoryGb = "estimated_memory_gb"
        case isCached = "is_cached"
        case isComplete = "is_complete"
        case sizeBytes = "size_bytes"
        case localPath = "local_path"
        case missingShards = "missing_shards"
        case publisherTrust = "publisher_trust"
        case isPinned = "is_pinned"
        case isUsable = "is_usable"
        case usabilityNote = "usability_note"
    }
}

public struct ModelRecommendationModel: Identifiable, Codable, Sendable, Equatable {
    public var id: String { modelId }
    public let role: String
    public let modelId: String
    public let parameterCount: String
    public let quantization: String
    public let estimatedMemoryGb: Double
    public let expectedTpsRange: String
    public let recommendedKvBits: Int?
    public let fitsInMetalBudget: Bool
    public let isReadyLocally: Bool
    public let rationale: String

    public init(
        role: String,
        modelId: String,
        parameterCount: String,
        quantization: String,
        estimatedMemoryGb: Double,
        expectedTpsRange: String,
        recommendedKvBits: Int?,
        fitsInMetalBudget: Bool,
        isReadyLocally: Bool,
        rationale: String
    ) {
        self.role = role
        self.modelId = modelId
        self.parameterCount = parameterCount
        self.quantization = quantization
        self.estimatedMemoryGb = estimatedMemoryGb
        self.expectedTpsRange = expectedTpsRange
        self.recommendedKvBits = recommendedKvBits
        self.fitsInMetalBudget = fitsInMetalBudget
        self.isReadyLocally = isReadyLocally
        self.rationale = rationale
    }

    enum CodingKeys: String, CodingKey {
        case role
        case modelId = "model_id"
        case parameterCount = "parameter_count"
        case quantization
        case estimatedMemoryGb = "estimated_memory_gb"
        case expectedTpsRange = "expected_tps_range"
        case recommendedKvBits = "recommended_kv_bits"
        case fitsInMetalBudget = "fits_in_metal_budget"
        case isReadyLocally = "is_ready_locally"
        case rationale
    }
}

public struct HardwareBenchmarkResultModel: Codable, Sendable, Equatable {
    public let modelId: String
    public let backend: String
    public let ttftMs: Double
    public let prefillTps: Double
    public let decodeTps: Double
    public let peakMemoryGb: Double
    public let tokensGenerated: Int
    public let durationMs: Int
    public let thermalState: String
    public let memoryPressurePct: Int
    public let guardrailActive: Bool
    public let guardrailReason: String

    public init(
        modelId: String,
        backend: String,
        ttftMs: Double,
        prefillTps: Double,
        decodeTps: Double,
        peakMemoryGb: Double,
        tokensGenerated: Int,
        durationMs: Int,
        thermalState: String = "nominal",
        memoryPressurePct: Int = 40,
        guardrailActive: Bool = false,
        guardrailReason: String = ""
    ) {
        self.modelId = modelId
        self.backend = backend
        self.ttftMs = ttftMs
        self.prefillTps = prefillTps
        self.decodeTps = decodeTps
        self.peakMemoryGb = peakMemoryGb
        self.tokensGenerated = tokensGenerated
        self.durationMs = durationMs
        self.thermalState = thermalState
        self.memoryPressurePct = memoryPressurePct
        self.guardrailActive = guardrailActive
        self.guardrailReason = guardrailReason
    }

    enum CodingKeys: String, CodingKey {
        case modelId = "model_id"
        case backend
        case ttftMs = "ttft_ms"
        case prefillTps = "prefill_tps"
        case decodeTps = "decode_tps"
        case peakMemoryGb = "peak_memory_gb"
        case tokensGenerated = "tokens_generated"
        case durationMs = "duration_ms"
        case thermalState = "thermal_state"
        case memoryPressurePct = "memory_pressure_pct"
        case guardrailActive = "guardrail_active"
        case guardrailReason = "guardrail_reason"
    }
}

public struct ModelPullResultModel: Codable, Sendable, Equatable {
    public let ok: Bool
    public let modelId: String
    public let backend: String
    public let isCached: Bool
    public let isComplete: Bool
    public let sizeGb: Double
    public let missingShards: Int
    public let status: String
    public let message: String
    public let cliCommand: String

    public init(
        ok: Bool,
        modelId: String,
        backend: String,
        isCached: Bool,
        isComplete: Bool,
        sizeGb: Double,
        missingShards: Int,
        status: String,
        message: String,
        cliCommand: String
    ) {
        self.ok = ok
        self.modelId = modelId
        self.backend = backend
        self.isCached = isCached
        self.isComplete = isComplete
        self.sizeGb = sizeGb
        self.missingShards = missingShards
        self.status = status
        self.message = message
        self.cliCommand = cliCommand
    }

    enum CodingKeys: String, CodingKey {
        case ok
        case modelId = "model_id"
        case backend
        case isCached = "is_cached"
        case isComplete = "is_complete"
        case sizeGb = "size_gb"
        case missingShards = "missing_shards"
        case status
        case message
        case cliCommand = "cli_command"
    }
}

public struct MacHardwareProfileModel: Codable, Sendable, Equatable {
    public let architecture: String
    public let chipBrand: String
    public let cpuCoresTotal: Int
    public let cpuCoresPerformance: Int
    public let cpuCoresEfficiency: Int
    public let gpuCores: Int
    public let gpuArchitecture: String
    public let metalAvailable: Bool
    public let mlxAvailable: Bool
    public let unifiedMemoryGb: Int
    public let metalWorkingSetGb: Double
    public let metalMaxBufferGb: Double
    public let memoryUsedPercent: Int
    public let availableMemoryGb: Double
    public let cpuBusyPercent: Int
    public let gpuBusyPercent: Int
    public let gpuRendererPercent: Int
    public let gpuTilerPercent: Int
    public let gpuInUseMemoryGb: Double
    public let hardwareTier: String
    public let selectedLocalModel: String
    public let selectedFastModel: String
    public let recommendedKvBits: Int?
    public let thermalState: String
    public let memoryPressureLevel: String
    public let guardrailTriggered: Bool
    public let guardrailReason: String
    public let cachedModels: [CachedModelStatusModel]
    public let recommendations: [ModelRecommendationModel]

    public init(
        architecture: String,
        chipBrand: String,
        cpuCoresTotal: Int,
        cpuCoresPerformance: Int,
        cpuCoresEfficiency: Int,
        gpuCores: Int,
        gpuArchitecture: String,
        metalAvailable: Bool,
        mlxAvailable: Bool,
        unifiedMemoryGb: Int,
        metalWorkingSetGb: Double,
        metalMaxBufferGb: Double,
        memoryUsedPercent: Int,
        availableMemoryGb: Double,
        cpuBusyPercent: Int,
        gpuBusyPercent: Int,
        gpuRendererPercent: Int,
        gpuTilerPercent: Int,
        gpuInUseMemoryGb: Double,
        hardwareTier: String,
        selectedLocalModel: String,
        selectedFastModel: String,
        recommendedKvBits: Int?,
        thermalState: String = "nominal",
        memoryPressureLevel: String = "normal",
        guardrailTriggered: Bool = false,
        guardrailReason: String = "",
        cachedModels: [CachedModelStatusModel],
        recommendations: [ModelRecommendationModel]
    ) {
        self.architecture = architecture
        self.chipBrand = chipBrand
        self.cpuCoresTotal = cpuCoresTotal
        self.cpuCoresPerformance = cpuCoresPerformance
        self.cpuCoresEfficiency = cpuCoresEfficiency
        self.gpuCores = gpuCores
        self.gpuArchitecture = gpuArchitecture
        self.metalAvailable = metalAvailable
        self.mlxAvailable = mlxAvailable
        self.unifiedMemoryGb = unifiedMemoryGb
        self.metalWorkingSetGb = metalWorkingSetGb
        self.metalMaxBufferGb = metalMaxBufferGb
        self.memoryUsedPercent = memoryUsedPercent
        self.availableMemoryGb = availableMemoryGb
        self.cpuBusyPercent = cpuBusyPercent
        self.gpuBusyPercent = gpuBusyPercent
        self.gpuRendererPercent = gpuRendererPercent
        self.gpuTilerPercent = gpuTilerPercent
        self.gpuInUseMemoryGb = gpuInUseMemoryGb
        self.hardwareTier = hardwareTier
        self.selectedLocalModel = selectedLocalModel
        self.selectedFastModel = selectedFastModel
        self.recommendedKvBits = recommendedKvBits
        self.thermalState = thermalState
        self.memoryPressureLevel = memoryPressureLevel
        self.guardrailTriggered = guardrailTriggered
        self.guardrailReason = guardrailReason
        self.cachedModels = cachedModels
        self.recommendations = recommendations
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        architecture = try container.decode(String.self, forKey: .architecture)
        chipBrand = try container.decode(String.self, forKey: .chipBrand)
        cpuCoresTotal = try container.decode(Int.self, forKey: .cpuCoresTotal)
        cpuCoresPerformance = try container.decode(Int.self, forKey: .cpuCoresPerformance)
        cpuCoresEfficiency = try container.decode(Int.self, forKey: .cpuCoresEfficiency)
        gpuCores = try container.decode(Int.self, forKey: .gpuCores)
        gpuArchitecture = try container.decode(String.self, forKey: .gpuArchitecture)
        metalAvailable = try container.decode(Bool.self, forKey: .metalAvailable)
        mlxAvailable = try container.decode(Bool.self, forKey: .mlxAvailable)
        unifiedMemoryGb = try container.decode(Int.self, forKey: .unifiedMemoryGb)
        metalWorkingSetGb = try container.decode(Double.self, forKey: .metalWorkingSetGb)
        metalMaxBufferGb = try container.decode(Double.self, forKey: .metalMaxBufferGb)
        memoryUsedPercent = try container.decode(Int.self, forKey: .memoryUsedPercent)
        availableMemoryGb = try container.decode(Double.self, forKey: .availableMemoryGb)
        cpuBusyPercent = try container.decode(Int.self, forKey: .cpuBusyPercent)
        gpuBusyPercent = try container.decode(Int.self, forKey: .gpuBusyPercent)
        gpuRendererPercent = try container.decode(Int.self, forKey: .gpuRendererPercent)
        gpuTilerPercent = try container.decode(Int.self, forKey: .gpuTilerPercent)
        gpuInUseMemoryGb = try container.decode(Double.self, forKey: .gpuInUseMemoryGb)
        hardwareTier = try container.decode(String.self, forKey: .hardwareTier)
        selectedLocalModel = try container.decode(String.self, forKey: .selectedLocalModel)
        selectedFastModel = try container.decode(String.self, forKey: .selectedFastModel)
        recommendedKvBits = try container.decodeIfPresent(Int.self, forKey: .recommendedKvBits)
        thermalState = try container.decodeIfPresent(String.self, forKey: .thermalState) ?? "nominal"
        memoryPressureLevel = try container.decodeIfPresent(String.self, forKey: .memoryPressureLevel) ?? "normal"
        guardrailTriggered = try container.decodeIfPresent(Bool.self, forKey: .guardrailTriggered) ?? false
        guardrailReason = try container.decodeIfPresent(String.self, forKey: .guardrailReason) ?? ""
        cachedModels = try container.decodeIfPresent([CachedModelStatusModel].self, forKey: .cachedModels) ?? []
        recommendations = try container.decodeIfPresent([ModelRecommendationModel].self, forKey: .recommendations) ?? []
    }

    enum CodingKeys: String, CodingKey {
        case architecture
        case chipBrand = "chip_brand"
        case cpuCoresTotal = "cpu_cores_total"
        case cpuCoresPerformance = "cpu_cores_performance"
        case cpuCoresEfficiency = "cpu_cores_efficiency"
        case gpuCores = "gpu_cores"
        case gpuArchitecture = "gpu_architecture"
        case metalAvailable = "metal_available"
        case mlxAvailable = "mlx_available"
        case unifiedMemoryGb = "unified_memory_gb"
        case metalWorkingSetGb = "metal_working_set_gb"
        case metalMaxBufferGb = "metal_max_buffer_gb"
        case memoryUsedPercent = "memory_used_percent"
        case availableMemoryGb = "available_memory_gb"
        case cpuBusyPercent = "cpu_busy_percent"
        case gpuBusyPercent = "gpu_busy_percent"
        case gpuRendererPercent = "gpu_renderer_percent"
        case gpuTilerPercent = "gpu_tiler_percent"
        case gpuInUseMemoryGb = "gpu_in_use_memory_gb"
        case hardwareTier = "hardware_tier"
        case selectedLocalModel = "selected_local_model"
        case selectedFastModel = "selected_fast_model"
        case recommendedKvBits = "recommended_kv_bits"
        case thermalState = "thermal_state"
        case memoryPressureLevel = "memory_pressure_level"
        case guardrailTriggered = "guardrail_triggered"
        case guardrailReason = "guardrail_reason"
        case cachedModels = "cached_models"
        case recommendations
    }
}

// MARK: - Rich Markdown Parser for Chat Responses

public struct OrderedListItem: Sendable, Equatable {
    public let marker: String
    public let text: String

    public init(marker: String, text: String) {
        self.marker = marker
        self.text = text
    }
}

public enum MarkdownBlock: Sendable, Equatable {
    case heading(level: Int, text: String)
    case paragraph(text: String)
    case codeBlock(language: String, code: String)
    case bulletList(items: [String])
    case orderedList(items: [OrderedListItem])
    case blockquote(text: String)
    case table(headers: [String], rows: [[String]])
    case divider
}

public enum MarkdownBlockParser {
    private static let cacheLock = NSLock()
    nonisolated(unsafe) private static var blockCache: [String: [MarkdownBlock]] = [:]
    nonisolated(unsafe) private static var inlineCache: [String: AttributedString] = [:]
    private static let tableSeparatorAllowedScalars = CharacterSet(charactersIn: "|-: ")
    private static let inlineParseOptions = AttributedString.MarkdownParsingOptions(
        allowsExtendedAttributes: true,
        interpretedSyntax: .inlineOnlyPreservingWhitespace,
        failurePolicy: .returnPartiallyParsedIfPossible
    )

    /// Parses a raw Markdown string (including in-flight streaming responses) into structured blocks.
    public static func parse(_ markdown: String) -> [MarkdownBlock] {
        if let cached = cacheLock.withLock({ blockCache[markdown] }) {
            return cached
        }
        let normalized = markdown.replacingOccurrences(of: "\r\n", with: "\n")
        let lines = normalized.components(separatedBy: "\n")
        var blocks: [MarkdownBlock] = []

        var i = 0
        while i < lines.count {
            let line = lines[i]
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            // 1. Blank line
            if trimmed.isEmpty {
                i += 1
                continue
            }

            // 2. Fenced Code Block (```lang ... ```)
            if trimmed.hasPrefix("```") {
                let lang = String(trimmed.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                var codeLines: [String] = []
                i += 1
                while i < lines.count {
                    let candidate = lines[i]
                    if candidate.trimmingCharacters(in: .whitespaces).hasPrefix("```") {
                        i += 1
                        break
                    }
                    codeLines.append(candidate)
                    i += 1
                }
                blocks.append(.codeBlock(language: lang.isEmpty ? "code" : lang, code: codeLines.joined(separator: "\n")))
                continue
            }

            // 3. Horizontal Rule (---, ***, ___)
            if isHorizontalRule(trimmed) {
                blocks.append(.divider)
                i += 1
                continue
            }

            // 4. ATX Heading (# H1 ... ###### H6)
            if let (level, headingText) = parseHeading(trimmed) {
                blocks.append(.heading(level: level, text: headingText))
                i += 1
                continue
            }

            // 5. Markdown Table (| col1 | col2 | followed by | --- | --- |)
            if trimmed.contains("|"),
               i + 1 < lines.count,
               isTableSeparatorLine(lines[i + 1].trimmingCharacters(in: .whitespaces)) {
                let headers = parseTableRow(trimmed)
                i += 2 // skip header + separator
                var rows: [[String]] = []
                while i < lines.count {
                    let rowTrimmed = lines[i].trimmingCharacters(in: .whitespaces)
                    if rowTrimmed.isEmpty || !rowTrimmed.contains("|") {
                        break
                    }
                    if !isTableSeparatorLine(rowTrimmed) {
                        rows.append(parseTableRow(rowTrimmed))
                    }
                    i += 1
                }
                if !headers.isEmpty {
                    blocks.append(.table(headers: headers, rows: rows))
                    continue
                }
            }

            // 6. Blockquote (> quote)
            if trimmed.hasPrefix(">") {
                var quoteLines: [String] = []
                while i < lines.count {
                    let qTrim = lines[i].trimmingCharacters(in: .whitespaces)
                    guard qTrim.hasPrefix(">") else { break }
                    let stripped = String(qTrim.dropFirst()).trimmingCharacters(in: .whitespaces)
                    quoteLines.append(stripped)
                    i += 1
                }
                blocks.append(.blockquote(text: quoteLines.joined(separator: "\n")))
                continue
            }

            // 7. Bullet List (- item, * item, + item, • item)
            if let firstBullet = parseBulletItem(trimmed) {
                var items: [String] = [firstBullet]
                i += 1
                while i < lines.count {
                    let nextTrim = lines[i].trimmingCharacters(in: .whitespaces)
                    if let nextBullet = parseBulletItem(nextTrim) {
                        items.append(nextBullet)
                        i += 1
                    } else {
                        break
                    }
                }
                blocks.append(.bulletList(items: items))
                continue
            }

            // 8. Ordered List (1. item, 2) item)
            if let firstOrdered = parseOrderedItem(trimmed) {
                var items: [OrderedListItem] = [firstOrdered]
                i += 1
                while i < lines.count {
                    let nextTrim = lines[i].trimmingCharacters(in: .whitespaces)
                    if let nextOrdered = parseOrderedItem(nextTrim) {
                        items.append(nextOrdered)
                        i += 1
                    } else {
                        break
                    }
                }
                blocks.append(.orderedList(items: items))
                continue
            }

            // 9. Standard Paragraph (accumulate contiguous non-special lines)
            var paraLines: [String] = [line]
            i += 1
            while i < lines.count {
                let nextLine = lines[i]
                let nextTrim = nextLine.trimmingCharacters(in: .whitespaces)
                if nextTrim.isEmpty
                    || nextTrim.hasPrefix("```")
                    || isHorizontalRule(nextTrim)
                    || parseHeading(nextTrim) != nil
                    || nextTrim.hasPrefix(">")
                    || parseBulletItem(nextTrim) != nil
                    || parseOrderedItem(nextTrim) != nil
                    || (nextTrim.contains("|") && i + 1 < lines.count && isTableSeparatorLine(lines[i + 1].trimmingCharacters(in: .whitespaces))) {
                    break
                }
                paraLines.append(nextLine)
                i += 1
            }
            blocks.append(.paragraph(text: paraLines.joined(separator: "\n")))
        }

        cacheLock.withLock {
            if blockCache.count >= 128 {
                blockCache.removeAll(keepingCapacity: true)
            }
            blockCache[markdown] = blocks
        }
        return blocks
    }

    /// Parses inline Markdown (**bold**, *italic*, `code`, ~~strike~~, [link](url)) into an AttributedString.
    public static func inlineAttributedString(_ text: String) -> AttributedString {
        if let cached = cacheLock.withLock({ inlineCache[text] }) {
            return cached
        }
        let result: AttributedString
        if let parsed = try? AttributedString(markdown: text, options: inlineParseOptions) {
            result = parsed
        } else {
            result = AttributedString(text)
        }
        cacheLock.withLock {
            if inlineCache.count >= 256 {
                inlineCache.removeAll(keepingCapacity: true)
            }
            inlineCache[text] = result
        }
        return result
    }

    private static func isHorizontalRule(_ trimmed: String) -> Bool {
        guard trimmed.count >= 3 else { return false }
        let compact = trimmed.replacingOccurrences(of: " ", with: "")
        guard compact.count >= 3 else { return false }
        return compact.allSatisfy({ $0 == "-" })
            || compact.allSatisfy({ $0 == "*" })
            || compact.allSatisfy({ $0 == "_" })
    }

    private static func parseHeading(_ trimmed: String) -> (Int, String)? {
        var count = 0
        for ch in trimmed {
            if ch == "#" {
                count += 1
            } else {
                break
            }
        }
        guard (1...6).contains(count), trimmed.count > count else { return nil }
        let idx = trimmed.index(trimmed.startIndex, offsetBy: count)
        guard trimmed[idx] == " " else { return nil }
        let content = String(trimmed[trimmed.index(after: idx)...]).trimmingCharacters(in: .whitespaces)
        return content.isEmpty ? nil : (count, content)
    }

    private static func parseBulletItem(_ trimmed: String) -> String? {
        for prefix in ["- ", "* ", "+ ", "• "] {
            if trimmed.hasPrefix(prefix) {
                return String(trimmed.dropFirst(prefix.count)).trimmingCharacters(in: .whitespaces)
            }
        }
        return nil
    }

    private static func parseOrderedItem(_ trimmed: String) -> OrderedListItem? {
        var digits = ""
        var idx = trimmed.startIndex
        while idx < trimmed.endIndex, trimmed[idx].isNumber {
            digits.append(trimmed[idx])
            idx = trimmed.index(after: idx)
        }
        guard !digits.isEmpty, idx < trimmed.endIndex else { return nil }
        let punct = trimmed[idx]
        guard punct == "." || punct == ")" else { return nil }
        let afterPunct = trimmed.index(after: idx)
        guard afterPunct < trimmed.endIndex, trimmed[afterPunct] == " " else { return nil }
        let content = String(trimmed[trimmed.index(after: afterPunct)...]).trimmingCharacters(in: .whitespaces)
        return OrderedListItem(marker: "\(digits)\(punct)", text: content)
    }

    private static func isTableSeparatorLine(_ trimmed: String) -> Bool {
        guard trimmed.contains("|") && trimmed.contains("-") else { return false }
        return trimmed.unicodeScalars.allSatisfy { tableSeparatorAllowedScalars.contains($0) }
    }

    private static func parseTableRow(_ trimmed: String) -> [String] {
        var working = trimmed
        if working.hasPrefix("|") { working.removeFirst() }
        if working.hasSuffix("|") { working.removeLast() }
        return working
            .components(separatedBy: "|")
            .map { $0.trimmingCharacters(in: .whitespaces) }
    }
}
