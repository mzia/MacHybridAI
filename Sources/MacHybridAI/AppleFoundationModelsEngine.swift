import Foundation

#if canImport(FoundationModels)
import FoundationModels
#endif

/// Native Apple-Signed On-Device Foundation Models Engine (macOS 26+ Apple Intelligence).
///
/// Uses Apple's OS-bundled, code-signed `FoundationModels` framework (`SystemLanguageModel`)
/// with **zero Hugging Face dependency** and **zero third-party weight downloads**.
/// Compiles cleanly on macOS 14/15 SDKs (Xcode 16) via `#if canImport(FoundationModels)` and
/// gracefully reports unavailability on older OS versions.
public enum AppleFoundationModelsEngine {
    public struct AvailabilityReport: Codable, Sendable {
        public let available: Bool
        public let modelName: String
        public let signer: String
        public let reason: String

        enum CodingKeys: String, CodingKey {
            case available
            case modelName = "model_name"
            case signer
            case reason
        }
    }

    public struct GenerationPayload: Codable, Sendable {
        public let prompt: String
        public let systemInstruction: String?

        enum CodingKeys: String, CodingKey {
            case prompt
            case systemInstruction = "system_instruction"
        }
    }

    public struct GenerationResponse: Codable, Sendable {
        public let ok: Bool
        public let outputText: String
        public let modelName: String
        public let signer: String
        public let error: String?

        enum CodingKeys: String, CodingKey {
            case ok
            case outputText = "output_text"
            case modelName = "model_name"
            case signer
            case error
        }
    }

    public static let modelDisplayName = "Apple On-Device Foundation Model (Apple-Signed)"
    public static let signerLabel = "Apple Inc. (macOS System Framework — Zero Hugging Face)"

    /// Returns whether Apple's OS-signed on-device Foundation Model is ready on this Mac.
    public static func checkAvailability() -> AvailabilityReport {
        #if canImport(FoundationModels)
        if #available(macOS 26.0, *) {
            switch SystemLanguageModel.default.availability {
            case .available:
                return AvailabilityReport(
                    available: true,
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    reason: "Apple-signed SystemLanguageModel is available on this Mac."
                )
            case .unavailable(let reason):
                return AvailabilityReport(
                    available: false,
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    reason: "Apple Foundation Models unavailable: \(String(describing: reason)). Enable Apple Intelligence in System Settings."
                )
            @unknown default:
                return AvailabilityReport(
                    available: false,
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    reason: "Apple Foundation Models returned an unrecognized availability state."
                )
            }
        }
        #endif
        return AvailabilityReport(
            available: false,
            modelName: modelDisplayName,
            signer: signerLabel,
            reason: "Requires macOS 26+ with Apple Intelligence (FoundationModels framework)."
        )
    }

    /// Generates text 100% locally using Apple's signed `SystemLanguageModel`.
    public static func generate(
        prompt: String,
        systemInstruction: String? = nil
    ) async -> GenerationResponse {
        #if canImport(FoundationModels)
        if #available(macOS 26.0, *) {
            let status = checkAvailability()
            guard status.available else {
                return GenerationResponse(
                    ok: false,
                    outputText: "",
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    error: status.reason
                )
            }
            do {
                let session: LanguageModelSession
                if let inst = systemInstruction, !inst.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    session = LanguageModelSession(model: .default, instructions: inst)
                } else {
                    session = LanguageModelSession(model: .default)
                }
                let response = try await session.respond(to: prompt)
                return GenerationResponse(
                    ok: true,
                    outputText: response.content,
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    error: nil
                )
            } catch {
                return GenerationResponse(
                    ok: false,
                    outputText: "",
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    error: "Apple Foundation Models error: \(error.localizedDescription)"
                )
            }
        }
        #endif
        return GenerationResponse(
            ok: false,
            outputText: "",
            modelName: modelDisplayName,
            signer: signerLabel,
            error: "Apple Foundation Models requires macOS 26+ with Apple Intelligence enabled."
        )
    }

    /// Streams incremental text deltas 100% locally using Apple's signed `SystemLanguageModel`.
    public static func stream(
        prompt: String,
        systemInstruction: String? = nil,
        onDelta: @escaping @Sendable (String) -> Void
    ) async -> GenerationResponse {
        #if canImport(FoundationModels)
        if #available(macOS 26.0, *) {
            let status = checkAvailability()
            guard status.available else {
                return GenerationResponse(
                    ok: false,
                    outputText: "",
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    error: status.reason
                )
            }
            do {
                let session: LanguageModelSession
                if let inst = systemInstruction, !inst.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    session = LanguageModelSession(model: .default, instructions: inst)
                } else {
                    session = LanguageModelSession(model: .default)
                }
                let stream = session.streamResponse(to: prompt)
                var accumulated = ""
                for try await snapshot in stream {
                    let full = snapshot.content
                    if full.count > accumulated.count, full.hasPrefix(accumulated) {
                        let delta = String(full.dropFirst(accumulated.count))
                        accumulated = full
                        if !delta.isEmpty {
                            onDelta(delta)
                        }
                    } else if full != accumulated {
                        accumulated = full
                    }
                }
                return GenerationResponse(
                    ok: true,
                    outputText: accumulated,
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    error: nil
                )
            } catch {
                return GenerationResponse(
                    ok: false,
                    outputText: "",
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    error: "Apple Foundation Models streaming error: \(error.localizedDescription)"
                )
            }
        }
        #endif
        return await generate(prompt: prompt, systemInstruction: systemInstruction)
    }

    /// Handles headless CLI flags (`--apple-fm-check`, `--apple-fm-generate`) before launching SwiftUI.
    /// Returns an exit code if handled, or `nil` to continue launching the GUI app.
    public static func handleHeadlessCommandIfPresent(arguments: [String]) -> Int32? {
        if arguments.contains("--apple-fm-check") {
            let report = checkAvailability()
            let encoder = JSONEncoder()
            if let data = try? encoder.encode(report), let str = String(data: data, encoding: .utf8) {
                print(str)
            }
            return 0
        }

        if arguments.contains("--apple-fm-generate") {
            let stdinData = FileHandle.standardInput.readDataToEndOfFile()
            let decoder = JSONDecoder()
            let encoder = JSONEncoder()

            guard let payload = try? decoder.decode(GenerationPayload.self, from: stdinData) else {
                let errResp = GenerationResponse(
                    ok: false,
                    outputText: "",
                    modelName: modelDisplayName,
                    signer: signerLabel,
                    error: "Invalid JSON payload on stdin (expected {\"prompt\": ...})."
                )
                if let data = try? encoder.encode(errResp), let str = String(data: data, encoding: .utf8) {
                    print(str)
                }
                return 1
            }

            let semaphore = DispatchSemaphore(value: 0)
            final class Box: @unchecked Sendable {
                var value: GenerationResponse?
            }
            let box = Box()

            Task.detached {
                box.value = await generate(
                    prompt: payload.prompt,
                    systemInstruction: payload.systemInstruction
                )
                semaphore.signal()
            }
            semaphore.wait()

            let finalResp = box.value ?? GenerationResponse(
                ok: false,
                outputText: "",
                modelName: modelDisplayName,
                signer: signerLabel,
                error: "Apple Foundation Models generation timed out or failed."
            )
            if let data = try? encoder.encode(finalResp), let str = String(data: data, encoding: .utf8) {
                print(str)
            }
            return finalResp.ok ? 0 : 1
        }

        return nil
    }
}
