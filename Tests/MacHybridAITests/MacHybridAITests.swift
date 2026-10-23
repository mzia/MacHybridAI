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

    @Test("BackendBridge executes Fully Local and Hybrid modes with PII protection")
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
}
