import SwiftUI

/// Separate push buttons whose appearance stays consistent inside the native toolbar.
struct ToolbarActionButton: View {
    let title: String
    var enabled = true
    var primary = false
    var help = ""
    var action: () -> Void

    var body: some View {
        Group {
            if primary {
                Button(title, action: action)
                    .keyboardShortcut("b")
            } else {
                Button(title, action: action)
            }
        }
        .buttonStyle(ToolbarPushButtonStyle(primary: primary))
        .controlSize(.regular)
        .disabled(!enabled)
        .help(help)
        .fixedSize()
    }
}

private struct ToolbarPushButtonStyle: ButtonStyle {
    let primary: Bool
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(.horizontal, 10).padding(.vertical, 5)
            .foregroundStyle(primary ? Color.white : Color.primary)
            .background {
                RoundedRectangle(cornerRadius: 5)
                    .fill(primary ? Color.accentColor : Color(nsColor: .controlColor))
            }
            .contentShape(RoundedRectangle(cornerRadius: 5))
            .opacity(isEnabled ? (configuration.isPressed ? 0.75 : 1) : 0.4)
    }
}
