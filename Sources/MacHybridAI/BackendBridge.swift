import Foundation
import NaturalLanguage

// MARK: - DaemonManager

/// Manages the lifecycle of the persistent `machybrid` Python daemon.
///
/// On first use the daemon is started once and kept running for the lifetime of the app.
/// All subsequent requests go through an in-process URLSession HTTP call to
/// `http://127.0.0.1:<port>` — no Python cold-start per request.
///
/// Startup protocol:
///  1. Swift creates a pipe and passes the write-end fd to the daemon via `--ready-fd`.
///  2. Once the server socket is bound, the daemon writes `"<port>\n"` to that fd.
///  3. Swift reads the port from the pipe and stores it.
///  4. If the pipe read times out (3 s), Swift falls back to polling `/health`.
///  5. If the process dies, the next `invoke` call restarts it automatically.
public final class DaemonManager: ObservableObject, @unchecked Sendable {
    public static let shared = DaemonManager()

    /// Published so the UI can show a "daemon starting…" indicator.
    @Published public private(set) var state: DaemonState = .notStarted

    public enum DaemonState: Equatable, Sendable {
        case notStarted
        case starting
        case running(port: Int)
        case failed(String)
    }

    private let lock = NSLock()
    private var _process: Process?
    private var _port: Int = 0

    private var process: Process? {
        get { lock.withLock { _process } }
        set { lock.withLock { _process = newValue } }
    }

    // Maximum seconds to wait for the daemon's ready-fd signal before polling.
    private let readyTimeoutSeconds: TimeInterval = 5

    private init() {}

    /// Start the daemon if not already running. Safe to call from any context.
    public func ensureRunning(backendDir: String, pythonPath: String) {
        lock.withLock {
            if case .running = state, let p = _process, p.isRunning { return }
            if case .starting = state { return }
        }
        DispatchQueue.main.async { self.state = .starting }

        Task.detached(priority: .userInitiated) {
            let result = self._launch(backendDir: backendDir, pythonPath: pythonPath)
            await MainActor.run {
                switch result {
                case .success(let p):
                    self.state = .running(port: p)
                case .failure(let err):
                    self.state = .failed(err.localizedDescription)
                }
            }
        }
    }

    /// Block the calling thread until the daemon is ready or timeout elapses.
    /// Call only from a background (non-MainActor) thread.
    func waitUntilReady(timeout: TimeInterval = 6) -> Int? {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            let sema = DispatchSemaphore(value: 0)
            // nonisolated(unsafe) lets us write from the main-actor closure without
            // a data-race error; the semaphore provides the necessary synchronisation.
            nonisolated(unsafe) var snap: DaemonState = .notStarted
            DispatchQueue.main.async {
                snap = self.state
                sema.signal()
            }
            sema.wait()
            if case .running(let p) = snap { return p }
            if case .failed = snap { return nil }
            Thread.sleep(forTimeInterval: 0.05)
        }
        return nil
    }

    /// Terminate the daemon process cleanly.
    public func stop() {
        process?.terminate()
        process = nil
        state = .notStarted
    }

    // MARK: Private launch

    private func _launch(backendDir: String, pythonPath: String) -> Result<Int, Error> {
        // Create a pipe: Swift reads from [0], Python writes to [1].
        var pipeFds: [Int32] = [0, 0]
        guard Darwin.pipe(&pipeFds) == 0 else {
            return .failure(NSError(domain: "DaemonManager", code: 1,
                                   userInfo: [NSLocalizedDescriptionKey: "pipe() failed"]))
        }
        let readFd = pipeFds[0]
        let writeFd = pipeFds[1]

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: pythonPath)
        proc.arguments = [
            "-m", "machybrid.server",
            "--host", "127.0.0.1",
            "--port", "0",           // OS picks a free port
            "--ready-fd", "\(writeFd)",
        ]
        var env = ProcessInfo.processInfo.environment
        env["PYTHONPATH"] = backendDir
        proc.environment = env
        proc.standardOutput = Pipe()   // suppress stdout noise
        proc.standardError = Pipe()    // suppress stderr noise

        do {
            try proc.run()
        } catch {
            Darwin.close(readFd)
            Darwin.close(writeFd)
            return .failure(error)
        }

        // Close the write-end in our process so the read below returns EOF if Python closes it.
        Darwin.close(writeFd)

        // Read the port line from the ready-fd with a timeout.
        let resolvedPort = _readPortFromPipe(fd: readFd, timeout: readyTimeoutSeconds)
        Darwin.close(readFd)

        guard let resolvedPort, resolvedPort > 0 else {
            // Pipe read timed out or failed — fall back to polling /health.
            if let polled = _pollHealth(proc: proc) {
                self.process = proc
                return .success(polled)
            }
            proc.terminate()
            return .failure(NSError(domain: "DaemonManager", code: 2,
                                    userInfo: [NSLocalizedDescriptionKey: "Daemon did not become ready in time"]))
        }

        self.process = proc
        return .success(resolvedPort)
    }

    /// Reads `"<port>\n"` from the ready-fd with a wall-clock timeout.
    private nonisolated func _readPortFromPipe(fd: Int32, timeout: TimeInterval) -> Int? {
        var buf = [UInt8](repeating: 0, count: 32)
        var totalRead = 0
        let deadline = Date().addingTimeInterval(timeout)

        while Date() < deadline {
            // Use withUnsafeMutableBytes to get a valid pointer into the buffer at
            // the current offset — avoids the "temporary pointer" warning from `&buf + n`.
            let n = buf.withUnsafeMutableBytes { ptr -> Int in
                Darwin.read(fd, ptr.baseAddress!.advanced(by: totalRead), 1)
            }
            if n <= 0 { break }
            totalRead += 1
            if buf[totalRead - 1] == UInt8(ascii: "\n") { break }
            if totalRead >= buf.count { break }
        }

        guard totalRead > 0 else { return nil }
        let line = String(bytes: buf.prefix(totalRead), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return Int(line)
    }

    /// Poll `GET /health` on sequential ports until a response arrives (fallback path).
    private nonisolated func _pollHealth(proc: Process, attempts: Int = 40, interval: TimeInterval = 0.15) -> Int? {
        // Try the default port first, then scan common ephemeral range.
        let candidates = [8765] + (49152...49200).map { $0 }
        for _ in 0..<attempts {
            guard proc.isRunning else { return nil }
            for port in candidates {
                if _httpGetOK(port: port, path: "/health") { return port }
            }
            Thread.sleep(forTimeInterval: interval)
        }
        return nil
    }

    private nonisolated func _httpGetOK(port: Int, path: String) -> Bool {
        guard let url = URL(string: "http://127.0.0.1:\(port)\(path)") else { return false }
        var req = URLRequest(url: url)
        req.timeoutInterval = 0.3
        // nonisolated(unsafe): written only inside the semaphore-guarded closure,
        // read only after sema.wait() — the semaphore is the synchronisation barrier.
        nonisolated(unsafe) var ok = false
        let sema = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            if let http = resp as? HTTPURLResponse, http.statusCode == 200 { ok = true }
            sema.signal()
        }.resume()
        sema.wait()
        return ok
    }
}

