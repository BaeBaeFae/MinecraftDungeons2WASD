import unittest
from input_states import movement_states, plan_state_changes


class InputStatesTests(unittest.TestCase):
    def test_click_paths_are_blocked_without_disabling_interactions(self):
        names = ['Root', 'MoveTowardsCursor', 'PathTowardsCursor', 'MoveWithArtifact',
                 'PathWithArtifact', 'MoveToInteractable', 'InteractionHold',
                 'InteractionRelease', 'TryInteract', 'MeleeAttackHold', 'MeleeAttackAbility']
        rows = [(name, i, 0xff) for i, name in enumerate(names)]
        changes = plan_state_changes(rows, True, True)
        self.assertEqual({names[address] for address, flags in changes}, movement_states(True, True))
        self.assertTrue(all(flags == 0xdf for _, flags in changes))
        self.assertNotIn(6, dict(changes))

    def test_incomplete_or_ambiguous_tree_rejected_before_writes(self):
        rows = [(n, i, 0xff) for i, n in enumerate(sorted(movement_states(True, True)))]
        with self.assertRaises(ValueError): plan_state_changes(rows[:-1], True, True)
        with self.assertRaises(ValueError): plan_state_changes(rows+[rows[0]], True, True)

    def test_independent_options_and_flag_preservation(self):
        rows = [(n, i, i) for i, n in enumerate(sorted(movement_states(True, True)))]
        self.assertEqual(plan_state_changes(rows, False, False), [])
        approach = plan_state_changes(rows, False, True)
        self.assertEqual([rows[i][0] for i, _ in approach], ['MoveToInteractable'])
        for i, flags in plan_state_changes(rows, True, False):
            self.assertEqual(flags, rows[i][2])



if __name__ == '__main__': unittest.main()
