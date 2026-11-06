# TVPort 1.2.3

- Added a build queue: prepare several games, see Building and numbered Queued badges, and remove waiting games. Stop or a failed build pauses the queue until you resume it.
- Added each built game’s signing expiry, with a live countdown and local date and time.
- Kept the Mac awake during setup, conversion, building and installation. The display can still turn off, and normal sleep resumes when the work finishes or stops.
- Added a confirmation after a save is successfully restored and verified on Apple TV, with an in-app fallback when notifications are unavailable.
- Automatically back up saves for all supported games installed on the selected Apple TV, including games built on another Mac.
- Save automatic backups only when their contents change, keeping the newest 10 per game and player/save slot. Manual backups, local imports, safety backups and older unlabelled copies are preserved.
- Kept saved backups available to browse during automatic backup, with clearer progress and retry messages. Builds can wait in the queue until backup finishes.
- Added drag-to-position for App Icon and Top Shelf artwork, cached previews for faster switching, and Crop to fill as the default for new Top Shelf covers.
- Fixed artwork disappearing after Stop and build results or installation messages appearing on the wrong game.

The embedded game engine is unchanged from TVPort 1.2. Existing artwork framing choices are retained. The build queue lasts for the current app session; keep TVPort open until it finishes.

Validation: all 103 TVPort tests passed, the Release app built successfully, and its packaged signature and version were verified. The macOS sleep assertion was checked for creation and release. Restore notification permission and fallback paths were tested with a simulated notification client. No new end-to-end game or save-transfer test on Apple TV was performed for this release.
