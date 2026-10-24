#!/usr/bin/env python3
"""Validate the reverse-engineered base_amplitude parity formula against all vanilla 26.2->26.3 noises."""
import json, os, math
BASE = "/home/z/my-project/mc/datagen"
def load(p): return json.load(open(p))
def walk(root, sub):
    out = {}
    d = os.path.join(root, sub)
    for dp, dn, fn in os.walk(d):
        for f in fn:
            if f.endswith(".json"):
                out[os.path.relpath(os.path.join(dp, f), d)] = json.load(open(os.path.join(dp, f)))
    return out

PERLIN_DEV = 0.2702247831245211

def get_mod(mods, i):
    return 1.0 if not mods else mods[i]

def build_octaves(first_octave, amplitude_scale, count, legacy, modifiers):
    scale = 2.0 ** first_octave
    amp = amplitude_scale
    if legacy:
        amp *= (2.0 ** (count - 1)) / (2.0 ** count - 1)
    octaves = []
    for i in range(count):
        mod = get_mod(modifiers, i)
        if mod != 0:
            octaves.append((first_octave + i, scale, amp * mod))
        scale *= 2.0
        amp *= 0.5
    return octaves

def estimate_deviation(octaves):
    return math.sqrt(sum((PERLIN_DEV * abs(a)) ** 2 for _, _, a in octaves))

def compute_normalization_factor(sum_amp, octaves):
    est = estimate_deviation(octaves)
    if est == 0:
        return 0.0
    return (sum_amp / 3.0) / (est * math.sqrt(2.0))

def parity_expected_deviation(spread):
    return 0.1 * (1.0 + 1.0 / (spread + 1))

def compute_parity_base_amplitude(first_octave, modifiers, use_abs_in_sum=False):
    count = len(modifiers)
    octaves = build_octaves(first_octave, 1.0, count, True, modifiers)
    if use_abs_in_sum:
        sum_amp = sum(abs(a) for _, _, a in octaves)
    else:
        sum_amp = sum(a for _, _, a in octaves)
    nf = compute_normalization_factor(sum_amp, octaves)
    if nf == 0:
        return 1.0
    nz = [i for i in range(count) if get_mod(modifiers, i) != 0]
    parity_norm = (0.5 * (1.0 / 3.0)) / parity_expected_deviation(max(nz) - min(nz))
    return parity_norm / nf

n2 = walk(f"{BASE}/26.2/generated/data/minecraft", "worldgen/noise")
n3 = walk(f"{BASE}/26.3/generated/data/minecraft", "worldgen/noise")
ok = bad = 0
for name, j2 in sorted(n2.items()):
    j3 = n3.get(name)
    if not j3 or "base_amplitude" not in j3:
        continue
    amps = j2.get("amplitudes")
    fo = j2.get("firstOctave")
    if amps is None:
        continue
    pred = compute_parity_base_amplitude(fo, amps)
    actual = j3["base_amplitude"]
    if abs(pred - actual) < 1e-9:
        ok += 1
    else:
        bad += 1
        print(f"MISMATCH {name}: pred={pred:.12f} actual={actual:.12f} (diff {pred-actual:.3e})")
print(f"\nMATCHED {ok}, MISMATCHED {bad} of {ok+bad}")
