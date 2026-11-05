import AppKit
import SwiftUI

/// One native text document lets Select All and Copy span the entire build log.
struct SelectableLogView: NSViewRepresentable {
    let text: String
    @Environment(\.colorScheme) private var colorScheme

    func makeNSView(context: Context) -> LogTextScrollView {
        LogTextScrollView()
    }

    func updateNSView(_ view: LogTextScrollView, context: Context) {
        view.setDarkAppearance(colorScheme == .dark)
        view.setLog(text)
    }
}

final class LogTextScrollView: NSScrollView {
    let logTextView = NSTextView()
    private var logColor = NSColor.black
    private let logFont = NSFont.monospacedSystemFont(ofSize: NSFont.smallSystemFontSize, weight: .regular)
    private var logAttributes: [NSAttributedString.Key: Any] {
        [.foregroundColor: logColor, .font: logFont]
    }

    init() {
        super.init(frame: .zero)
        drawsBackground = false
        hasVerticalScroller = true
        autohidesScrollers = true
        borderType = .noBorder

        logTextView.isEditable = false
        logTextView.isSelectable = true
        logTextView.isRichText = false
        logTextView.drawsBackground = false
        // SwiftUI supplies the appearance; apply it to stored text as well as
        // typing attributes, since direct textStorage appends bypass typing.
        logTextView.usesAdaptiveColorMappingForDarkAppearance = false
        logTextView.font = logFont
        logTextView.textColor = logColor
        logTextView.typingAttributes = logAttributes
        logTextView.textContainerInset = NSSize(width: 0, height: 2)
        logTextView.textContainer?.lineFragmentPadding = 0
        logTextView.isVerticallyResizable = true
        logTextView.isHorizontallyResizable = false
        logTextView.autoresizingMask = [.width]
        logTextView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        logTextView.textContainer?.widthTracksTextView = true
        logTextView.setAccessibilityLabel("Build log")
        documentView = logTextView
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func setDarkAppearance(_ dark: Bool) {
        let color: NSColor = dark ? .white : .black
        guard color != logColor else { return }
        logColor = color
        logTextView.textColor = color
        logTextView.typingAttributes = logAttributes
        logTextView.textStorage?.addAttributes(logAttributes,
            range: NSRange(location: 0, length: (logTextView.string as NSString).length))
    }

    func setLog(_ text: String) {
        let oldText = logTextView.string
        guard text != oldText else { return }
        let selection = logTextView.selectedRange()
        let visibleOrigin = contentView.bounds.origin
        let followsTail = oldText.isEmpty || (selection.length == 0
            && contentView.bounds.maxY >= logTextView.bounds.maxY - 2)

        // Append without resetting an in-progress selection or the scroll position.
        let oldLength = (oldText as NSString).length
        let newLength = (text as NSString).length
        if text.hasPrefix(oldText) {
            logTextView.textStorage?.append(NSAttributedString(
                string: (text as NSString).substring(from: oldLength), attributes: logAttributes))
        } else {
            logTextView.textStorage?.setAttributedString(NSAttributedString(string: text, attributes: logAttributes))
        }
        let start = min(selection.location, newLength)
        logTextView.setSelectedRange(NSRange(location: start, length: min(selection.length, newLength - start)))
        logTextView.layoutManager?.ensureLayout(for: logTextView.textContainer!)
        if followsTail {
            logTextView.scrollRangeToVisible(NSRange(location: newLength, length: 0))
        } else {
            contentView.scroll(to: visibleOrigin)
            reflectScrolledClipView(contentView)
        }
    }
}
