import Testing
import Foundation
@testable import MacHybridAI

@Suite("MacHybridAI Privacy Gate & Hybrid Compute Tests")
struct MacHybridAITests {
    @Test("SwiftNativeGuardian masks and restores PII reversibly")
    func testSwiftNativeGuardianMasksAndRestoresPII() {
        let guardian = SwiftNativeGuardian()
        let raw = "Contact: Sam Reyes at sam.reyes@meridian.io or (415) 555-2671, SSN 123-45-6789."
        let scan = guardian.redactAndRestorePreview(text: raw, policy: .reversibleMask)

        #expect(!scan.entities.isEmpty)
        #expect(!scan.sanitized.contains("sam.reyes@meridian.io"))
        #expect(!scan.sanitized.contains("123-45-6789"))
        #expect(!scan.sanitized.contains("Sam Reyes"))
        #expect(scan.sanitized.contains("[EMAIL_1]"))
        #expect(scan.sanitized.contains("[SSN_1]"))
        #expect(scan.restored.contains("sam.reyes@meridian.io"))
        #expect(scan.restored.contains("Sam Reyes"))
    }

    @Test("BackendBridge executes Fully Local and Hybrid modes with PII protection and Zero Cloud History")
    func testBackendBridgeHybridAndLocalExecution() {
        let bridge = BackendBridge.shared

        // 1. Fully Local Mode
        let localResult = bridge.runTask(
            prompt: "Review portfolio holdings for Contact: Sam Reyes (sam.reyes@meridian.io).",
            mode: .local,
            cloudProvider: .gemini,
            guardianPolicy: .reversibleMask,
            attachedFiles: []
        )
        #expect(localResult.cloudPromptSent == nil)
        #expect(localResult.receipt.nothingLeftMac == true)
        #expect(localResult.receipt.cloudZeroRetention == true)
        #expect(localResult.receipt.cloudModelsUsed == "not used")

        // 2. Hybrid Mode with Privacy Gate
        let hybridResult = bridge.runTask(
            prompt: "Benchmark deal for Contact: Sam Reyes (sam.reyes@meridian.io).",
            mode: .hybrid,
            cloudProvider: .m365Copilot,
            guardianPolicy: .reversibleMask,
            attachedFiles: []
        )
        #expect(hybridResult.cloudPromptSent != nil)
        #expect(!(hybridResult.cloudPromptSent?.contains("sam.reyes@meridian.io") ?? true))
        #expect(hybridResult.finalOutput.contains("sam.reyes@meridian.io"))
        #expect(hybridResult.receipt.piiFlaggedCount > 0)
        #expect(hybridResult.receipt.cloudZeroRetention == true)
    }

    @Test("Strict redaction mode permanently strips PII without restoration")
    func testStrictRedactionDoesNotRestore() {
        let guardian = SwiftNativeGuardian()
        let scan = guardian.redactAndRestorePreview(
            text: "Email secret@company.com",
            policy: .strictRedact
        )
        #expect(scan.sanitized.contains("[REDACTED_EMAIL]"))
        #expect(!scan.restored.contains("secret@company.com"))
    }

    @Test("PromptHistoryStore saves to Local Mac or iCloud and enforces auto-delete or never-delete")
    func testPromptHistoryStoreLocalICloudAndAutoDelete() throws {
        let tempBase = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let localDir = tempBase.appendingPathComponent("local", isDirectory: true)
        let icloudDir = tempBase.appendingPathComponent("icloud", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: tempBase) }

        let store = PromptHistoryStore(customLocalDirectory: localDir, customICloudDirectory: icloudDir)
        let baseDate = Date(timeIntervalSince1970: 1_700_000_000)

        let msg = ChatMessageModel(role: "user", content: "Saved prompt", createdAt: baseDate)
        let conv24h = ChatConversationModel(
            title: "24h Expiring Chat",
            createdAt: baseDate,
            updatedAt: baseDate,
            storageLocation: .localMac,
            retentionPolicy: .hours24,
            messages: [msg]
        )
        store.saveConversations([conv24h], to: .localMac)

        // Before 24 hours: still present
        let loadedBefore = store.loadConversations(from: .localMac, now: baseDate.addingTimeInterval(3600))
        #expect(loadedBefore.count == 1)

        // After 25 hours: automatically deleted
        let loadedAfter = store.loadConversations(from: .localMac, now: baseDate.addingTimeInterval(25 * 3600))
        #expect(loadedAfter.isEmpty)

        // Never delete option on iCloud Drive: persists indefinitely
        let convNever = ChatConversationModel(
            title: "Permanent iCloud Chat",
            createdAt: baseDate,
            updatedAt: baseDate,
            storageLocation: .iCloudDrive,
            retentionPolicy: .neverDelete,
            messages: [msg]
        )
        store.saveConversations([convNever], to: .iCloudDrive)
        let loadedYearsLater = store.loadConversations(
            from: .iCloudDrive,
            now: baseDate.addingTimeInterval(10 * 365 * 86400)
        )
        #expect(loadedYearsLater.count == 1)
        #expect(loadedYearsLater.first?.retentionPolicy == .neverDelete)
    }

    @Test("HardwareProfiler returns Apple Silicon SoC, Metal Working Set budget, and Model Recommendations")
    func testHardwareProfilerReturnsSpecsAndRecommendations() {
        let profile = BackendBridge.shared.fetchHardwareProfile()
        #expect(!profile.chipBrand.isEmpty)
        #expect(profile.unifiedMemoryGb >= 8)
        #expect(profile.metalWorkingSetGb > 0)
        #expect(!profile.selectedLocalModel.isEmpty)
        #expect(!profile.recommendations.isEmpty)
    }
}
