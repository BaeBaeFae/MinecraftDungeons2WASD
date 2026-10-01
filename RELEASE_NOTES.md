# 0.1.3 beta

- Fix automatic recovery getting stuck after a temporary interruption when the same character remains loaded. The companion now reacquires its movement reference without requiring Apply settings.
- Fix the resulting repeated read errors with Jump Slam enabled and inactive turning with it disabled. Existing settings and restoration records are preserved.
- Improve local diagnostics with bounded filename, function, and line context, without full paths, source text, or local variables.

All 62 automated tests and the packaged GUI smoke check pass. A regression test reproduces the prior failure through the real engine synchronization code and verifies recovery with Jump Slam both enabled and disabled. The original live-game interruption has not been reproduced.

Version 0.1.2 users can use Check updates, Download update, then Restart & update. Earlier versions need a manual download. Support for both previously verified Steam builds is retained; Microsoft Store compatibility remains unverified.
