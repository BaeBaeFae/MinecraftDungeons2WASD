"""Portable settings and turn dynamics. No game or Windows dependencies."""
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path

VERSION = '0.1.3-beta'
KEYS = tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ('Up', 'Down', 'Left', 'Right')


@dataclass(frozen=True)
class Settings:
    wasd: bool = True
    attack_in_place: bool = True
    block_ground_move: bool = True
    block_interaction_approach: bool = True
    native_interactions: bool = False
    jump_slam: bool = False
    slam_binding: str = 'Auto'
    slam_delay: float = 80.0
    smooth: bool = True
    maximum: float = 900.0
    acceleration: float = 6000.0
    deceleration: float = 7000.0
    ease_out: float = 18.0
    forward: str = 'W'
    left: str = 'A'
    back: str = 'S'
    right: str = 'D'

    def validate(self):
        for name in ('wasd', 'attack_in_place', 'block_ground_move',
                     'block_interaction_approach', 'smooth', 'jump_slam', 'native_interactions'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'{name} must be true or false.')
        for name, low, high in [('maximum', 90, 1800), ('acceleration', 500, 20000),
                                ('deceleration', 500, 20000), ('ease_out', 4, 40), ('slam_delay', 0, 500)]:
            value = getattr(self, name)
            if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{name} must be between {low} and {high}.')
        from slam import BINDINGS
        if self.slam_binding not in BINDINGS:
            raise ValueError('Choose a supported Jump Slam binding.')
        movement = [self.forward, self.left, self.back, self.right]
        if len(set(movement)) != 4 or any(key not in KEYS for key in movement):
            raise ValueError('Choose four different movement keys.')
        return self

    def effective(self):
        if not self.native_interactions:
            return self
        from dataclasses import replace
        return replace(self, attack_in_place=False, block_ground_move=False,
                       block_interaction_approach=False, jump_slam=False)

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('schema') != 1 or not isinstance(data.get('settings'), dict):
            raise ValueError('Unrecognized profile format.')
        return cls(**data['settings']).validate()

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps({'schema': 1, 'settings': asdict(self.validate())}, indent=2), encoding='utf-8')
        temporary.replace(path)


PRESETS = {
    'Responsive': Settings(),
    'Gentle': Settings(maximum=470, acceleration=2400, deceleration=2800, ease_out=12),
    'Fast': Settings(maximum=1200, acceleration=9500, deceleration=11000, ease_out=23),
}


def step(speed, error, dt, settings):
    if not all(math.isfinite(v) for v in (speed, error, dt)) or dt < 0:
        raise ValueError('Invalid turn sample.')
    if not settings.smooth:
        return float(settings.maximum)
    goal = min(settings.maximum, abs(error) * settings.ease_out,
               math.sqrt(2 * settings.deceleration * abs(error)))
    change = (settings.acceleration if goal > speed else settings.deceleration) * min(dt, 0.05)
    return max(0.0, min(settings.maximum, speed + max(-change, min(change, goal - speed))))


def angle_error(target, current):
    return (target - current + 180) % 360 - 180
