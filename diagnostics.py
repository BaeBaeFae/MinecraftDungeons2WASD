"""Bounded local event history and shareable, redacted diagnostic reports."""
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
import traceback


def redact(value):
    if isinstance(value, dict):
        return {str(k): redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    for key in ('USERPROFILE', 'LOCALAPPDATA', 'APPDATA'):
        path = os.environ.get(key)
        if path:
            value = re.sub(re.escape(path), '<local-data>', value, flags=re.I)
            value = re.sub(re.escape(path.replace('\\', '/')), '<local-data>', value, flags=re.I)
    value = re.sub(r'[A-Z]:[\\/][^\r\n\"<>]*', '<path>', value, flags=re.I)
    value = re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '<email>', value)
    value = re.sub(r'\b0x[0-9a-fA-F]{6,}\b', '<address>', value)
    return value[:3000]


class Recorder:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.events = deque(maxlen=200)
        self.errors = deque(maxlen=30)
        self.total_errors = 0
        self.last_saved = -float('inf')
        self.save_error = ''

    def event(self, kind, **details):
        self.events.append(redact({'at': datetime.now(timezone.utc).isoformat(), 'kind': kind, **details}))

    def error(self, exc, operation):
        self.total_errors += 1
        record = redact({'at': datetime.now(timezone.utc).isoformat(), 'operation': operation,
                         'type': type(exc).__name__, 'message': str(exc)})
        # Function/line context distinguishes failing recovery stages without
        # exporting source lines, local variables, or filesystem paths.
        record['frames'] = [{'module': Path(frame.filename).name,
                             'function': frame.name, 'line': frame.lineno}
                            for frame in traceback.extract_tb(exc.__traceback__)[-8:]]
        self.errors.append(record)
        self.event('error', **record)

    def report(self, **details):
        return redact({'schema': 1, **details, 'total_errors': self.total_errors,
                       'recent_errors': list(self.errors), 'events': list(self.events),
                       'automatic_save_error': self.save_error,
                       'privacy': 'No memory dump, full paths, usernames, or process list. Review before sharing.'})

    def save(self, report, force=False):
        now = time.monotonic()
        if not force and now-self.last_saved < 5:
            return
        self.last_saved = now
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            temp = self.folder/'last-session.tmp'
            temp.write_text(json.dumps(redact(report), indent=2), encoding='utf-8')
            temp.replace(self.folder/'last-session.json')
            self.save_error = ''
        except OSError as exc:
            self.save_error = redact(str(exc))
