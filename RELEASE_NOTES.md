# 0.1.1 beta test candidate

This build addresses connection recovery and adds diagnostics for the first user reports. It is a test candidate, not a confirmed co-op fix.

- Recover from interrupted memory reads, changed objects, and cleanup/refresh failures without terminating the worker or discarding the undo journal.
- Preserve applied settings and retry automatically in gameplay. Only request title for missing movement mappings.
- Add a process selector to Setup, with Refresh and Show all processes. Manual selection cannot bypass build validation.
- Recognize subclasses of the supported title/gameplay controllers. Show an explicit unknown-screen notice for unrecognized controllers.
- Save a bounded, redacted last-session report on failures. Manual export retains recent errors and the last attached state after fatal failures.
- Add Native interaction mode as an unverified revive workaround: original click behavior returns while WASD/turning remain configured. Jump Slam assist is suspended in this mode. Dodge behavior is unchanged.

36 automated tests pass. Packaged GUI structural checks cover new recovery and detection states. No live game was available; boss rematches, matchmaking guest transitions, co-op revives, and the affected user's title-screen variant remain unverified.

For testing: close the old companion normally, extract the full ZIP, and start this build. After a problem, choose Save diagnostics. The automatic report is at %LOCALAPPDATA%/DungeonsInputStudio/diagnostics/last-session.json. Reports stay local; review before sharing. Include storefront, exact notice, host/guest role, and the transition where it happened.

Multiplayer remains outside the validated support scope. To try the revive workaround, enable Controls → Native interaction mode, Apply settings, and use the game's normal revive interaction. Click-to-move returns in this mode; disable it and Apply to restore your saved click preferences.
