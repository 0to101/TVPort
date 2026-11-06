import SwiftUI
import UniformTypeIdentifiers

struct LogTextDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.plainText] }
    var text: String

    init(text: String) { self.text = text }

    init(configuration: ReadConfiguration) throws {
        guard let data = configuration.file.regularFileContents,
              let text = String(data: data, encoding: .utf8) else {
            throw CocoaError(.fileReadInapplicableStringEncoding)
        }
        self.text = text
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: Data(text.utf8))
    }
}

struct LogExportButton: View {
    let text: String
    let filename: String
    @State private var document = LogTextDocument(text: "")
    @State private var exporting = false
    @State private var exportError: String?

    var body: some View {
        Button("Save Log…") {
            // Capture the complete log when clicked, even if a build keeps running.
            document = LogTextDocument(text: text)
            exporting = true
        }
        .disabled(text.isEmpty)
        .fileExporter(isPresented: $exporting, document: document, contentType: .plainText,
                      defaultFilename: filename.replacingOccurrences(of: "/", with: "-")) { result in
            if case .failure(let error) = result { exportError = error.localizedDescription }
        }
        .alert("Couldn’t save log", isPresented: Binding(
            get: { exportError != nil }, set: { if !$0 { exportError = nil } })) {
                Button("OK") { exportError = nil }
            } message: { Text(exportError ?? "") }
    }
}
