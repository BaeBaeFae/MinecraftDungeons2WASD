"""Supported-build adapter. All writes are to validated live data, never image code."""
import math
import struct
import time
from journal import Journal
from model import angle_error, step
from ue import UE, StaleState


class Engine:
    FLAG = 0xC068610

    def __init__(self, process, settings):
        self.p, self.settings = process, settings.validate().effective()
        self.u = UE(process)
        self.journal = Journal(process)
        self.u.refresh()
        self.local = self.u.one('DungeonsLocalPlayer')
        self.local_guard = self.u.guard(self.local)
        self.move = self.pc = self.pawn = 0
        self.move_guard = lambda: False
        self.speed = 0.0
        self.sign = 0
        self.status = 'Attached; checking input mappings'
        self.conflicts = []
        self.last_refresh = time.monotonic()
        self.tick_number = 0
        self.phase = 'loading'
        self.checks = []
        from slam import SlamAssist, WindowsInput
        self.slam = SlamAssist(WindowsInput(process.pid))
        self.slam_key = None
        self.slam_problem = ''
        self.slam_mode_offset = None
        self.slam_binding_guard = lambda: False

    def release_inputs(self):
        self.slam.reset()

    def enable_backup(self, folder):
        from pathlib import Path
        import json
        folder = Path(folder)
        session = self.p.session_id()
        self.journal.attach_store(folder/f'restore-{session}.json',
                                  {'session': session, 'hash': self.p.hash}, self.u.saved_guard)
        self.controls_backup = folder/f'original-controls-{session}.json'
        from control_backup import ControlBackup
        self.binding_backup = ControlBackup(folder/'control-bindings.json')

    def capture_controls(self):
        import json
        path = getattr(self, 'controls_backup', None)
        if path is None or path.exists():
            return
        rows = [{'action': name, 'key': self.u.name_at(mapping+0x48)}
                for name, mapping, guard in self.profile_rows()]
        self.binding_backup.capture(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps({'session': self.p.session_id(), 'bindings': rows}, indent=2), encoding='utf-8')
        temp.replace(path)

    def record_binding(self, role, current, wanted):
        if hasattr(self, 'binding_backup'):
            self.binding_backup.record(role, current, wanted)

    def restore_saved_bindings(self):
        backup = getattr(self, 'binding_backup', None)
        if not backup or not backup.data['managed']:
            return 0, 0
        targets = []
        for name, mapping, guard in self.profile_rows():
            if name == 'Root':
                targets.append(('profile_root', mapping+0x48, guard))
        for obj, name in self.u.objects('InputMappingContext'):
            if name == 'IMC_DefaultKBM':
                rows, guard = self.mapping_rows(obj, self.u.offset(obj, 'Mappings'))
                targets.extend(('source_root', entry+40, self.row_guard(entry, guard))
                               for entry, action, key in rows if action == 'IA_RootPlayer')
        if self.location() == 'gameplay':
            pc = self.u.u64(self.local+48)
            pi = self.u.u64(pc+self.u.offset(pc, 'PlayerInput'))
            rows, guard = self.mapping_rows(pi, self.u.offset(pi, 'EnhancedActionMappings'))
            targets.extend(('runtime_root', entry+40, self.row_guard(entry, guard))
                           for entry, action, key in rows if action == 'IA_RootPlayer')
        restored = skipped = 0
        for role, address, guard in targets:
            if role not in backup.data['managed']:
                continue
            if not guard():
                skipped += 1
                continue
            current = self.u.name_at(address)
            wanted = backup.wanted(role, current)
            if wanted is not None:
                value = self.u.key_name(wanted)
                if not guard() or self.u.name_at(address) != current:
                    skipped += 1
                    continue
                self.p.write(address, value+bytes(16))
                if self.u.read(address, 8) != value:
                    raise RuntimeError('Could not verify the restored '+role+' binding.')
                restored += 1
            elif current != backup.data['managed'][role]['original']:
                skipped += 1  # Preserve a later player remap.
            backup.restored(role)
        return restored, skipped

    def can_resume(self):
        if self.location() != 'gameplay':
            return False
        if not self.settings.wasd:
            return True
        pc = self.u.u64(self.local+48)
        pi = self.u.u64(pc+self.u.offset(pc, 'PlayerInput'))
        rows, guard = self.mapping_rows(pi, self.u.offset(pi, 'EnhancedActionMappings'))
        signatures = [self.modifier_signature(entry) for entry, action, key in rows
                      if action == 'IA_Gamepad_Move' and not key.startswith('Gamepad_')]
        return (len(signatures) == 4 and () in signatures and ('InputModifierNegate',) in signatures
                and ('InputModifierSwizzleAxis',) in signatures
                and any(s in signatures for s in [('InputModifierSwizzleAxis', 'InputModifierNegate'),
                                                 ('InputModifierNegate', 'InputModifierSwizzleAxis')]))

    def leave_controls(self):
        self.release_inputs()
        if self.move and self.move_guard():
            self.journal.set(self.move+0x1280, struct.pack('<d', self.settings.maximum), self.move_guard)
        # An unattended feature flag must not break the next title-screen Play handshake.
        self.flag(False)
        self.journal.save()
        self.move = 0

    def sync_slam(self):
        from slam import select_binding
        if not self.settings.jump_slam:
            self.release_inputs()
            self.slam_key, self.slam_problem = None, ''
            return
        profile_rows = self.profile_rows()
        rows = [(name, self.u.name_at(mapping+0x48)) for name, mapping, guard in profile_rows]
        movement = (self.settings.forward, self.settings.left, self.settings.back, self.settings.right) if self.settings.wasd else ()
        key, problem = select_binding(rows, self.settings.slam_binding, movement)
        if key != self.slam_key:
            self.release_inputs()
        self.slam_key = key
        self.slam_binding_guard = lambda: False
        if key:
            for name, mapping, guard in profile_rows:
                if name == 'HeavyJumpAttack' and self.u.name_at(mapping+0x48) == key:
                    expected = self.u.read(mapping+0x48, 8)
                    self.slam_binding_guard = lambda m=mapping, g=guard, v=expected: g() and self.u.read(m+0x48, 8) == v
                    break
        self.slam_problem = self.slam.error or problem
        self.slam_mode_offset = self.u.offset(self.move, 'MovementMode')

    def tick_slam(self):
        if not self.p.writable or not self.settings.jump_slam or not self.slam_key or self.slam_problem:
            self.release_inputs()
            return
        try:
            if not self.slam_binding_guard():
                self.release_inputs()
                return
            mode = self.u.read(self.move+self.slam_mode_offset, 1)[0]
            if mode > 6:
                raise StaleState('Jump Slam: unexpected movement mode.')
            io = self.slam.io
            eligible = io.focused() and not any(io.down(vk) for vk in (0x11, 0x12, 0x5b, 0x5c))
            if eligible:
                # Follow the current world each tick; never retain a previous map's address.
                world_settings = self.local
                for prop in ('ViewportClient', 'World', 'PersistentLevel', 'WorldSettings'):
                    world_settings = self.u.u64(world_settings+self.u.offset(world_settings, prop))
                    if not world_settings:
                        raise StaleState('Jump Slam is waiting for the current world.')
                eligible = not self.u.u64(world_settings+self.u.offset(world_settings, 'PauserPlayerState'))
            self.slam.update(time.monotonic(), eligible, mode in (1, 2), mode == 3,
                             io.down(1), self.slam_key, self.settings.slam_delay)
        except Exception as exc:
            self.slam.error = self.slam_problem = str(exc)
            self.release_inputs()

    def location(self):
        if not self.local_guard():
            self.u.refresh()
            self.local = self.u.one('DungeonsLocalPlayer')
            self.local_guard = self.u.guard(self.local)
        pc = self.u.u64(self.local+48)
        if not pc:
            return 'loading'
        if self.u.is_a(pc, 'BP_MenuPlayerController_C'):
            return 'title'
        if self.u.is_a(pc, 'BP_GameplayPlayerController_C'):
            return 'gameplay' if self.u.u64(pc+0x2e8) else 'loading'
        return 'unknown_screen'

    def configure(self, settings):
        settings.validate()
        self.release_inputs()
        self.slam.error = self.slam_problem = ''
        self.journal.restore_where()
        self.restore_saved_bindings()
        self.settings = settings.effective()
        self.move = self.pc = self.pawn = 0
        self.move_guard = lambda: False
        self.speed = 0.0

    def flag(self, enabled):
        if not enabled and (self.settings.wasd or not self.move):
            self.release_inputs()
        address = self.p.base + self.FLAG
        if self.p.read(address, 1) not in (b'\0', b'\1'):
            raise StaleState('Unexpected feature flag value.')
        self.journal.set(address, bytes([bool(enabled)]), self.p.alive, original=b'\0')

    def prepare_context(self):
        """Unmark the native test context without enabling the network feature at title."""
        u = self.u
        gi = u.one('GameInstanceSWTypeSystem')
        a = u.u64(gi + 0x30)
        cache = u.u64(a + 0x70)
        root, count = u.array(cache + 0x300, 10000)
        player_tag = u.read(u.u64(u.base + 0xBB3E9C0), 8)
        context_tag = u.read(u.u64(u.base + 0xBB3E108), 8)
        for i in range(count):
            outer = root + i*96
            if u.read(outer, 8) != player_tag:
                continue
            inner, n = u.array(outer + 8, 10000)
            for j in range(n):
                entry = inner + j*40
                if u.read(entry, 8) != context_tag:
                    continue
                st = u.u64(entry + 8)
                if u.name(st) != 'MappingContexts':
                    raise StaleState('Unexpected mapping context structure.')
                row = u.u64(entry + 16)
                records, length = u.array(row, 100)
                for k in range(length):
                    record = records + k*56
                    if u.name_at(record + 16) != 'IMC_AITestRunner':
                        continue
                    checks = [(gi+0x30, struct.pack('<Q', a)), (a+0x70, struct.pack('<Q', cache)),
                              (cache+0x300, struct.pack('<Q', root)),
                              (outer+8, struct.pack('<Q', inner)), (entry+16, struct.pack('<Q', row)),
                              (row, struct.pack('<Q', records)), (record+16, u.read(record+16, 8))]
                    guard = u.guard(gi, checks)
                    if u.read(record+46, 1) not in (b'\0', b'\1'):
                        raise StaleState('Unexpected test-context marker.')
                    self.journal.set(record+46, b'\0', guard)
                    return
        raise StaleState('Native movement context has not been loaded yet.')

    def mapping_rows(self, obj, offset):
        u = self.u
        pointer, count = u.array(obj + offset, 400)
        rows = []
        for i in range(count):
            entry = pointer + i*80
            action = u.u64(entry+32)
            if not action:
                continue
            rows.append((entry, u.name(action), u.name_at(entry+40)))
        guard = u.guard(obj, [(obj+offset, struct.pack('<Q', pointer))])
        return rows, guard

    def modifier_signature(self, entry):
        u = self.u
        pointer, count = u.array(entry + 16, 16)
        return tuple(u.class_name(u.u64(pointer+i*8)) for i in range(count))

    def row_guard(self, entry, container_guard):
        expected = self.u.read(entry, 40)
        def valid():
            try:
                return container_guard() and self.u.read(entry, 40) == expected
            except RuntimeError:
                return False
        valid.record = dict(container_guard.record)
        valid.record['checks'] = container_guard.record['checks'] + [[entry, expected.hex()]]
        return valid

    def movement_keys(self, obj, offset):
        rows, guard = self.mapping_rows(obj, offset)
        # Native axis modifiers uniquely distinguish directions independently of key names.
        roles = {
            ('InputModifierSwizzleAxis',): self.settings.forward,
            ('InputModifierNegate',): self.settings.left,
            ('InputModifierSwizzleAxis', 'InputModifierNegate'): self.settings.back,
            ('InputModifierNegate', 'InputModifierSwizzleAxis'): self.settings.back,
            (): self.settings.right,
        }
        found = set()
        for entry, action, key in rows:
            if action != 'IA_Gamepad_Move' or key.startswith('Gamepad_'):
                continue
            signature = self.modifier_signature(entry)
            if signature not in roles:
                raise StaleState(f'Unknown native movement modifier: {signature}.')
            wanted = roles[signature]
            if wanted in found:
                raise StaleState('Ambiguous movement-axis mappings.')
            found.add(wanted)
            self.journal.set(entry+40, self.u.key_name(wanted), self.row_guard(entry, guard), key=True)
        return found

    def root_binding(self, obj, offset):
        rows, guard = self.mapping_rows(obj, offset)
        primary = [(entry, key) for entry, action, key in rows if action == 'IA_KBM_PrimaryAction']
        roots = [entry for entry, action, key in rows if action == 'IA_RootPlayer']
        if len(primary) != 1 or len(roots) != 1:
            raise StaleState('Primary/stand-still bindings are ambiguous.')
        primary_entry, primary_key = primary[0]
        self.record_binding('runtime_root', self.u.name_at(roots[0]+40), primary_key)
        self.journal.set(roots[0]+40, self.u.read(primary_entry+40, 8), self.row_guard(roots[0], guard), key=True)
        return primary_key

    def profile(self):
        found = []
        for obj, name in self.u.objects('SWEnhancedPlayerMappableKeyProfile'):
            if self.u.fstring(obj+0x30) == 'SW.Input.Profile.InputType.Keyboard':
                found.append(obj)
        if len(found) != 1:
            raise StaleState('Keyboard profile is not ready or is ambiguous.')
        return found[0]

    def profile_rows(self):
        u = self.u
        profile = self.profile()
        pointer, count = u.array(profile+0x58, 400)
        output = []
        for i in range(count):
            row = pointer + i*96
            name = u.name_at(row)
            mappings, length = u.array(row+8, 16)
            for j in range(length):
                mapping = mappings + j*176
                # Sparse arrays may include deleted slots. MappingName must match the row.
                if u.read(mapping, 8) != u.read(row, 8):
                    continue
                guard = u.guard(profile, [(profile+0x58, struct.pack('<Q', pointer)),
                                          (row+8, struct.pack('<Q', mappings)),
                                          (mapping, u.read(mapping, 8))])
                output.append((name, mapping, guard))
        return output

    def patch_profile(self, attack_key):
        self.conflicts = []
        movement_keys = {self.settings.forward, self.settings.left, self.settings.back, self.settings.right}
        roots = 0
        for name, mapping, guard in self.profile_rows():
            key = self.u.name_at(mapping+0x48)
            if name == 'Root' and self.settings.attack_in_place:
                roots += 1
                self.record_binding('profile_root', key, attack_key)
                self.journal.set(mapping+0x48, self.u.key_name(attack_key), guard, key=True)
            elif self.settings.wasd and key in movement_keys:
                self.conflicts.append(f'{key}: {name}')
        if self.settings.attack_in_place and roots != 1:
            raise StaleState('Stand-still profile row is not ready or is ambiguous.')

    def patch_tree(self, pc):
        if not self.settings.block_ground_move and not self.settings.block_interaction_approach:
            return  # Original click behavior needs no state-tree mutation or discovery.
        u = self.u
        component = u.u64(pc + u.offset(pc, 'StateTreeComponent'))
        tree = u.u64(component + u.offset(component, 'StateTreeRef'))
        tree_name = u.name(tree)
        if tree_name != 'ST_PlayerInput':
            raise StaleState(f'Player input tree not ready: {tree_name}.')
        offset = u.offset(tree, 'States')
        pointer, count = u.array(tree+offset, 400)
        targets = set()
        if self.settings.block_ground_move:
            targets.update(('MoveTowardsCursor', 'PathTowardsCursor'))
        if self.settings.block_interaction_approach:
            targets.add('MoveToInteractable')
        found = set()
        for i in range(count):
            state = pointer+i*96
            name = u.name_at(state+16)
            if name not in targets:
                continue
            found.add(name)
            guard = u.guard(tree, [(tree+offset, struct.pack('<Q', pointer)),
                                   (state+16, u.read(state+16, 8))])
            current = u.read(state+93, 1)[0]
            self.journal.set(state+93, bytes([current & ~0x20]), guard)
        if found != targets:
            raise StaleState('Expected click-movement states are missing.')

    def sync(self):
        u = self.u
        self.capture_controls()
        self.phase = 'loading'
        self.checks = []
        if not self.local_guard():
            u.refresh()
            self.local = u.one('DungeonsLocalPlayer')
            self.local_guard = u.guard(self.local)
        pc = u.u64(self.local+48)
        location = self.location()
        gameplay = location == 'gameplay'
        pawn = u.u64(pc+0x2e8) if gameplay else 0
        if not gameplay or not pawn:
            self.flag(False)
            self.move = 0
            self.move_guard = lambda: False
        if self.settings.wasd:
            self.prepare_context()
        if not gameplay or not pawn:
            self.status = 'Ready at title — press Play. WASD feature flag is off here.'
            self.phase = location
            return
        # Context objects can be loaded/replaced during map transitions.
        if time.monotonic() - self.last_refresh > 5 and not u.objects('InputMappingContext'):
            u.refresh()
            self.last_refresh = time.monotonic()
        if self.settings.wasd:
            native = u.one('InputMappingContext', 'IMC_AITestRunner')
            self.movement_keys(native, u.offset(native, 'Mappings'))
        if self.settings.attack_in_place:
            source = u.one('InputMappingContext', 'IMC_DefaultKBM')
            # The player's PrimaryAction remap takes precedence over the default context.
            attack_key = next((u.name_at(m+0x48) for nm, m, g in self.profile_rows() if nm == 'PrimaryAction'), 'LeftMouseButton')
            rows, guard = self.mapping_rows(source, u.offset(source, 'Mappings'))
            for entry, action, key in rows:
                if action == 'IA_RootPlayer':
                    self.record_binding('source_root', key, attack_key)
                    self.journal.set(entry+40, u.key_name(attack_key), self.row_guard(entry, guard), key=True)
            self.patch_profile(attack_key)
        else:
            self.patch_profile('LeftMouseButton')
        if not gameplay or not pawn:
            self.status = 'Ready at title — press Play. WASD feature flag is off here.'
            return
        pi = u.u64(pc + u.offset(pc, 'PlayerInput'))
        mappings_offset = u.offset(pi, 'EnhancedActionMappings')
        movement = self.movement_keys(pi, mappings_offset) if self.settings.wasd else set()
        if self.settings.attack_in_place:
            self.root_binding(pi, mappings_offset)
        self.patch_tree(pc)
        self.flag(self.settings.wasd and bool(movement))
        if pc != self.pc or pawn != self.pawn or not self.move_guard():
            move = u.u64(pawn + u.offset(pawn, 'CharacterMovement'))
            if u.class_name(move) != 'PlayerCharacterMovementComponent' or u.offset(move, 'RotationRate') != 0x2d0:
                raise StaleState('Unknown character movement layout.')
            pitch, yaw, roll = struct.unpack('<ddd', u.read(move+0x1278, 24))
            if pitch != 0 or roll != 0 or not math.isfinite(yaw) or not 0 <= yaw <= 1800:
                raise StaleState('Unexpected rotation-rate source.')
            self.pc, self.pawn, self.move = pc, pawn, move
            checks = [(self.local+48, struct.pack('<Q', pc)), (pc+0x2e8, struct.pack('<Q', pawn)),
                      (pawn+u.offset(pawn, 'CharacterMovement'), struct.pack('<Q', move))]
            self.move_guard = u.guard(move, checks)
            self.speed, self.sign = 0.0, 0
        self.status = f'Active — {"smooth" if self.settings.smooth else "constant"} turning, {self.settings.maximum:g}°/s maximum'
        self.phase = 'active'
        self.checks = [
            f'Keyboard movement: {len(movement)}/4 mappings ready' if self.settings.wasd else 'Keyboard movement: off in your profile',
            'Click controls: selected behavior applied',
            f'Turning: {"smooth" if self.settings.smooth else "constant"}, {self.settings.maximum:g}°/s maximum',
        ]
        if self.settings.native_interactions:
            self.checks.append('Native interaction mode: original click behavior restored; revive workaround is unverified.')
        if self.settings.wasd and len(movement) < 4:
            self.status = 'Movement mappings incomplete — return to title and load your character once.'
            self.phase = 'needs_reload'
        if self.conflicts:
            self.status += '\nRebind conflicting game controls: ' + ', '.join(self.conflicts)
            self.phase = 'conflict'
        self.sync_slam()
        if self.settings.jump_slam:
            self.checks.append('Jump Slam: ' + (self.slam_problem or f'ready via {self.slam_key}; {self.slam.count} presses sent'))
            if self.slam_problem and self.phase == 'active':
                self.phase = 'assist_warning'
        else:
            self.checks.append('Jump Slam assist: off')
        self.journal.prune()

    def tick(self, dt):
        if not self.move or not self.move_guard():
            self.release_inputs()
            if self.move:
                self.flag(False)
                self.move = 0
            return
        self.tick_slam()
        u = self.u
        target = struct.unpack('<d', u.read(self.pc+0x328, 8))[0]
        x, y, z, w = struct.unpack('<dddd', u.read(self.move+0x340, 32))
        if not all(math.isfinite(v) for v in (target, x, y, z, w)) or not 0.9 < x*x+y*y+z*z+w*w < 1.1:
            raise StaleState('Invalid rotation sample.')
        current = math.degrees(math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z)))
        error = angle_error(target, current)
        sign = 1 if error > 0.2 else -1 if error < -0.2 else 0
        if sign and self.sign and sign != self.sign:
            self.speed = 0.0
        if sign:
            self.sign = sign
        self.speed = step(self.speed, error, dt, self.settings)
        self.journal.set(self.move+0x1280, struct.pack('<d', max(1.0, self.speed)), self.move_guard)

    def stop(self):
        self.release_inputs()
        self.move = 0
        restored, skipped = self.journal.restore_where()
        more_restored, more_skipped = self.restore_saved_bindings()
        restored += more_restored
        skipped += more_skipped
        # Keep Play compatible even when attaching to an earlier experimental session.
        if self.p.alive() and self.p.writable:
            self.p.write(self.p.base+self.FLAG, b'\0')
        return restored, skipped

    def diagnostics(self):
        return {'pid': self.p.pid, 'build_sha256': self.p.hash,
                'status': self.status, 'conflicts': list(self.conflicts),
                'phase': self.phase, 'checks': list(self.checks),
                'jump_slam': {'binding': self.slam_key, 'problem': self.slam_problem,
                              'presses_sent': self.slam.count, 'held': self.slam.held},
                'owned_changes': len(self.journal.entries), 'local_players': len(self.u.objects('DungeonsLocalPlayer'))}

    def state_snapshot(self):
        """Best effort, no raw pointers or player identities; works while loading."""
        report = {'phase': self.phase, 'object_counts': {k: len(v) for k, v in self.u.index.items()}}
        try:
            pc = self.u.u64(self.local+48)
            report['controller_class'] = self.u.class_name(pc) if pc else 'None'
            report['location'] = self.location()
            if report['location'] == 'gameplay':
                report['movement_mappings_ready'] = self.can_resume()
                component = self.u.u64(pc+self.u.offset(pc, 'StateTreeComponent'))
                tree = self.u.u64(component+self.u.offset(component, 'StateTreeRef'))
                report['input_tree'] = self.u.name(tree)
                rows = self.profile_rows()
                report['relevant_bindings'] = [{'action': n, 'key': self.u.name_at(m+0x48)} for n, m, g in rows
                                               if n in ('Root', 'PrimaryAction', 'Interact', 'Revive', 'HeavyJumpAttack')]
        except (RuntimeError, OSError) as exc:
            report['snapshot_error'] = str(exc)
        return report
