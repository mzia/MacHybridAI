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
        #expect(!profile.thermalState.isEmpty)
        #expect(!profile.recommendations.isEmpty)

        let bench = BackendBridge.shared.runHardwareBenchmark(modelId: profile.selectedLocalModel)
        #expect(bench.ttftMs > 0)
        #expect(bench.decodeTps > 0)
        #expect(bench.peakMemoryGb > 0)

        let pullCheck = BackendBridge.shared.pullOrVerifyLocalModel(
            modelId: "mlx-community/gemma-3-4b-it-4bit",
            allowDownload: false
        )
        #expect(pullCheck.modelId == "mlx-community/gemma-3-4b-it-4bit")
    }

    @Test("MarkdownBlockParser parses headings, code blocks, lists, tables, blockquotes, and inline Markdown")
    func testMarkdownBlockParserRendersStructuredBlocks() {
        let sample = """
        # Executive Summary
        Prepared for **Sam Reyes** (`sam.reyes@meridian.io`).

        - [x] Verify **local** Metal working set
        - Benchmark `gemma-3-4b-it-4bit`

        1. First step
        2. Second step

        > Privacy Gate masked 2 entities on this Mac.

        | Metric | Value |
        | --- | --- |
        | Decode | **112 tok/s** |

        ```swift
        let mode = ComputeModeOption.hybrid
        ```
        """

        let blocks = MarkdownBlockParser.parse(sample)
        #expect(blocks.count == 7)
        #expect(blocks[0] == .heading(level: 1, text: "Executive Summary"))
        #expect(blocks[1] == .paragraph(text: "Prepared for **Sam Reyes** (`sam.reyes@meridian.io`)."))
        #expect(blocks[2] == .bulletList(items: ["[x] Verify **local** Metal working set", "Benchmark `gemma-3-4b-it-4bit`"]))
        #expect(blocks[3] == .orderedList(items: [
            OrderedListItem(marker: "1.", text: "First step"),
            OrderedListItem(marker: "2.", text: "Second step"),
        ]))
        #expect(blocks[4] == .blockquote(text: "Privacy Gate masked 2 entities on this Mac."))
        #expect(blocks[5] == .table(headers: ["Metric", "Value"], rows: [["Decode", "**112 tok/s**"]]))
        #expect(blocks[6] == .codeBlock(language: "swift", code: "let mode = ComputeModeOption.hybrid"))

        let inline = MarkdownBlockParser.inlineAttributedString("Prepared for **Sam Reyes** (`sam.reyes@meridian.io`)")
        let renderedPlain = String(inline.characters)
        #expect(renderedPlain == "Prepared for Sam Reyes (sam.reyes@meridian.io)")
    }

    @Test("Smart Auto mode, Multi-Cloud Consensus option, Cryptographic Receipt, and LocalVisionOCRScrubber")
    func testSmartAutoConsensusCryptographicReceiptAndVisionOCR() throws {
        #expect(ComputeModeOption.allCases.contains(.auto))
        #expect(CloudProviderOption.allCases.contains(.consensus))

        let receipt = ExecutionReceiptModel(
            modeExecuted: "hybrid",
            localModelUsed: "mlx-community/gemma-3-4b-it-4bit",
            localAgentLocation: "on this Mac",
            cloudModelsUsed: "Multi-Cloud Consensus Arena",
            piiFlaggedCount: 2,
            piiRestoredCount: 2,
            piiCategories: ["PERSON", "EMAIL"],
            nothingLeftMac: false,
            cloudZeroRetention: true,
            outboundPayloadSha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            receiptSignatureSha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
        )
        #expect(receipt.outboundPayloadSha256.count == 64)
        #expect(receipt.receiptSignatureSha256.count == 64)

        let tmpURL = FileManager.default.temporaryDirectory.appendingPathComponent("vision_ocr_test_\(UUID().uuidString).txt")
        try "Invoice for Sam Reyes (sam.reyes@meridian.io)".write(to: tmpURL, atomically: true, encoding: .utf8)
        defer { try? FileManager.default.removeItem(at: tmpURL) }

        let (extracted, audit) = LocalVisionOCRScrubber.extractAndAuditFile(at: tmpURL, policy: .reversibleMask)
        #expect(extracted.contains("Sam Reyes"))
        #expect(audit.piiFlagged == true)
        #expect(!audit.sanitizedText.contains("sam.reyes@meridian.io"))
    }

    @Test("Universal Cloud AI providers cover OpenAI, Anthropic Claude, OpenRouter, xAI, Groq, DeepSeek, Mistral, Perplexity, Together, and Custom protocols")
    func testUniversalCloudProviderCatalog() {
        let all = CloudProviderOption.allCases
        #expect(all.contains(.openai))
        #expect(all.contains(.anthropic))
        #expect(all.contains(.gemini))
        #expect(all.contains(.openRouter))
        #expect(all.contains(.xai))
        #expect(all.contains(.groq))
        #expect(all.contains(.deepseek))
        #expect(all.contains(.mistral))
        #expect(all.contains(.perplexity))
        #expect(all.contains(.together))
        #expect(all.contains(.openAICompatible))
        #expect(all.contains(.consensus))

        #expect(CloudProviderOption.openai.defaultBaseURL == "https://api.openai.com/v1")
        #expect(CloudProviderOption.anthropic.defaultBaseURL == "https://api.anthropic.com/v1")
        #expect(CloudProviderOption.anthropic.apiKeyEnvName == "ANTHROPIC_API_KEY")
        #expect(CloudProviderOption.openRouter.defaultBaseURL == "https://openrouter.ai/api/v1")
        #expect(CustomCloudProtocolOption.allCases.contains(.openai))
        #expect(CustomCloudProtocolOption.allCases.contains(.anthropic))
    }

    @Test("Apple Foundation Models engine & LocalBackendOption supply-chain trust badges")
    func testAppleFoundationModelsAndLocalBackendSupplyChainOptions() {
        #expect(LocalBackendOption.allCases.contains(.appleFoundationModels))
        #expect(LocalBackendOption.appleFoundationModels.rawValue == "apple_fm")
        #expect(LocalBackendOption.appleFoundationModels.displayName.contains("Apple-Signed"))
        #expect(LocalBackendOption.appleFoundationModels.displayName.contains("Zero Hugging Face"))

        let report = AppleFoundationModelsEngine.checkAvailability()
        #expect(report.modelName.contains("Apple On-Device Foundation Model"))
        #expect(report.signer.contains("Apple Inc."))
        #expect(!report.reason.isEmpty)

        // Verify native macOS HIG navigation sections & appearance options
        #expect(MainWorkspaceSection.allCases == [.chat, .history, .privacyGate])
        #expect(AppAppearanceOption.allCases == [.system, .light, .dark])
        #expect(AppAppearanceOption.system.displayName.contains("macOS"))
    }

    @Test("Cloud prompt storage (iCloud & Google Drive) exports PII-redacted and full shareable Markdown files")
    func testCloudDriveStorageAndShareableMarkdownExport() throws {
        let tempBase = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let localDir = tempBase.appendingPathComponent("local", isDirectory: true)
        let icloudDir = tempBase.appendingPathComponent("icloud", isDirectory: true)
        let gdriveDir = tempBase.appendingPathComponent("gdrive", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: tempBase) }

        let store = PromptHistoryStore(
            customLocalDirectory: localDir,
            customICloudDirectory: icloudDir,
            customGoogleDriveDirectory: gdriveDir
        )

        #expect(HistoryStorageOption.allCases.contains(.googleDrive))
        #expect(HistoryStorageOption.iCloudDrive.isCloudBacked == true)
        #expect(HistoryStorageOption.googleDrive.isCloudBacked == true)
        #expect(HistoryStorageOption.localMac.isCloudBacked == false)

        let baseDate = Date(timeIntervalSince1970: 1_700_000_000)
        let userMsg = ChatMessageModel(
            role: "user",
            content: "Review Q4 memo for Sam Reyes (sam.reyes@meridian.io, 415-555-2671).",
            createdAt: baseDate,
            computeMode: "hybrid",
            cloudProvider: "gemini"
        )
        let assistantMsg = ChatMessageModel(
            role: "assistant",
            content: "Completed Q4 analysis for Sam Reyes (sam.reyes@meridian.io).",
            createdAt: baseDate.addingTimeInterval(5),
            computeMode: "hybrid",
            cloudProvider: "gemini"
        )
        let conv = ChatConversationModel(
            title: "../Q4 Deal Memo: Sam Reyes",
            createdAt: baseDate,
            updatedAt: baseDate.addingTimeInterval(5),
            storageLocation: .googleDrive,
            retentionPolicy: .days30,
            messages: [userMsg, assistantMsg]
        )

        store.saveConversations([conv], to: .googleDrive)
        let loaded = store.loadConversations(from: .googleDrive, now: baseDate.addingTimeInterval(60))
        #expect(loaded.count == 1)

        // 1. Export PII-redacted conversation to Google Drive Shared/ folder
        let redactedURL = try #require(
            store.exportShareableConversation(conv, to: .googleDrive, redactPII: true)
        )
        #expect(redactedURL.path.hasPrefix(gdriveDir.appendingPathComponent("Shared").path))
        #expect(!redactedURL.lastPathComponent.contains(".."))
        let redactedText = try String(contentsOf: redactedURL, encoding: .utf8)
        #expect(!redactedText.contains("sam.reyes@meridian.io"))
        #expect(!redactedText.contains("415-555-2671"))
        #expect(redactedText.contains("Privacy Gate Redacted"))

        // 2. Export full conversation to iCloud Drive Shared/ folder
        let fullURL = try #require(
            store.exportShareableConversation(conv, to: .iCloudDrive, redactPII: false)
        )
        #expect(fullURL.path.hasPrefix(icloudDir.appendingPathComponent("Shared").path))
        let fullText = try String(contentsOf: fullURL, encoding: .utf8)
        #expect(fullText.contains("sam.reyes@meridian.io"))

        // 3. Export single prompt snippet & build Google Drive Web search URL
        let snippetURL = try #require(
            store.exportShareableMessage(userMsg, conversationTitle: conv.title, to: .googleDrive, redactPII: true)
        )
        let snippetText = try String(contentsOf: snippetURL, encoding: .utf8)
        #expect(!snippetText.contains("sam.reyes@meridian.io"))
        let gdriveWebURL = try #require(PromptHistoryStore.googleDriveWebSearchURL(for: snippetURL))
        #expect(gdriveWebURL.absoluteString.hasPrefix("https://drive.google.com/drive/search?q="))
    }

    @Test("Pure Swift NativeSwiftEngine enforces supply-chain audit, CryptoKit SHA-256 pinning, and runs with zero Python daemon")
    func testPureSwiftNativeEngineSupplyChainAndZeroPythonExecution() throws {
        // 1. Engine launches directly into Pure Swift Native mode with zero Python daemon
        BackendBridge.shared.ensureDaemonStarted()
        #expect(DaemonManager.shared.state == .nativeSwift)

        // 2. Path containment guard blocks system directories outside home/temp
        #expect(NativeModelSecurity.sanitizeLocalDirectory("/etc") == nil)
        #expect(NativeModelSecurity.sanitizeLocalDirectory("/usr/bin") == nil)

        // 3. Native Swift supply-chain audit & CryptoKit SHA-256 lockfile verification
        let tempBase = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let modelDir = tempBase.appendingPathComponent("clean_model", isDirectory: true)
        let lockfile = tempBase.appendingPathComponent("models.lock.json")
        defer { try? FileManager.default.removeItem(at: tempBase) }

        try FileManager.default.createDirectory(at: modelDir, withIntermediateDirectories: true)
        try Data("{\"model_type\":\"gemma3\"}".utf8).write(to: modelDir.appendingPathComponent("config.json"))
        try Data("{\"chat_template\":\"{{ messages }}\"}".utf8).write(to: modelDir.appendingPathComponent("tokenizer_config.json"))
        try Data("SAFETENSORS_WEIGHTS_BYTES_1234567890".utf8).write(to: modelDir.appendingPathComponent("model.safetensors"))

        // Strict policy blocks unpinned community repo
        let blocked = NativeModelSecurity.auditModel(
            modelId: "mlx-community/gemma-3-4b-it-4bit",
            modelDir: modelDir,
            allowUnverifiedHuggingFace: false,
            lockfileURL: lockfile
        )
        #expect(blocked.allowed == false)

        // Pin via CryptoKit SHA-256 -> passes under strict policy
        let digest = try #require(
            NativeModelSecurity.pinModel(
                modelId: "mlx-community/gemma-3-4b-it-4bit",
                modelDir: modelDir,
                lockfileURL: lockfile
            )
        )
        #expect(digest.count == 64)

        let pinnedAudit = NativeModelSecurity.auditModel(
            modelId: "mlx-community/gemma-3-4b-it-4bit",
            modelDir: modelDir,
            allowUnverifiedHuggingFace: false,
            lockfileURL: lockfile
        )
        #expect(pinnedAudit.allowed == true)
        #expect(pinnedAudit.lockedSha256Verified == true)

        // Tamper 1 byte -> MUST FAIL CLOSED
        try Data("TAMPERED_WEIGHTS_9999".utf8).write(to: modelDir.appendingPathComponent("model.safetensors"))
        let tamperedAudit = NativeModelSecurity.auditModel(
            modelId: "mlx-community/gemma-3-4b-it-4bit",
            modelDir: modelDir,
            allowUnverifiedHuggingFace: false,
            lockfileURL: lockfile
        )
        #expect(tamperedAudit.allowed == false)
        #expect(tamperedAudit.lockedSha256Verified == false)

        // 4. Pure Swift 4-Station Hybrid task returns real 64-char CryptoKit SHA-256 receipts
        let res = NativeSwiftEngine.shared.runTask(
            prompt: "Compare Q4 ARR for Contact: Sam Reyes (sam.reyes@meridian.io).",
            mode: .hybrid,
            cloudProvider: .gemini,
            guardianPolicy: .reversibleMask,
            attachedFiles: []
        )
        #expect(res.receipt.outboundPayloadSha256.count == 64)
        #expect(res.receipt.receiptSignatureSha256.count == 64)
        #expect(!(res.cloudPromptSent?.contains("sam.reyes@meridian.io") ?? true))
        #expect(res.finalOutput.contains("sam.reyes@meridian.io"))
    }
}
