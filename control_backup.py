"""Portable key names for bindings the companion owns, independent of heap addresses."""
import json
from pathlib import Path


class ControlBackup:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {'schema': 1, 'original_bindings': None, 'managed': {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('schema') != 1 or not isinstance(self.data.get('managed'), dict):
                raise RuntimeError('The original-controls backup is unreadable. No new changes were applied.')

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
        temp.replace(self.path)

    def capture(self, bindings):
        if self.data['original_bindings'] is None:
            self.data['original_bindings'] = bindings
            self.save()

    def record(self, role, current, wanted):
        if current == wanted:
            return
        old = self.data['managed'].get(role)
        original = old['original'] if old and current == old['last'] else current
        self.data['managed'][role] = {'original': original, 'last': wanted}
        self.save()

    def wanted(self, role, current):
        entry = self.data['managed'].get(role)
        return entry['original'] if entry and current == entry['last'] else None

    def restored(self, role):
        if role in self.data['managed']:
            del self.data['managed'][role]
            self.save()
