"""Undo only owned, unchanged data whose owning objects are still valid."""
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class Entry:
    address: int
    original: bytes
    last: bytes
    guard: object
    key: bool = False


class Journal:
    def __init__(self, process):
        self.p = process
        self.entries = {}
        self.path = None
        self.session = None

    def attach_store(self, path, session, guard_factory):
        self.path, self.session = Path(path), session
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('schema') != 1 or data.get('session') != session:
            raise RuntimeError('Control backup belongs to another game session. No saved addresses were used.')
        for row in data['entries']:
            guard = self.p.alive if row['guard'].get('process') else guard_factory(row['guard'])
            entry = Entry(row['address'], bytes.fromhex(row['original']), bytes.fromhex(row['last']), guard, row['key'])
            if guard():
                self.entries[entry.address] = entry

    def save(self):
        if self.path is None:
            return
        rows = []
        for entry in self.entries.values():
            record = getattr(entry.guard, 'record', None)
            if record is None and entry.guard == self.p.alive:
                record = {'process': True}
            if record is None:
                raise RuntimeError('Cannot record the original control safely; changes cancelled.')
            rows.append({'address': entry.address, 'original': entry.original.hex(),
                         'last': entry.last.hex(), 'key': entry.key, 'guard': record})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps({'schema': 1, 'session': self.session, 'entries': rows}, indent=2), encoding='utf-8')
        temp.replace(self.path)

    def set(self, address, value, guard, key=False, original=None):
        if not guard():
            raise RuntimeError('Object changed before write; update cancelled.')
        current = self.p.read(address, len(value))
        entry = self.entries.get(address)
        if entry and not entry.guard():
            self.entries.pop(address)
            entry = None
        if current == value:
            return
        if not entry:
            entry = Entry(address, current if original is None else original, value, guard, key)
            self.entries[address] = entry
            self.save()  # Record the original before the first write, including crash recovery.
        elif key:
            entry.last = value
            self.save()
        # Clear FKey's lazy detail cache; never borrow shared ownership from another key.
        self.p.write(address, value + bytes(16) if key else value)
        if self.p.read(address, len(value)) != value:
            raise RuntimeError('Game data changed during verification.')
        entry.last = value

    def restore_where(self, predicate=lambda entry: True):
        restored = skipped = 0
        for address, entry in reversed(list(self.entries.items())):
            if not predicate(entry):
                continue
            try:
                if entry.guard() and self.p.read(address, len(entry.last)) == entry.last:
                    self.p.write(address, entry.original + bytes(16) if entry.key else entry.original)
                    if self.p.read(address, len(entry.original)) != entry.original:
                        raise RuntimeError('Original control could not be verified after restoration.')
                    restored += 1
                else:
                    skipped += 1
            except RuntimeError:
                skipped += 1
                continue  # Keep failed writes available for an explicit retry.
            del self.entries[address]
        self.save()
        return restored, skipped

    def prune(self):
        for address, entry in list(self.entries.items()):
            if not entry.guard():
                del self.entries[address]
