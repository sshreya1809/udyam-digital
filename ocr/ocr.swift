import Foundation
import Vision
import AppKit

// Prints recognised text lines as JSON: [{"text", "alts" (top-3 readings), "conf", "x", "y"}]
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let img = NSImage(contentsOf: url),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(1) }
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
try VNImageRequestHandler(cgImage: cg).perform([req])
let out = (req.results ?? []).compactMap { o -> [String: Any]? in
    let cands = o.topCandidates(3)
    guard let c = cands.first else { return nil }
    return ["text": c.string, "alts": cands.map { $0.string }, "conf": c.confidence,
            "x": o.boundingBox.minX, "y": 1 - o.boundingBox.maxY, "h": o.boundingBox.height]
}
print(String(data: try JSONSerialization.data(withJSONObject: out), encoding: .utf8)!)
