#!/usr/bin/env swift
import AppKit
import CoreGraphics
import Foundation

/// Generates a custom 1024x1024 PNG icon for MacHybridAI depicting:
/// - Left half: Apple Silicon Local Chip (Cyan/Teal)
/// - Center: Privacy Gate PII Filter Bridge (Gold/Emerald)
/// - Right half: Stateless Cloud AI Node (Purple/Indigo)
/// - Bottom badge: "HYBRID AI"
func renderIcon(size: Int) -> NSImage {
    let imgSize = NSSize(width: size, height: size)
    let image = NSImage(size: imgSize)
    image.lockFocus()

    guard let ctx = NSGraphicsContext.current?.cgContext else {
        image.unlockFocus()
        return image
    }

    let rect = CGRect(x: 0, y: 0, width: CGFloat(size), height: CGFloat(size))
    let inset = CGFloat(size) * 0.06
    let cardRect = rect.insetBy(dx: inset, dy: inset)
    let cornerRadius = CGFloat(size) * 0.22

    // 1. Rounded squircle background with deep midnight-to-indigo gradient
    let bgPath = CGPath(roundedRect: cardRect, cornerWidth: cornerRadius, cornerHeight: cornerRadius, transform: nil)
    ctx.saveGState()
    ctx.addPath(bgPath)
    ctx.clip()

    let colorSpace = CGColorSpaceCreateDeviceRGB()
    let bgColors = [
        CGColor(red: 0.05, green: 0.09, blue: 0.18, alpha: 1.0),
        CGColor(red: 0.09, green: 0.14, blue: 0.28, alpha: 1.0),
        CGColor(red: 0.16, green: 0.10, blue: 0.30, alpha: 1.0),
    ] as CFArray
    if let gradient = CGGradient(colorsSpace: colorSpace, colors: bgColors, locations: [0.0, 0.55, 1.0]) {
        ctx.drawLinearGradient(
            gradient,
            start: CGPoint(x: cardRect.minX, y: cardRect.maxY),
            end: CGPoint(x: cardRect.maxX, y: cardRect.minY),
            options: []
        )
    }

    // Subtle split glow: Cyan on left (Local Mac), Violet on right (Cloud AI)
    ctx.setFillColor(CGColor(red: 0.0, green: 0.78, blue: 0.92, alpha: 0.14))
    ctx.fillEllipse(in: CGRect(x: cardRect.minX - CGFloat(size) * 0.1, y: cardRect.midY - CGFloat(size) * 0.3, width: CGFloat(size) * 0.6, height: CGFloat(size) * 0.6))

    ctx.setFillColor(CGColor(red: 0.62, green: 0.32, blue: 0.98, alpha: 0.16))
    ctx.fillEllipse(in: CGRect(x: cardRect.midX, y: cardRect.midY - CGFloat(size) * 0.3, width: CGFloat(size) * 0.6, height: CGFloat(size) * 0.6))
    ctx.restoreGState()

    // Outer metallic border
    ctx.addPath(bgPath)
    ctx.setStrokeColor(CGColor(red: 0.38, green: 0.78, blue: 0.95, alpha: 0.55))
    ctx.setLineWidth(max(2.0, CGFloat(size) * 0.014))
    ctx.strokePath()

    let centerY = CGFloat(size) * 0.55

    // 2. Left Node: Local Mac Silicon Chip (Cyan)
    let chipSize = CGFloat(size) * 0.26
    let chipCenterX = CGFloat(size) * 0.28
    let chipRect = CGRect(
        x: chipCenterX - chipSize / 2,
        y: centerY - chipSize / 2,
        width: chipSize,
        height: chipSize
    )
    let chipPath = CGPath(
        roundedRect: chipRect,
        cornerWidth: chipSize * 0.18,
        cornerHeight: chipSize * 0.18,
        transform: nil
    )

    // Chip pins
    ctx.setStrokeColor(CGColor(red: 0.18, green: 0.88, blue: 0.96, alpha: 0.9))
    ctx.setLineWidth(max(2.0, CGFloat(size) * 0.016))
    let pinOffsets: [CGFloat] = [-0.28, 0.0, 0.28]
    let pinLen = chipSize * 0.16
    for offset in pinOffsets {
        let px = chipCenterX + chipSize * offset
        // Top & bottom pins
        ctx.move(to: CGPoint(x: px, y: chipRect.maxY))
        ctx.addLine(to: CGPoint(x: px, y: chipRect.maxY + pinLen))
        ctx.move(to: CGPoint(x: px, y: chipRect.minY))
        ctx.addLine(to: CGPoint(x: px, y: chipRect.minY - pinLen))
        // Left & right pins
        let py = centerY + chipSize * offset
        ctx.move(to: CGPoint(x: chipRect.minX, y: py))
        ctx.addLine(to: CGPoint(x: chipRect.minX - pinLen, y: py))
    }
    ctx.strokePath()

    ctx.addPath(chipPath)
    ctx.setFillColor(CGColor(red: 0.06, green: 0.26, blue: 0.36, alpha: 0.95))
    ctx.fillPath()
    ctx.addPath(chipPath)
    ctx.setStrokeColor(CGColor(red: 0.22, green: 0.90, blue: 0.98, alpha: 1.0))
    ctx.setLineWidth(max(2.0, CGFloat(size) * 0.018))
    ctx.strokePath()

    // 3. Right Node: Cloud AI Constellation Circle (Purple/Magenta)
    let cloudRadius = CGFloat(size) * 0.13
    let cloudCenterX = CGFloat(size) * 0.72
    let cloudRect = CGRect(
        x: cloudCenterX - cloudRadius,
        y: centerY - cloudRadius,
        width: cloudRadius * 2,
        height: cloudRadius * 2
    )
    ctx.setFillColor(CGColor(red: 0.24, green: 0.12, blue: 0.42, alpha: 0.95))
    ctx.fillEllipse(in: cloudRect)
    ctx.setStrokeColor(CGColor(red: 0.75, green: 0.48, blue: 1.0, alpha: 1.0))
    ctx.setLineWidth(max(2.0, CGFloat(size) * 0.018))
    ctx.strokeEllipse(in: cloudRect)

    // 4. Connecting Neural Bridge + Center Privacy Gate Lock Node (Gold/Emerald)
    ctx.setStrokeColor(CGColor(red: 0.98, green: 0.78, blue: 0.28, alpha: 0.95))
    ctx.setLineWidth(max(2.5, CGFloat(size) * 0.02))
    ctx.move(to: CGPoint(x: chipRect.maxX + 4, y: centerY))
    ctx.addLine(to: CGPoint(x: cloudRect.minX - 4, y: centerY))
    ctx.strokePath()

    let gateRadius = CGFloat(size) * 0.075
    let gateRect = CGRect(
        x: CGFloat(size) * 0.5 - gateRadius,
        y: centerY - gateRadius,
        width: gateRadius * 2,
        height: gateRadius * 2
    )
    ctx.setFillColor(CGColor(red: 0.10, green: 0.34, blue: 0.26, alpha: 1.0))
    ctx.fillEllipse(in: gateRect)
    ctx.setStrokeColor(CGColor(red: 0.30, green: 0.95, blue: 0.68, alpha: 1.0))
    ctx.setLineWidth(max(2.0, CGFloat(size) * 0.016))
    ctx.strokeEllipse(in: gateRect)

    // Draw labels inside nodes when size >= 64
    if size >= 64 {
        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = .center

        let mAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: CGFloat(size) * 0.11, weight: .heavy),
            .foregroundColor: NSColor(calibratedRed: 0.45, green: 0.96, blue: 1.0, alpha: 1.0),
            .paragraphStyle: paragraph,
        ]
        let mStr = NSString(string: "M")
        let mSize = mStr.size(withAttributes: mAttrs)
        mStr.draw(
            in: CGRect(
                x: chipCenterX - mSize.width / 2,
                y: centerY - mSize.height / 2,
                width: mSize.width,
                height: mSize.height
            ),
            withAttributes: mAttrs
        )

        let aiAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: CGFloat(size) * 0.095, weight: .black),
            .foregroundColor: NSColor(calibratedRed: 0.88, green: 0.72, blue: 1.0, alpha: 1.0),
            .paragraphStyle: paragraph,
        ]
        let aiStr = NSString(string: "AI")
        let aiSize = aiStr.size(withAttributes: aiAttrs)
        aiStr.draw(
            in: CGRect(
                x: cloudCenterX - aiSize.width / 2,
                y: centerY - aiSize.height / 2,
                width: aiSize.width,
                height: aiSize.height
            ),
            withAttributes: aiAttrs
        )

        // Bottom pill: "HYBRID"
        let pillWidth = CGFloat(size) * 0.64
        let pillHeight = CGFloat(size) * 0.14
        let pillRect = CGRect(
            x: (CGFloat(size) - pillWidth) / 2,
            y: CGFloat(size) * 0.14,
            width: pillWidth,
            height: pillHeight
        )
        let pillPath = CGPath(
            roundedRect: pillRect,
            cornerWidth: pillHeight / 2,
            cornerHeight: pillHeight / 2,
            transform: nil
        )
        ctx.addPath(pillPath)
        ctx.setFillColor(CGColor(red: 0.08, green: 0.18, blue: 0.30, alpha: 0.92))
        ctx.fillPath()
        ctx.addPath(pillPath)
        ctx.setStrokeColor(CGColor(red: 0.30, green: 0.88, blue: 0.96, alpha: 0.75))
        ctx.setLineWidth(max(1.5, CGFloat(size) * 0.01))
        ctx.strokePath()

        let badgeAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: CGFloat(size) * 0.072, weight: .bold),
            .foregroundColor: NSColor.white,
            .paragraphStyle: paragraph,
        ]
        let badgeStr = NSString(string: "HYBRID AI")
        let badgeSize = badgeStr.size(withAttributes: badgeAttrs)
        badgeStr.draw(
            in: CGRect(
                x: pillRect.midX - badgeSize.width / 2,
                y: pillRect.midY - badgeSize.height / 2,
                width: badgeSize.width,
                height: badgeSize.height
            ),
            withAttributes: badgeAttrs
        )
    }

    image.unlockFocus()
    return image
}

func savePNG(_ image: NSImage, to url: URL) throws {
    guard let tiffData = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: tiffData),
          let pngData = bitmap.representation(using: .png, properties: [:]) else {
        throw NSError(domain: "IconGen", code: 1)
    }
    try pngData.write(to: url)
}

let args = CommandLine.arguments
let outIconsetPath = args.count > 1 ? args[1] : "build/AppIcon.iconset"
let iconsetURL = URL(fileURLWithPath: outIconsetPath, isDirectory: true)
try FileManager.default.createDirectory(at: iconsetURL, withIntermediateDirectories: true)

let specs: [(name: String, pixels: Int)] = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]

for spec in specs {
    let img = renderIcon(size: spec.pixels)
    try savePNG(img, to: iconsetURL.appendingPathComponent(spec.name))
}
print("Generated MacHybridAI iconset at \(outIconsetPath)")
