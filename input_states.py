"""Select click-movement states without disabling attack or interaction states."""


def movement_states(block_ground, block_approach):
    result = set()
    if block_ground:
        result.update(('MoveTowardsCursor', 'PathTowardsCursor'))
    if block_approach:
        result.add('MoveToInteractable')
    return result


def plan_state_changes(rows, block_ground, block_approach):
    """Validate every expected state before returning any write locations."""
    targets = movement_states(block_ground, block_approach)
    selected = [(name, address, flags) for name, address, flags in rows if name in targets]
    names = [name for name, _, _ in selected]
    if set(names) != targets or len(names) != len(targets):
        raise ValueError('Expected click-movement states are missing or duplicated.')
    return [(address, flags & ~0x20) for _, address, flags in selected]