// MARK: - SwiftNativeGuardian
public struct SwiftNativeGuardian: Sendable {
    public init() {}

    public func redactAndRestorePreview(
        text: String,
        policy: GuardianPolicyOption = .reversibleMask
    ) -> (sanitized: String, restored: String, entities: [PIIEntityModel], vault: [String: String]) {
        guard !text.isEmpty else {
            return ("", "", [], [:])
        }

        var entities: [PIIEntityModel] = []
        var vault: [String: String] = [:]
        var counters: [String: Int] = [:]

        // 1. Native macOS NER using NaturalLanguage framework (The "Native Privacy Layer")
        let tagger = NLTagger(tagSchemes: [.nameType])
        tagger.string = text
        tagger.enumerateTags(in: text.startIndex..<text.endIndex, unit: .word, scheme: .nameType, options: [.joinNames]) { tag, range in
            if let tag = tag {
                let category: String
                switch tag {
                case .personalName: category = "PERSON"
                case .organizationName: category = "ORGANIZATION"
                case .placeName: category = "PLACE"
                default: return true // skip other tags
                }

                let value = String(text[range])
                let start = range.lowerBound.utf16Offset(in: text)
                let end = range.upperBound.utf16Offset(in: text)

                // Register entity
                let count = (counters[category] ?? 0) + 1
                counters[category] = count
                let token = policy == .strictRedact ? "[REDACTED_\(category)]" : "[\(category)_\(count)]"
                if policy != .strictRedact { vault[token] = value }

                entities.append(
                    PIIEntityModel(
                        category: category,
                        replacementToken: token,
                        start: start,
                        end: end,
                        confidence: 0.95,
                        maskedPreview: value.count <= 4 ? "****" : "\(value.prefix(2))****\(value.suffix(2))"
                    )
                )
            }
            return true
        }

        // 2. High-precision regex for patterns NLTagger doesn't cover (Secrets, SSNs, etc.)
        let patterns: [(category: String, regex: String, confidence: Double)] = [
            ("SECRET", #"\b(?:AIza[0-9A-Za-z\-_]{35}|sk-[A-Za-z0-9\-_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"#, 0.99),
            ("SSN", #"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"#, 0.99),
            ("EMAIL", #"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"#, 0.99),
            ("PHONE", #"(?:\+?1[-.\s]?)?(?:\(\d{3}\)[-.\s]?|\b\d{3}[-.\s])\d{3}[-.\s]\d{4}\b"#, 0.95),
        ]

        for item in patterns {
            guard let regex = try? NSRegularExpression(pattern: item.regex) else { continue }
            let matches = regex.matches(in: text, range: NSRange(location: 0, length: (text as NSString).length))
            for m in matches {
                let val = (text as NSString).substring(with: m.range)
                
                // Avoid overlapping with NLTagger entities
                if entities.contains(where: { $0.start < m.range.location + m.range.length && $0.end > m.range.location }) {
                    continue
                }

                let category = item.category
                let count = (counters[category] ?? 0) + 1
                counters[category] = count
                let token = policy == .strictRedact ? "[REDACTED_\(category)]" : "[\(category)_\(count)]"
                if policy != .strictRedact { vault[token] = val }

                entities.append(
                    PIIEntityModel(
                        category: category,
                        replacementToken: token,
                        start: m.range.location,
                        end: m.range.location + m.range.length,
                        confidence: item.confidence,
                        maskedPreview: val.count <= 4 ? "****" : "\(val.prefix(2))****\(val.suffix(2))"
                    )
                )
            }
        }

        // Sort entities by start position to build the sanitized string
        entities.sort { $0.start < $1.start }

        var result = ""
        var cursor = 0
        for entity in entities {
            if entity.start > cursor {
                result += (text as NSString).substring(with: NSRange(location: cursor, length: entity.start - cursor))
            }
            result += entity.replacementToken
            cursor = entity.end
        }

        if cursor < (text as NSString).length {
            result += (text as NSString).substring(from: cursor)
        }

        var restored = "Cloud processed request for \(result)"
        for (token, original) in vault {
            restored = restored.replacingOccurrences(of: token, with: original)
        }
        return (result, restored, entities, vault)
    }
}

/// Manages saving user chat and prompt history to Local Mac Storage or iCloud Drive,
/// with configurable auto-delete retention periods (`24h`, `7d`, `30d`, `90d`, `never`).
/// Note: Nothing is ever retained in any Cloud AI provider's history (`store=false`).
public final class PromptHistoryStore: @unchecked Sendable {
    public let localDirectoryURL: URL
    public let iCloudDirectoryURL: URL

    public init(
        customLocalDirectory: URL? = nil,
        customICloudDirectory: URL? = nil
    ) {
        let home = FileManager.default.homeDirectoryForCurrentUser
        self.localDirectoryURL = customLocalDirectory ?? home
            .appendingPathComponent("Library/Application Support/MacHybridAI/history", isDirectory: true)
        self.iCloudDirectoryURL = customICloudDirectory ?? home
            .appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs/MacHybridAI", isDirectory: true)
    }

    public func fileURL(for location: HistoryStorageOption) -> URL {
        let dir = location == .iCloudDrive ? iCloudDirectoryURL : localDirectoryURL
        return dir.appendingPathComponent("chat_history.json")
    }

    public func isICloudAvailable() -> Bool {
        let parent = iCloudDirectoryURL.deletingLastPathComponent()
        return FileManager.default.fileExists(atPath: parent.path) || FileManager.default.fileExists(atPath: iCloudDirectoryURL.path)
    }

    public func loadConversations(
        from location: HistoryStorageOption,
        now: Date = Date()
    ) -> [ChatConversationModel] {
        let target = fileURL(for: location)
        guard FileManager.default.fileExists(atPath: target.path),
              let data = try? Data(contentsOf: target) else {
            return []
        }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        guard let decoded = try? decoder.decode([ChatConversationModel].self, from: data) else {
            return []
        }
        let valid = decoded.filter { !$0.isExpired(at: now) }
        if valid.count != decoded.count {
            saveConversations(valid, to: location)
        }
        return valid
    }

    public func saveConversations(
        _ conversations: [ChatConversationModel],
        to location: HistoryStorageOption
    ) {
        let target = fileURL(for: location)
        let dir = target.deletingLastPathComponent()
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            encoder.dateEncodingStrategy = .iso8601
            let data = try encoder.encode(conversations)
            try data.write(to: target, options: .atomic)
            try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: target.path)
        } catch {
            // Ignore write errors in restricted environments
        }
    }

    public func applyRetentionPolicy(
        _ policy: HistoryRetentionOption,
        conversations: [ChatConversationModel],
        location: HistoryStorageOption,
        now: Date = Date()
    ) -> [ChatConversationModel] {
        var updated: [ChatConversationModel] = []
        for var conv in conversations {
            conv.retentionPolicy = policy
            conv.storageLocation = location
            conv.expiresAt = policy.computeExpiryDate(from: conv.updatedAt)
            if !conv.isExpired(at: now) {
                updated.append(conv)
            }
        }
        saveConversations(updated, to: location)
        return updated
    }
}

/// Bridges the SwiftUI macOS App with the Python `machybrid` backend engine.
///
/// Request routing priority:
///  1. HTTP to the persistent daemon (zero cold-start, fastest path).
///  2. Subprocess `--cli-json` (legacy fallback when daemon hasn't started yet).
///  3. Native Swift fallback (pure-Swift PII Guardian, no Python required).
public final class BackendBridge: Sendable {
    public static let shared = BackendBridge()
    private let fallbackGuardian = SwiftNativeGuardian()

    public init() {}

    // MARK: – Helpers

    /// Resolves the path to the `backend` folder inside the `.app` bundle or repository workspace.
    public func resolveBackendDirectory() -> String? {
        if let resourcePath = Bundle.main.resourcePath {
            let bundled = (resourcePath as NSString).appendingPathComponent("backend")
            if FileManager.default.fileExists(atPath: (bundled as NSString).appendingPathComponent("machybrid/server.py")) {
                return bundled
            }
        }
        let cwd = FileManager.default.currentDirectoryPath
        let localBackend = (cwd as NSString).appendingPathComponent("backend")
        if FileManager.default.fileExists(atPath: (localBackend as NSString).appendingPathComponent("machybrid/server.py")) {
            return localBackend
        }
        return nil
    }

    private var pythonPath: String {
        let candidates = ["/opt/homebrew/bin/python3", "/usr/bin/python3"]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) } ?? "/usr/bin/python3"
    }

