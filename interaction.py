"""Guarded native interaction priority for the supported build's input tree.

The game evaluates target eligibility when it processes input. No cursor polling,
synthetic Root key, or movement-directed aiming is involved.
"""
import struct
from ue import StaleState


def plan_interaction_priority(u, tree):
    checks = []

    def capture(address, size):
        value = u.read(address, size)
        checks.append((address, value))
        return value

    def array(address, maximum):
        header = capture(address, 16)
        ptr, count, cap = struct.unpack('<Qii', header)
        if not 0 <= count <= cap <= maximum or (count and not ptr):
            raise StaleState('Interaction container is not ready.')
        return ptr, count

    states, count = array(tree + u.offset(tree, 'States'), 400)
    if count != 49:
        raise StaleState('Interaction priority requires the original input tree.')
    ranges = []
    for i in range(count):
        address = states + i * 96
        begin = struct.unpack('<H', u.read(address + 48, 2))[0]
        length = u.read(address + 83, 1)[0]
        ranges.append((begin, length))
    for i, name, original, replacement in [
        (5, 'StationaryMeleeAttack', 59, 77),
        (17, 'InteractionRelease', 77, 74),
    ]:
        address = states + i * 96
        capture(address + 16, 8)
        if u.name_at(address + 16) != name or ranges[i] not in ((original, 1), (replacement, 1)):
            raise StaleState('Interaction condition layout has changed.')
    if ranges[4] != (58, 1):
        raise StaleState('Primary action must retain its native button condition.')
    for i, (begin, length) in enumerate(ranges):
        if i not in (5, 17) and begin <= 77 < begin + length:
            raise StaleState('Interaction condition has another state consumer.')
    transitions, count = array(tree + u.offset(tree, 'Transitions'), 400)
    for i in range(count):
        row = transitions + i * 48
        begin = struct.unpack('<H', u.read(row + 32, 2))[0]
        length = u.read(row + 43, 1)[0]
        if begin <= 77 < begin + length:
            raise StaleState('Interaction condition has a transition consumer.')

    memory, size, count = struct.unpack('<Qii', capture(tree + u.offset(tree, 'Nodes'), 16))
    if count != 106 or not 16 * count <= size <= 65536 or not memory:
        raise StaleState('Interaction nodes have changed.')
    bindings = tree + u.offset(tree, 'PropertyBindings')
    batches, batch_count = array(bindings + 16, 400)
    copies, copy_count = array(bindings + 32, 1000)
    nodes = {}
    for index, expected_batch in ((74, 27), (77, 28)):
        cls, offset = struct.unpack('<Qi', capture(memory + size - (index + 1) * 16, 12))
        if u.name(cls) != 'STC_IsTargetInteractable' or not 0 <= offset <= size - count * 16 - 56:
            raise StaleState('Native interactable condition is unavailable.')
        node = memory + offset
        if struct.unpack('<H', capture(node + 16, 2))[0] != expected_batch:
            raise StaleState('Interaction binding batch changed.')
        if capture(node + 33, 2) != b'\0\0':
            raise StaleState('Interaction condition expression changed.')
        invert = u.read(node + 48, 1)[0]
        if invert not in ((0,) if index == 74 else (0, 1)):
            raise StaleState('Interaction condition inversion changed.')
        if expected_batch >= batch_count:
            raise StaleState('Interaction binding batch is missing.')
        begin, end = struct.unpack('<HH', capture(batches + expected_batch * 24 + 16, 4))
        if end != begin + 1 or end > copy_count:
            raise StaleState('Interaction target binding is ambiguous.')
        copy = copies + begin * 104
        # Both predicates must consume the global cursor target, not attackable target.
        for shift in (0, 24):
            if capture(copy + shift, 7) != b'\xff\xff\0\0\xff\xff\0':
                raise StaleState('Interaction target path changed.')
        if u.name(struct.unpack('<Q', capture(copy + 64, 8))[0]) != 'ST_CurrentTargetInstanceData':
            raise StaleState('Interaction predicate does not use the cursor target.')
        handle_type, handle = struct.unpack('<QQ', capture(copy + 80, 16))
        if u.name(handle_type) != 'StateTreeDataHandle' or capture(handle, 6) != b'\x01\0\0\0\xff\xff':
            raise StaleState('Interaction target is not globally available.')
        nodes[index] = node
    guard = u.guard(tree, checks)
    # Preserve release interactions first, then invert the now-spare predicate,
    # then redirect stationary melee. Journal reverses this order on restoration.
    return [(states + 17 * 96 + 48, struct.pack('<H', 74)),
            (nodes[77] + 48, b'\x01'),
            (states + 5 * 96 + 48, struct.pack('<H', 77))], guard
