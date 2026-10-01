"""Exact executable fingerprints and their independently inspected global locations."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Build:
    name_pool: int
    objects: int
    wasd_flag: int
    feature_name: int
    input_gate: int
    input_bytes: bytes


BUILDS = {
    '7c83afbf0ad34a40b853cdb25a22fffb605d08e2a1e2d431974d7c7c1ee0ba54': Build(
        0xBDC5040, 0xBEA8C00, 0xC068610, 0x9D6CD80, 0x63B936B,
        bytes.fromhex('80 3d 9e f2 ca 05 00 74 5a')),
    '231147bd0c655a4ae73f90873675d42917f2bfb3a9ee164fc64f217d6d6bd4ef': Build(
        0xBE51EC0, 0xBF35A80, 0xC0F5568, 0x9DD9360, 0x63BBE2B,
        bytes.fromhex('80 3d 36 97 d3 05 00 74 5a')),
}


def select_build(digest):
    if digest not in BUILDS:
        raise RuntimeError(f'Unsupported game build ({digest[:12]}). No changes made.')
    return BUILDS[digest]