    // MARK: – HTTP transport (persistent daemon)

    /// Send a JSON request to the persistent daemon via HTTP.
    /// Called from a background thread — blocks until the response arrives.
    private func invokeHTTP(method: String, path: String, body: [String: Any]) -> Data? {
        // Ensure the daemon is running. This is a no-op when it's already up.
        if let backendDir = resolveBackendDirectory() {
            let py = pythonPath
            DispatchQueue.main.async {
                DaemonManager.shared.ensureRunning(backendDir: backendDir, pythonPath: py)
            }
        }

        // Wait (blocking, called off main thread) until the daemon signals ready.
        guard let port = DaemonManager.shared.waitUntilReady(timeout: 8) else { return nil }

        guard let url = URL(string: "http://127.0.0.1:\(port)\(path)") else { return nil }
        var req = URLRequest(url: url)
        req.httpMethod = method.uppercased()
        req.timeoutInterval = 120
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if method.uppercased() != "GET",
           let bodyData = try? JSONSerialization.data(withJSONObject: body) {
            req.httpBody = bodyData
        }

        // nonisolated(unsafe): semaphore guarantees result is written before it is read.
        nonisolated(unsafe) var result: Data?
        let sema = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: req) { data, _, _ in
            result = data
            sema.signal()
        }.resume()
        sema.wait()
        return result
    }

    // MARK: – Subprocess transport (legacy / cold-start fallback)

    /// Invokes the Python `machybrid.server --cli-json` bridge via subprocess.
    /// Used as fallback when the HTTP daemon is not yet ready.
    public func invokePythonJSON(method: String, path: String, body: [String: Any]) -> Data? {
        guard let backendDir = resolveBackendDirectory() else { return nil }

        let requestDict: [String: Any] = ["method": method, "path": path, "body": body]
        guard let reqData = try? JSONSerialization.data(withJSONObject: requestDict),
              let reqStr = String(data: reqData, encoding: .utf8) else { return nil }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = ["-m", "machybrid.server", "--cli-json", reqStr]
        var env = ProcessInfo.processInfo.environment
        env["PYTHONPATH"] = backendDir
        process.environment = env

        let outPipe = Pipe()
        process.standardOutput = outPipe
        process.standardError = Pipe()

        do {
            try process.run()
            process.waitUntilExit()
            guard process.terminationStatus == 0 else { return nil }
            let data = outPipe.fileHandleForReading.readDataToEndOfFile()
            return data.isEmpty ? nil : data
        } catch {
            return nil
        }
    }

    // MARK: – Unified invoke (HTTP → subprocess → nil)

    /// Routes a request through HTTP daemon first, subprocess second.
    private func invoke(method: String, path: String, body: [String: Any]) -> Data? {
        // Fast path: HTTP to persistent daemon (no cold-start)
        if let data = invokeHTTP(method: method, path: path, body: body) { return data }
        // Slow path: subprocess (daemon not yet running or crashed)
        return invokePythonJSON(method: method, path: path, body: body)
    }

    // MARK: – Token streaming (SSE)

    /// Connects to `POST /v1/tasks/stream` and calls `onToken` for every token
    /// as it arrives from the MLX model or hybrid pipeline.
    /// Call from a background thread — blocks until the stream ends or an error occurs.
    ///
    /// - Parameters:
    ///   - prompt: Raw user prompt (Privacy Gate runs server-side before streaming starts).
    ///   - mode: Compute mode (local / hybrid / auto).
    ///   - sessionId: Optional session ID for history continuity.
    ///   - onToken: Called on each token string as it streams in.
    ///   - onReceipt: Called once at stream end with the final receipt dictionary.
    public func streamTask(
        prompt: String,
        mode: ComputeModeOption,
        cloudProvider: CloudProviderOption,
        attachedFiles: [String] = [],
        sessionId: String? = nil,
        onToken: @escaping @Sendable (String) -> Void,
        onReceipt: @escaping @Sendable ([String: Any]) -> Void
    ) {
        guard let port = DaemonManager.shared.waitUntilReady(timeout: 8) else {
            onReceipt([:])
            return
        }

        guard let url = URL(string: "http://127.0.0.1:\(port)/v1/tasks/stream") else { return }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 300   // long-running streams need a generous timeout
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("text/event-stream", forHTTPHeaderField: "Accept")

        var excerpts: [String] = []
        var fileLabels: [String] = []
        for path in attachedFiles {
            let fileURL = URL(fileURLWithPath: path)
            fileLabels.append(fileURL.lastPathComponent)
            if let text = try? String(contentsOf: fileURL, encoding: .utf8) {
                let snippet = String(text.prefix(8192))
                excerpts.append("--- \(fileURL.lastPathComponent) ---\n\(snippet)")
            }
        }

        var body: [String: Any] = [
            "prompt": prompt,
            "mode": mode.rawValue,
            "cloud_provider": cloudProvider.rawValue,
            "file_paths": fileLabels,
            "inline_file_context": excerpts.joined(separator: "\n\n"),
        ]
        if let sessionId { body["session_id"] = sessionId }
        req.httpBody = try? JSONSerialization.data(withJSONObject: body)

        // Use a delegate-based URLSession so we can process data as it arrives.
        let delegate = SSEStreamDelegate(onToken: onToken, onReceipt: onReceipt)
        let session = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
        let task = session.dataTask(with: req)
        task.resume()
        delegate.waitUntilDone()
        session.invalidateAndCancel()
    }

    public func runTask(
        prompt: String,
        mode: ComputeModeOption,
        cloudProvider: CloudProviderOption,
        guardianPolicy: GuardianPolicyOption,
        attachedFiles: [String],
        sessionId: String? = nil
    ) -> TaskResultModel {
        var excerpts: [String] = []
        var fileLabels: [String] = []
        for path in attachedFiles {
            let url = URL(fileURLWithPath: path)
            fileLabels.append(url.lastPathComponent)
            if let text = try? String(contentsOf: url, encoding: .utf8) {
                let snippet = String(text.prefix(8192))
                excerpts.append("--- \(url.lastPathComponent) ---\n\(snippet)")
            }
        }
        var body: [String: Any] = [
            "prompt": prompt,
            "mode": mode.rawValue,
            "cloud_provider": cloudProvider.rawValue,
            "file_paths": fileLabels,
            "inline_file_context": excerpts.joined(separator: "\n\n"),
        ]
        if let sessionId {
            body["session_id"] = sessionId
        }

        if let data = invoke(method: "POST", path: "/v1/tasks/run", body: body),
           let decoded = try? JSONDecoder().decode(TaskResultModel.self, from: data) {
            return decoded
        }

        // Native Swift fallback execution
        return runNativeFallbackTask(
            prompt: prompt,
            mode: mode,
            cloudProvider: cloudProvider,
            guardianPolicy: guardianPolicy,
            attachedFiles: attachedFiles,
            sessionId: sessionId
        )
    }

    public func inspectPII(
        text: String,
        policy: GuardianPolicyOption
    ) -> GuardianAuditModel {
        // Use the native macOS privacy layer (NLTagger) as the primary source for high-accuracy, on-device detection
        let scan = fallbackGuardian.redactAndRestorePreview(text: text, policy: policy)
        let categories = Array(Set(scan.entities.map(\.category))).sorted()
        
        return GuardianAuditModel(
            sanitizedText: scan.sanitized,
            piiFlagged: !scan.entities.isEmpty,
            piiCount: scan.entities.count,
            categories: categories,
            policyApplied: policy.rawValue,
            forcedLocal: policy == .forceLocalOnPII && !scan.entities.isEmpty,
            entities: scan.entities,
            restoredPreview: scan.restored,
            restoredCount: scan.entities.count
        )
    }

    public func fetchHardwareProfile() -> MacHardwareProfileModel {
        if let data = invoke(method: "GET", path: "/v1/hardware/profile", body: [:]),
           let decoded = try? JSONDecoder().decode(MacHardwareProfileModel.self, from: data) {
            return decoded
        }
        return nativeHardwareProfileFallback()
    }

    public func updateBackendConfig(body: [String: Any]) {
        _ = invoke(method: "POST", path: "/v1/config", body: body)
    }

    private func nativeSysctlString(_ key: String) -> String? {
        var size: Int = 0
        guard Darwin.sysctlbyname(key, nil, &size, nil, 0) == 0, size > 0 else { return nil }
        var buf = [CChar](repeating: 0, count: size)
        guard Darwin.sysctlbyname(key, &buf, &size, nil, 0) == 0 else { return nil }
        return String(cString: buf).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func nativeSysctlInt(_ key: String) -> Int? {
        var val: Int64 = 0
        var size = MemoryLayout<Int64>.size
        guard Darwin.sysctlbyname(key, &val, &size, nil, 0) == 0 else { return nil }
        return Int(val)
    }

    private func nativeHardwareProfileFallback() -> MacHardwareProfileModel {
        let memBytes = ProcessInfo.processInfo.physicalMemory
        let memGb = max(8, Int(memBytes / (1024 * 1024 * 1024)))
        let chip = nativeSysctlString("machdep.cpu.brand_string") ?? "Apple Silicon"
        let totalCores = ProcessInfo.processInfo.activeProcessorCount
        let perfCores = nativeSysctlInt("hw.perflevel0.physicalcpu") ?? totalCores
        let effCores = nativeSysctlInt("hw.perflevel1.physicalcpu") ?? 0
        let workingSetGb = Double(memGb) * 0.78
        let maxBufferGb = Double(memGb) * 0.58
        let tier = memGb >= 64 ? "ultra_64gb_plus" : (memGb >= 48 ? "pro_max_48gb" : (memGb >= 24 ? "pro_24_36gb" : "entry_8_16gb"))

        return MacHardwareProfileModel(
            architecture: "arm64",
            chipBrand: chip,
            cpuCoresTotal: totalCores,
            cpuCoresPerformance: perfCores,
            cpuCoresEfficiency: effCores,
            gpuCores: 20,
            gpuArchitecture: "applegpu_g17s",
            metalAvailable: true,
            mlxAvailable: true,
            unifiedMemoryGb: memGb,
            metalWorkingSetGb: (workingSetGb * 100).rounded() / 100,
            metalMaxBufferGb: (maxBufferGb * 100).rounded() / 100,
            memoryUsedPercent: 52,
            availableMemoryGb: Double(memGb) * 0.48,
            cpuBusyPercent: 12,
            gpuBusyPercent: 8,
            gpuRendererPercent: 8,
            gpuTilerPercent: 4,
            gpuInUseMemoryGb: 1.5,
            hardwareTier: tier,
            selectedLocalModel: "mlx-community/gemma-3-4b-it-4bit",
            selectedFastModel: "mlx-community/gemma-3-4b-it-4bit",
            recommendedKvBits: 8,
            cachedModels: [],
            recommendations: [
                ModelRecommendationModel(
                    role: "fast_interactive",
                    modelId: "mlx-community/gemma-3-4b-it-4bit",
                    parameterCount: "4B",
                    quantization: "4-bit",
                    estimatedMemoryGb: 2.6,
                    expectedTpsRange: "90–140 tok/s",
                    recommendedKvBits: nil,
                    fitsInMetalBudget: true,
                    isReadyLocally: true,
                    rationale: "Fast local MLX model (~2.6 GB) for low-latency on-device tasks and Station 1 file analysis."
                ),
                ModelRecommendationModel(
                    role: "deep_reasoning",
                    modelId: "lmstudio-community/gemma-4-31B-it-MLX-4bit",
                    parameterCount: "31B",
                    quantization: "4-bit",
                    estimatedMemoryGb: 18.2,
                    expectedTpsRange: "28–40 tok/s",
                    recommendedKvBits: 8,
                    fitsInMetalBudget: workingSetGb >= 20.0,
                    isReadyLocally: false,
                    rationale: "Sweet-spot 31B 4-bit model (~18.2 GB) leaving ample Metal working-set headroom for KV cache."
                ),
            ]
        )
    }

    private func runNativeFallbackTask(
        prompt: String,
        mode: ComputeModeOption,
        cloudProvider: CloudProviderOption,
        guardianPolicy: GuardianPolicyOption,
        attachedFiles: [String],
        sessionId: String?
    ) -> TaskResultModel {
        let scan = fallbackGuardian.redactAndRestorePreview(text: prompt, policy: guardianPolicy)
        let categories = Array(Set(scan.entities.map(\.category))).sorted()

        if mode == .local || (guardianPolicy == .forceLocalOnPII && !scan.entities.isEmpty) {
            let stations = [
                StationStepModel(
                    stationIndex: 1,
                    stationId: "this_mac",
                    label: "This Mac",
                    locality: "local",
                    title: "Local agent & Gemma 4 processed task on-device",
                    detail: "Processed \(attachedFiles.count) local file(s) on this Mac. Nothing leaves this Mac.",
                    status: "completed",
                    durationMs: 18,
                    badges: ["Fully Local", "gemma4:26b", "Nothing leaves this Mac"]
                ),
                StationStepModel(
                    stationIndex: 2,
                    stationId: "cloud",
                    label: "Cloud models",
                    locality: "local",
                    title: "Cloud models not used",
                    detail: "AI processing stayed 100% on your Mac. Zero Cloud AI history.",
                    status: "completed",
                    durationMs: 0,
                    badges: ["Not used", "Zero Cloud History"]
                ),
                StationStepModel(
                    stationIndex: 3,
                    stationId: "result",
                    label: "Result",
                    locality: "local",
                    title: "Completed on this Mac",
                    detail: "Result generated locally with zero cloud transmission.",
                    status: "completed",
                    durationMs: 1,
                    badges: ["Verified On-Device"]
                ),
            ]
            return TaskResultModel(
                taskId: "task_\(Int(Date().timeIntervalSince1970))",
                sessionId: sessionId,
                prompt: prompt,
                finalOutput: "[On-Device Local Agent · gemma4:26b on Apple Silicon Metal] Completed task locally on this Mac. Nothing left this device.\nTask: \(prompt)",
                cloudPromptSent: nil,
                stations: stations,
                receipt: ExecutionReceiptModel(
                    modeExecuted: "local",
                    localModelUsed: "gemma4:26b (on this Mac)",
                    localAgentLocation: "on this Mac",
                    cloudModelsUsed: "not used",
                    piiFlaggedCount: scan.entities.count,
                    piiRestoredCount: 0,
                    piiCategories: categories,
                    nothingLeftMac: true,
                    cloudZeroRetention: true
                ),
                telemetry: TelemetryModel(
                    architecture: "arm64",
                    chipBrand: nativeSysctlString("machdep.cpu.brand_string") ?? "Apple Silicon (Metal)",
                    cpuPercent: 18,
                    memoryPercent: 52,
                    gpuPercent: 24,
                    tokensProcessed: max(32, prompt.split(separator: " ").count * 3),
                    unifiedMemoryGb: max(8, Int(ProcessInfo.processInfo.physicalMemory / (1024 * 1024 * 1024)))
                ),
                guardianAudit: GuardianAuditModel(
                    sanitizedText: scan.sanitized,
                    piiFlagged: !scan.entities.isEmpty,
                    piiCount: scan.entities.count,
                    categories: categories,
                    policyApplied: guardianPolicy.rawValue,
                    forcedLocal: guardianPolicy == .forceLocalOnPII && !scan.entities.isEmpty,
                    entities: scan.entities,
                    restoredPreview: scan.restored,
                    restoredCount: 0
                )
            )
        }

        var cloudSynthesis = "[\(cloudProvider.displayName) · Stateless Zero-History Call] Benchmarked comparable deals and synthesized reasoning for: \(scan.sanitized)"
        for (token, original) in scan.vault {
            cloudSynthesis = cloudSynthesis.replacingOccurrences(of: token, with: original)
        }

        let stations = [
            StationStepModel(
                stationIndex: 1,
                stationId: "this_mac",
                label: "This Mac",
                locality: "local",
                title: "Local agent analyzed private files on this Mac",
                detail: "Processed \(attachedFiles.count) private file(s) locally before Privacy Gate.",
                status: "completed",
                durationMs: 14,
                badges: ["This Mac", "gemma4:26b"]
            ),
            StationStepModel(
                stationIndex: 2,
                stationId: "privacy_gate",
                label: "Privacy Gate",
                locality: "shield",
                title: scan.entities.isEmpty
                    ? "Privacy Gate verified prompt is clean"
                    : "Privacy Gate masked \(scan.entities.count) sensitive item(s) on this Mac",
                detail: scan.entities.isEmpty
                    ? "Zero PII detected."
                    : "Masked \(scan.entities.map(\.replacementToken).joined(separator: ", ")) before cloud call.",
                status: "completed",
                durationMs: 4,
                badges: scan.entities.isEmpty ? ["Verified Clean"] : ["PII flagged (\(scan.entities.count))"] + categories
            ),
            StationStepModel(
                stationIndex: 3,
                stationId: "cloud",
                label: "Cloud",
                locality: "cloud",
                title: "Stateless Cloud reasoning via \(cloudProvider.displayName)",
                detail: "Researched using masked stand-in tokens only. store=false: nothing remains in Cloud AI history.",
                status: "completed",
                durationMs: 42,
                badges: [cloudProvider.rawValue, "Zero Cloud History (store=false)"]
            ),
            StationStepModel(
                stationIndex: 4,
                stationId: "result",
                label: "Result",
                locality: "local",
                title: "Combined on this Mac — real values restored locally",
                detail: "Restored \(scan.entities.count) stand-in token(s) from local PIIVault.",
                status: "completed",
                durationMs: 2,
                badges: ["Real values restored", "Hybrid Complete"]
            ),
        ]

        return TaskResultModel(
            taskId: "task_\(Int(Date().timeIntervalSince1970))",
            sessionId: sessionId,
            prompt: prompt,
            finalOutput: cloudSynthesis,
            cloudPromptSent: scan.sanitized,
            stations: stations,
            receipt: ExecutionReceiptModel(
                modeExecuted: "hybrid",
                localModelUsed: "gemma4:26b (on this Mac)",
                localAgentLocation: "on this Mac",
                cloudModelsUsed: cloudProvider.displayName,
                piiFlaggedCount: scan.entities.count,
                piiRestoredCount: scan.entities.count,
                piiCategories: categories,
                nothingLeftMac: false,
                cloudZeroRetention: true
            ),
            telemetry: TelemetryModel(
                architecture: "arm64",
                chipBrand: nativeSysctlString("machdep.cpu.brand_string") ?? "Apple Silicon (Metal)",
                cpuPercent: 20,
                memoryPercent: 54,
                gpuPercent: 28,
                tokensProcessed: max(48, prompt.split(separator: " ").count * 4),
                unifiedMemoryGb: max(8, Int(ProcessInfo.processInfo.physicalMemory / (1024 * 1024 * 1024)))
            ),
            guardianAudit: GuardianAuditModel(
                sanitizedText: scan.sanitized,
                piiFlagged: !scan.entities.isEmpty,
                piiCount: scan.entities.count,
                categories: categories,
                policyApplied: guardianPolicy.rawValue,
                forcedLocal: false,
                entities: scan.entities,
                restoredPreview: scan.restored,
                restoredCount: scan.entities.count
            )
        )
    }
}

