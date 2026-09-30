import struct
import unittest
from interaction import plan_interaction_priority
from journal import Journal
from ue import StaleState


class Fixture:
    tree, states, nodes, batches, copies = 100, 1000, 7000, 16000, 18000

    def __init__(self):
        self.memory = bytearray(30000)
        self.names = {11: 'STC_IsTargetInteractable', 12: 'ST_CurrentTargetInstanceData',
                      13: 'StateTreeDataHandle'}
        self.props = {'States': 80, 'Transitions': 96, 'Nodes': 112, 'PropertyBindings': 208}
        self.put(self.tree+80, '<Qii', self.states, 49, 49)
        self.put(self.tree+96, '<Qii', 6000, 1, 1)
        self.put(self.tree+112, '<Qii', self.nodes, 7152, 106)
        self.put(self.tree+208+16, '<Qii', self.batches, 29, 29)
        self.put(self.tree+208+32, '<Qii', self.copies, 30, 30)
        self.labels = {self.states+5*96+16: 'StationaryMeleeAttack',
                       self.states+17*96+16: 'InteractionRelease'}
        for i, begin in ((4, 58), (5, 59), (17, 77)):
            self.put(self.states+i*96+48, '<H', begin)
            self.put(self.states+i*96+83, '<B', 1)
        for i, batch, offset in ((74, 27, 100), (77, 28, 200)):
            self.put(self.nodes+7152-(i+1)*16, '<Qi', 11, offset)
            self.put(self.nodes+offset+16, '<H', batch)
            self.put(self.batches+batch*24+16, '<HH', batch, batch+1)
            copy = self.copies+batch*104
            for shift in (0, 24):
                self.write(copy+shift, b'\xff\xff\0\0\xff\xff\0')
            self.put(copy+64, '<Q', 12)
            self.put(copy+80, '<QQ', 13, 24000+batch*8)
            self.write(24000+batch*8, b'\x01\0\0\0\xff\xff')

    def put(self, address, fmt, *values): self.write(address, struct.pack(fmt, *values))
    def write(self, address, value): self.memory[address:address+len(value)] = value
    def read(self, address, size): return bytes(self.memory[address:address+size])
    def name(self, obj): return self.names[obj]
    def name_at(self, address): return self.labels[address]
    def offset(self, obj, key): return self.props[key]
    def guard(self, obj, checks): return lambda: all(self.read(a, len(v)) == v for a, v in checks)


class InteractionTests(unittest.TestCase):
    def test_apply_recheck_and_restore_exactly(self):
        u = Fixture()
        original = bytes(u.memory)
        writes, guard = plan_interaction_priority(u, u.tree)
        journal = Journal(u)
        for a, v in writes: journal.set(a, v, guard)
        self.assertEqual(u.read(u.states+17*96+48, 2), struct.pack('<H', 74))
        self.assertEqual(u.read(u.states+5*96+48, 2), struct.pack('<H', 77))
        self.assertEqual(u.read(u.nodes+200+48, 1), b'\1')
        self.assertEqual(plan_interaction_priority(u, u.tree)[0], writes)
        self.assertEqual(journal.restore_where(), (3, 0))
        self.assertEqual(bytes(u.memory), original)

    def test_reject_attackable_target_instead_of_cursor_target(self):
        u = Fixture()
        u.names[12] = 'ST_CurrentAttackableTargetInstanceData'
        with self.assertRaises(StaleState): plan_interaction_priority(u, u.tree)

    def test_reject_other_condition_consumers(self):
        for transition in (False, True):
            u = Fixture()
            if transition:
                u.put(6000+32, '<H', 77); u.put(6000+43, '<B', 1)
            else:
                u.put(u.states+48, '<H', 77); u.put(u.states+83, '<B', 1)
            with self.assertRaises(StaleState): plan_interaction_priority(u, u.tree)

    def test_target_binding_replacement_invalidates_guard(self):
        u = Fixture()
        _, guard = plan_interaction_priority(u, u.tree)
        u.put(u.copies+27*104+80, '<Q', 99)
        self.assertFalse(guard())

    def test_reject_missing_primary_input_gate(self):
        u = Fixture()
        u.put(u.states+4*96+48, '<H', 81)
        with self.assertRaises(StaleState): plan_interaction_priority(u, u.tree)


if __name__ == '__main__': unittest.main()
