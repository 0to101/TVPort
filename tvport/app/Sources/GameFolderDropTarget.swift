import SwiftUI

/// Shared by the empty library and sidebar; importing follows the folder picker's path.
struct GameFolderDropTarget: ViewModifier {
    let addFolder: (URL) -> Void
    @State private var isTargeted = false

    func body(content: Content) -> some View {
        content
            .contentShape(Rectangle())
            .overlay {
                if isTargeted {
                    RoundedRectangle(cornerRadius: 10)
                        .fill(Color.accentColor.opacity(0.08))
                        .overlay {
                            RoundedRectangle(cornerRadius: 10)
                                .strokeBorder(Color.accentColor, style: StrokeStyle(lineWidth: 2, dash: [6]))
                        }
                        .padding(4)
                        .allowsHitTesting(false)
                        .accessibilityHidden(true)
                }
            }
            .dropDestination(for: URL.self) { urls, _ in
                let folders = urls.filter { url in
                    guard url.isFileURL,
                          let values = try? url.resourceValues(forKeys: [.isDirectoryKey, .isPackageKey]) else { return false }
                    return values.isDirectory == true && values.isPackage != true
                }
                for folder in folders { addFolder(folder.standardizedFileURL) }
                return !folders.isEmpty
            } isTargeted: { isTargeted = $0 }
    }
}