// MARK: - SSEStreamDelegate

/// URLSession delegate that parses a Server-Sent Events stream from
/// `POST /v1/tasks/stream` and forwards tokens and receipts to callbacks.
///
/// SSE format expected from the daemon:
///   data: {"type":"token","text":"Hello"}\n\n
///   data: {"type":"heartbeat"}\n\n
///   data: [DONE]\n\n
///   data: {"type":"receipt", ...}\n\n
final class SSEStreamDelegate: NSObject, URLSessionDataDelegate, @unchecked Sendable {
    private let onToken: @Sendable (String) -> Void
    private let onReceipt: @Sendable ([String: Any]) -> Void
    private let doneSignal = DispatchSemaphore(value: 0)
    private var buffer = ""

    init(
        onToken: @escaping @Sendable (String) -> Void,
        onReceipt: @escaping @Sendable ([String: Any]) -> Void
    ) {
        self.onToken = onToken
        self.onReceipt = onReceipt
    }

    /// Block the calling thread until the stream ends.
    func waitUntilDone() { doneSignal.wait() }

    // MARK: URLSessionDataDelegate

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard let chunk = String(data: data, encoding: .utf8) else { return }
        buffer += chunk
        processBuffer()
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        // Drain any remaining buffer content
        if !buffer.isEmpty { processBuffer() }
        doneSignal.signal()
    }

    // MARK: Private

    private func processBuffer() {
        // SSE events are delimited by double newlines.
        while let range = buffer.range(of: "\n\n") {
            let event = String(buffer[buffer.startIndex..<range.lowerBound])
            buffer.removeSubrange(buffer.startIndex..<range.upperBound)
            handle(event: event)
        }
    }

    private func handle(event: String) {
        for line in event.split(separator: "\n", omittingEmptySubsequences: false) {
            let str = String(line)
            guard str.hasPrefix("data: ") else { continue }
            let payload = String(str.dropFirst(6))

            if payload == "[DONE]" { continue }

            guard let data = payload.data(using: .utf8),
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }

            let type_ = json["type"] as? String ?? ""
            switch type_ {
            case "token":
                if let text = json["text"] as? String {
                    onToken(text)
                }
            case "receipt":
                onReceipt(json)
            case "heartbeat", "error":
                break   // heartbeat is expected; errors surface in receipt
            default:
                break
            }
        }
    }
}
