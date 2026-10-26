import Foundation

public enum ComputeModeOption: String, CaseIterable, Codable, Sendable {
    case local = "local"
    case hybrid = "hybrid"

    public var title: String {
        switch self {
        case .local: return "Fully local"
        case .hybrid: return "Hybrid"
        }
    }

    public var subtitle: String {
        switch self {
        case .local:
            return "Model and agent run on this Mac. Nothing leaves this Mac."
        case .hybrid:
            return "Privacy Gate masks PII on your Mac before stateless cloud research, then restores real values."
        }
    }
}

public enum CloudProviderOption: String, CaseIterable, Codable, Sendable {
    case gemini = "gemini"
    case antigravity = "antigravity"
    case m365Copilot = "m365_copilot"
    case openAICompatible = "openai_compatible"

    public var displayName: String {
        switch self {
        case .gemini: return "Google Gemini (gemini-3.8-flash)"
        case .antigravity: return "Google Antigravity Agent"
        case .m365Copilot: return "M365 Copilot Proxy (gpt-5.5-think-deeper)"
        case .openAICompatible: return "OpenAI Extension API"
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

    public init(
        modeExecuted: String,
        localModelUsed: String,
        localAgentLocation: String,
        cloudModelsUsed: String,
        piiFlaggedCount: Int,
        piiRestoredCount: Int,
        piiCategories: [String],
        nothingLeftMac: Bool,
        cloudZeroRetention: Bool = true
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
    public let content: String
    public let createdAt: Date
    public let computeMode: String
    public let cloudProvider: String
    public let sanitizedCloudPrompt: String?
    public let piiMaskedCount: Int
    public let piiRestoredCount: Int
    public let stations: [StationStepModel]
    public let receipt: ExecutionReceiptModel?
    public let telemetry: TelemetryModel?
    public let cloudZeroRetention: Bool

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
        cloudZeroRetention: Bool = true
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
