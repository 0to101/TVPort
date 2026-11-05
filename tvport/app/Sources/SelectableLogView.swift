import AppKit
import SwiftUI

/// One native text document lets Select All and Copy span the entire build log.
struct SelectableLogView: NSViewRepresentable {
    let text: String

    func makeNSView(context: Context) -> LogTextScrollView {
        LogTextScrollView()
    }

    func updateNSView(_ view: LogTextScrollView, context: Context) {
        view.setLog(text)
    }
}

final class LogTextScrollView: NSScrollView {
    let logTextView = NSTextView()

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
        logTextView.font = .monospacedSystemFont(ofSize: NSFont.smallSystemFontSize, weight: .regular)
        logTextView.textColor = .labelColor
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
            logTextView.textStorage?.replaceCharacters(in: NSRange(location: oldLength, length: 0),
                with: (text as NSString).substring(from: oldLength))
        } else {
            logTextView.string = text
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
