# TVPort 1.2.3

## Build 44

- Added separate Swap A/B and Swap X/Y controls. Existing combined swaps stay enabled, and new games inherit your most recent choices.
- Reduced automatic save checks to every 30 minutes. Backups are still created only when saves change, keeping the newest 10 automatic copies per game and player/save slot.
- Kept Updates & DLC attachments editable during automatic save checks and fixed the Add Files dialog.
- Kept separate generated game profiles when input files change, fixing the cached base-game profile error when adding an update. Previous profiles are preserved for switching back.
- Made Last Run show the complete available run log, added text-file export for build and run logs, and made the build log follow new output. Save Log now sits beside the status and Show/Hide Log controls.
- Kept the prod.keys picker visible in game settings.
- Made Crop to fill the default for new App Icons and when choosing replacement artwork. Top Shelf uses the App Icon image unless a separate cover is selected, with a clearer Use App Icon Image action.
- Added an in-app warning that Updates & DLC support is under development and may cause games to crash.

Known issue: Snufkin reached gameplay with the newer engine without the game update, but the updated game still crashes during loading. The latest updated-game log repeats the same null-pointer fault as earlier tests. The cause remains under investigation; DLC has not been isolated as the cause. This is not a confirmed crash fix.

Validation for build 44: all 107 TVPort tests and the native controller-mapping tests passed. The Add Files dialog was checked with a test file. The Release app and packaged signature were verified. User testing confirmed Snufkin gameplay without the update and reproduced the updated-game crash; no general DLC compatibility claim is made. The newer engine is retained, with independent controller swaps; no experimental memory rollback is included.

## Original 1.2.3 release (build 32)

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
