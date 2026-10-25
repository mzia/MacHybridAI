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
            return "Privacy Gate masks PII on your Mac before cloud research, then restores real values."
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

    enum CodingKeys: String, CodingKey {
        case modeExecuted = "mode_executed"
        case localModelUsed = "local_model_used"
        case localAgentLocation = "local_agent_location"
        case cloudModelsUsed = "cloud_models_used"
        case piiFlaggedCount = "pii_flagged_count"
        case piiRestoredCount = "pii_restored_count"
        case piiCategories = "pii_categories"
        case nothingLeftMac = "nothing_left_mac"
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
    public let prompt: String
    public let finalOutput: String
    public let cloudPromptSent: String?
    public let stations: [StationStepModel]
    public let receipt: ExecutionReceiptModel
    public let telemetry: TelemetryModel
    public let guardianAudit: GuardianAuditModel

    enum CodingKeys: String, CodingKey {
        case taskId = "task_id"
        case prompt
        case finalOutput = "final_output"
        case cloudPromptSent = "cloud_prompt_sent"
        case stations
        case receipt
        case telemetry
        case guardianAudit = "guardian_audit"
    }
}
