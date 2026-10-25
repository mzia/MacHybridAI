// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "MacHybridAI",
    platforms: [
        .macOS(.v14)
    ],
    targets: [
        .executableTarget(
            name: "MacHybridAI",
            path: "Sources/MacHybridAI"
        ),
        .testTarget(
            name: "MacHybridAITests",
            dependencies: ["MacHybridAI"],
            path: "Tests/MacHybridAITests"
        ),
    ]
)
