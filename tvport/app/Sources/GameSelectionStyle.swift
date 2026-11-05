import SwiftUI
import AppKit

/// Keep native list selection and keyboard navigation, with a softer row highlight.
struct GameSelectionStyle: ViewModifier {
    let selected: Bool
    @Environment(\.colorScheme) private var colorScheme

    func body(content: Content) -> some View {
        content
            .foregroundStyle(.primary)
            .padding(6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background {
                RoundedRectangle(cornerRadius: 8)
                    .fill(selected ? Color.gray.opacity(colorScheme == .dark ? 0.24 : 0.12) : .clear)
            }
            .background(NativeSelectionAppearance().frame(width: 0, height: 0))
    }
}

private struct NativeSelectionAppearance: NSViewRepresentable {
    final class Marker: NSView {
        override func viewDidMoveToSuperview() { super.viewDidMoveToSuperview(); apply() }
        override func viewDidMoveToWindow() { super.viewDidMoveToWindow(); apply() }
        func apply() {
            var parent = superview
            while let view = parent {
                if let table = view as? NSTableView {
                    table.selectionHighlightStyle = .none
                    return
                }
                parent = view.superview
            }
        }
    }
    func makeNSView(context: Context) -> Marker { Marker() }
    func updateNSView(_ view: Marker, context: Context) {
        DispatchQueue.main.async { [weak view] in view?.apply() }
    }
}
