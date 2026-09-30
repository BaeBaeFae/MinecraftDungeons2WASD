"""Validated reflection and object discovery for the single supported game build."""
import struct


class StaleState(RuntimeError):
    pass


class UE:
    def __init__(self, process):
        self.p = process
        self.base = process.base
        self.read = process.read
        self.u64 = process.u64
        self.names = {0: 'None'}
        self.name_ids = {}
        self.index = {}
        self.offsets = {}

    def fname(self, index, number=0):
        if index not in self.names:
            block_count = struct.unpack('<I', self.read(self.base + 0xBDC5048, 4))[0]
            if index >> 16 > block_count:
                raise StaleState('Name no longer valid.')
            block = self.u64(self.base + 0xBDC5050 + (index >> 16) * 8)
            entry = block + (index & 65535) * 2
            head = struct.unpack('<H', self.read(entry, 2))[0]
            length = head >> 6
            if not 0 < length < 1024:
                raise StaleState('Invalid object name.')
            self.names[index] = self.read(entry + 2, length * (2 if head & 1 else 1)).decode(
                'utf-16le' if head & 1 else 'utf-8', errors='strict')
        return self.names[index] + (f'_{number-1}' if number else '')

    def name_at(self, address):
        return self.fname(*struct.unpack('<II', self.read(address, 8)))

    def name(self, obj):
        return self.name_at(obj + 24) if obj else 'None'

    def class_name(self, obj):
        return self.name(self.u64(obj + 16))

    def array(self, address, maximum=1000):
        pointer, count, capacity = struct.unpack('<Qii', self.read(address, 16))
        if not 0 <= count <= capacity <= maximum or (count and not pointer):
            raise StaleState('Container changed or is not ready.')
        return pointer, count

    def identity(self, obj):
        index = struct.unpack('<i', self.read(obj + 12, 4))[0]
        chunks = self.u64(self.base + 0xBEA8C00)
        count = struct.unpack('<i', self.read(self.base + 0xBEA8C14, 4))[0]
        if not 0 <= index < count:
            raise StaleState('Object has expired.')
        item = self.u64(chunks + (index >> 16) * 8) + (index & 65535) * 24
        data = self.read(item, 24)
        if struct.unpack_from('<Q', data)[0] != obj or struct.unpack_from('<I', data, 8)[0] & 0x10200000:
            raise StaleState('Object is being destroyed.')
        return obj, index, struct.unpack_from('<I', data, 16)[0]

    def valid(self, identity):
        try:
            return self.identity(identity[0]) == identity
        except (RuntimeError, OSError):
            return False

    def guard(self, obj, checks=()):
        identity = self.identity(obj)
        def valid():
            try:
                return self.valid(identity) and all(self.read(a, len(v)) == v for a, v in checks)
            except RuntimeError:
                return False
        valid.record = {'identity': list(identity), 'checks': [[a, v.hex()] for a, v in checks]}
        return valid

    def saved_guard(self, record):
        identity = tuple(record['identity'])
        checks = [(a, bytes.fromhex(v)) for a, v in record['checks']]
        def valid():
            try:
                return self.valid(identity) and all(self.read(a, len(v)) == v for a, v in checks)
            except RuntimeError:
                return False
        valid.record = record
        return valid

    def refresh(self):
        index = {}
        chunks = self.u64(self.base + 0xBEA8C00)
        count = struct.unpack('<i', self.read(self.base + 0xBEA8C14, 4))[0]
        if not 0 < count < 2000000:
            raise StaleState('Object registry is not ready.')
        for chunk in range((count + 65535) // 65536):
            data = self.read(self.u64(chunks + chunk * 8), min(65536, count-chunk*65536)*24)
            for offset in range(0, len(data), 24):
                obj, flags = struct.unpack_from('<QI', data, offset)
                if not obj or flags & 0x10200000:
                    continue
                try:
                    header = self.read(obj, 40)
                    cname = self.name(struct.unpack_from('<Q', header, 16)[0])
                    # Only retain classes relevant to input; no actor or inventory scan.
                    if cname in ('DungeonsLocalPlayer', 'GameInstanceSWTypeSystem', 'InputMappingContext',
                                 'SWEnhancedPlayerMappableKeyProfile', 'StateTree'):
                        name = self.fname(*struct.unpack_from('<II', header, 24))
                        if not name.startswith('Default__'):
                            index.setdefault(cname, []).append((obj, name))
                except (RuntimeError, UnicodeError):
                    continue
        self.index = index

    def objects(self, cname):
        found = []
        for obj, name in self.index.get(cname, []):
            try:
                if self.safe_valid(obj) and self.class_name(obj) == cname and self.name(obj) == name:
                    found.append((obj, name))
            except RuntimeError:
                continue
        return found

    def safe_valid(self, obj):
        try:
            self.identity(obj)
            return True
        except RuntimeError:
            return False

    def one(self, cname, name=None):
        found = [(obj, nm) for obj, nm in self.objects(cname) if name is None or nm == name]
        if len(found) != 1:
            raise StaleState(f'{name or cname} is not ready or is ambiguous ({len(found)}).')
        return found[0][0]

    def offset(self, obj, key):
        cls = self.u64(obj + 16)
        cache_key = (cls, key)
        if cache_key in self.offsets:
            return self.offsets[cache_key]
        for _ in range(64):
            if not cls:
                break
            field = self.u64(cls + 80)
            for _ in range(2048):
                if not field:
                    break
                data = self.read(field, 80)
                if self.fname(*struct.unpack_from('<II', data, 32)) == key:
                    value = struct.unpack_from('<I', data, 72)[0]
                    self.offsets[cache_key] = value
                    return value
                field = struct.unpack_from('<Q', data, 24)[0]
            cls = self.u64(cls + 64)
        raise StaleState(f'Missing property: {key}.')

    def key_name(self, key):
        if not self.name_ids:
            block, cursor = struct.unpack('<II', self.read(self.base + 0xBDC5048, 8))
            if block > 1024:
                raise StaleState('Invalid name registry.')
            for bi in range(block + 1):
                data = self.read(self.u64(self.base + 0xBDC5050 + bi*8), cursor if bi == block else 131072)
                pos = 0
                while pos + 2 <= len(data):
                    head = struct.unpack_from('<H', data, pos)[0]
                    length = head >> 6
                    if not length:
                        break
                    end = pos + 2 + length * (2 if head & 1 else 1)
                    if end > len(data):
                        break
                    name = data[pos+2:end].decode('utf-16le' if head & 1 else 'utf-8', errors='replace')
                    self.name_ids[name] = (bi << 16) + pos//2
                    pos = (end + 1) & ~1
        if key not in self.name_ids:
            raise StaleState(f'Key {key} is not available in this game build.')
        return struct.pack('<II', self.name_ids[key], 0)

    def fstring(self, address):
        pointer, count = self.array(address, 2048)
        return self.read(pointer, count*2).decode('utf-16le').rstrip('\0') if count else ''
