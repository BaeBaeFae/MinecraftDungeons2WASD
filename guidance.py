"""User-facing connection states; usable without Windows or a running game."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Guidance:
    stage: str
    title: str
    detail: str
    next_action: str
    tone: str = 'info'
    progress: int = 0
    can_start: bool = False
    can_apply: bool = False
    can_stop: bool = True
    checks: tuple = ()


def guide(stage, detail='', checks=(), configured=False):
    catalog = {
        'idle': ('Start at the game’s title screen', 'Follow the four steps below to set up this session.',
                 'Open the game, stay at the title screen, then click Start companion.', 'info', 0, True, False, False),
        'waiting_game': ('Waiting for the game', 'The companion is running, but the game has not been detected yet.',
                         'Launch Minecraft Dungeons II and stay at its title screen. We will connect automatically.', 'waiting', 0, False, False, True),
        'connecting': ('Connecting to the game…', 'Checking the game version and finding its controls. This can take a few seconds.',
                       'Stay at the title screen while this check completes.', 'waiting', 1, False, False, True),
        'return_title': ('Return to the title screen', 'The current character is missing the native movement mappings needed for keyboard movement.',
                         'Return to the title screen. When it is detected, click Apply settings here before loading your character.', 'warning', 0, False, False, True),
        'resume': ('Ready to resume — stay in your game', 'All four native movement mappings are already loaded for this character.',
                   'Click Apply settings to enable your chosen controls. You do not need to return to title.', 'info', 2, False, True, True),
        'apply': ('Title screen detected — apply your settings', 'The game version is supported and the companion is connected.',
                  'Choose your controls and turning options, then click Apply settings. Stay at title until this step finishes.', 'info', 2, False, True, True),
        'applying': ('Applying settings…', 'Updating the game’s input configuration.',
                     'Keep keys and mouse buttons released while settings are applied.', 'waiting', 2, False, False, True),
        'load_character': ('Settings applied — load your character', 'Title-screen setup is complete. Gameplay controls will activate after loading.',
                          'Switch to the game, press Play, and load your character. Keep this app open.', 'info', 3, False, True, True),
        'loading': ('Waiting for the character to load…', 'The game is changing screens or loading its input objects.',
                    'Let the game finish loading. The companion will check again automatically.', 'waiting', 3 if configured else 1, False, configured, True),
        'active': ('Working — controls are active', 'The selected settings have been applied to the current character.',
                   'Play normally. Keep the companion open; use Apply settings after changing an option.', 'success', 4, False, True, True),
        'needs_reload': ('Movement setup needs one more load', 'The character loaded without all four native movement mappings.',
                         'Return to title, click Apply settings, then load your character again. Also check any key conflicts listed below.', 'warning', 3, False, True, True),
        'conflict': ('Action needed — movement key conflict', 'A movement key is also assigned to another game action.',
                     'Rebind the listed actions in the game’s Controls settings. We will recheck automatically.', 'warning', 3, False, True, True),
        'assist_warning': ('Movement ready — Jump Slam assist needs attention', 'The other controls remain available.',
                           'Check the Jump Slam binding in Controls and in the game, then Apply settings. You can also switch the assist off.', 'warning', 4, False, True, True),
        'recovering': ('Controls are not ready yet', 'The companion cannot currently verify the game’s input state.',
                       'If a screen is loading, wait. Otherwise return to title, click Apply settings, and reload your character.', 'warning', 3 if configured else 1, False, configured, True),
        'stopped': ('Companion stopped', 'This app is no longer updating the game’s controls.',
                    'Click Start companion, then Apply settings. Stay in gameplay if the mappings are ready; return to title only when prompted.', 'info', 0, True, False, False),
        'restore_warning': ('Some changes could not be restored', 'The game state changed while the companion was stopping.',
                            'Restart the game to clear remaining runtime changes before reconnecting.', 'warning', 0, True, False, False),
        'unsupported': ('This game version is not supported', 'The companion refused to modify an unrecognized game build.',
                        'Use a companion release that supports your installed game version. Your game was not patched.', 'error', 1, True, False, False),
        'error': ('Connection stopped — action needed', 'The companion encountered an error and stopped updating controls.',
                  'Return to title and click Retry connection. If this repeats, save diagnostics from Setup & diagnostics.', 'error', 1, True, False, False),
    }
    values = catalog[stage]
    title, description, next_action, tone, progress, start, apply, stop = values
    return Guidance(stage, title, description + ('\n' + detail if detail else ''), next_action,
                    tone, progress, start, apply, stop, tuple(checks))


def classify_error(error):
    return 'unsupported' if 'Unsupported game build' in str(error) else 'error'


STEPS = (
    ('Open the title screen', 'Launch Minecraft Dungeons II. Stay at the title screen before loading your character.'),
    ('Start companion', 'Click Start companion here. Wait for “Title screen detected.”'),
    ('Apply settings', 'Choose your options, then click Apply settings while you are still at title.'),
    ('Load your character', 'Press Play in the game. Wait for the green “Working” status here.'),
)
