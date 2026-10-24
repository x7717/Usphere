#!/usr/bin/env python3
"""Validate the ported overlay_26.3: no legacy format markers, all references resolve."""
import json, os, re, sys
ROOT = "/home/z/my-project/mc"
OV = f"{ROOT}/datapacks/lithosphere-26.3/overlay_26.3"
VAN = f"{ROOT}/datagen/26.3/generated/data/minecraft"
SRC = f"{ROOT}/datapacks/litho-26.2"

errors, warnings = [], []

# 1) legacy markers must not appear in overlay_26.3
LEGACY = ["flat_cache", "cache_2d", "cache_once", "cache_all_in_cell", "shifted_noise",
          "y_clamped_gradient", "firstOctave", '"amplitudes"', '"argument1"', '"argument2"',
          '"Name"', "from_y", "to_y", "initial_density_without_jaggedness", "preliminary_surface_level",
          "ore_veins_enabled", "aquifers_enabled", "size_horizontal", "size_vertical", "surface_rule",
          "configured_feature", "configured_carver"]
def walk_files(root):
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.endswith(".json"):
                yield os.path.join(dp, f)

n_checked = 0
for p in walk_files(OV):
    txt = open(p).read()
    n_checked += 1
    for marker in LEGACY:
        if marker in txt:
            errors.append(f"{os.path.relpath(p, OV)}: legacy marker '{marker}'")

# 2) collect available registries
def ids_from(datagen_dir):
    out = set()
    d = os.path.join(VAN, datagen_dir)
    for dp, _, fn in os.walk(d):
        for f in fn:
            if f.endswith(".json"):
                out.add(os.path.relpath(os.path.join(dp, f), d)[:-5])
    return out

def ids_from_pack(rel_dir):
    out = set()
    for layer in (f"{SRC}/data", f"{OV}/data"):
        d = os.path.join(layer, rel_dir)
        for dp, _, fn in os.walk(d):
            for f in fn:
                if f.endswith(".json"):
                    out.add(os.path.relpath(os.path.join(dp, f), d)[:-5])
    return out

van_noise = ids_from("worldgen/noise")
van_df = ids_from("worldgen/density_function")
pack_noise = ids_from_pack("worldgen/noise")
pack_df = ids_from_pack("worldgen/density_function")
van_biomes = ids_from("worldgen/biome")

REF_MAP = {"noise": van_noise | pack_noise, "df": van_df | pack_df}

REF_PAT = re.compile(r'"minecraft:([a-z0-9_/.-]+)"')
def check_refs(obj, where, kind):
    if isinstance(obj, dict):
        for k, v in obj.items():
            check_refs(v, where, kind)
    elif isinstance(obj, list):
        for v in obj:
            check_refs(v, where, kind)
    elif isinstance(obj, str) and obj.startswith("minecraft:"):
        rid = obj[10:]
        if kind == "noise" and rid not in REF_MAP["noise"]:
            errors.append(f"{where}: unknown noise ref {obj}")
        if kind == "df" and rid not in REF_MAP["df"] and rid not in REF_MAP["noise"]:
            # density function refs may also point to noises via auto-wrap? keep strict for df
            errors.append(f"{where}: unknown density function ref {obj}")

def walk_noise_refs(obj, where):
    """find noise fields inside noise{} df nodes and noise_threshold conditions"""
    if isinstance(obj, dict):
        t = obj.get("type", "")
        if t.endswith(":noise") and isinstance(obj.get("noise"), str):
            rid = obj["noise"].replace("minecraft:", "")
            if not obj["noise"].startswith("lithosphere:") and rid not in REF_MAP["noise"]:
                errors.append(f"{where}: unknown noise {obj['noise']}")
        if t.endswith(":noise_threshold") and isinstance(obj.get("noise"), str):
            rid = obj["noise"].replace("minecraft:", "")
            if not obj["noise"].startswith("lithosphere:") and rid not in REF_MAP["noise"]:
                errors.append(f"{where}: unknown noise {obj['noise']}")
        for k, v in obj.items():
            walk_noise_refs(v, where)
    elif isinstance(obj, list):
        for v in obj:
            walk_noise_refs(v, where)

def walk_df_refs(obj, where):
    """string values used as density function inputs"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("input", "left", "right", "first", "second", "argument") and isinstance(v, str):
                if v.startswith("minecraft:"):
                    rid = v[10:]
                    if rid not in REF_MAP["df"] and rid not in REF_MAP["noise"]:
                        errors.append(f"{where}: unknown df ref {v}")
            walk_df_refs(v, where)
    elif isinstance(obj, list):
        for v in obj:
            walk_df_refs(v, where)

for p in walk_files(OV):
    rel = os.path.relpath(p, OV)
    try:
        j = json.load(open(p))
    except Exception as e:
        errors.append(f"{rel}: invalid JSON {e}")
        continue
    if "/worldgen/noise/" in rel:
        # check parity fields present
        if "base_octave" not in j:
            errors.append(f"{rel}: missing base_octave")
    if "/worldgen/density_function/" in rel or "/noise_settings/" in rel:
        walk_noise_refs(j, rel)
        walk_df_refs(j, rel)
    if "/material_rule/" in rel:
        walk_noise_refs(j, rel)
        # biome_is refs
        for m in re.finditer(r'"biome_is":\s*(\[[^\]]*\]|"minecraft:[a-z_]+")', json.dumps(j)):
            frag = m.group(1)
            for bid in re.findall(r'minecraft:([a-z_]+)', frag):
                if bid not in van_biomes:
                    errors.append(f"{rel}: unknown biome {bid}")

# 3) noise_settings schema sanity
for f in ("overworld", "large_biomes"):
    ns = json.load(open(f"{OV}/data/minecraft/worldgen/noise_settings/{f}.json"))
    expect = {"aquifers", "default_block", "default_fluid", "disable_mob_generation",
              "legacy_random_source", "material_rule", "noise", "noise_router", "sea_level", "spawn_target"}
    got = set(ns.keys())
    if got != expect:
        errors.append(f"noise_settings/{f}: key mismatch: extra={got-expect} missing={expect-got}")
    nr = ns["noise_router"]
    expect_nr = {"temperature", "vegetation", "continents", "erosion", "ridges", "depth", "final_density", "chunk_surface_level"}
    if set(nr.keys()) != expect_nr:
        errors.append(f"noise_settings/{f}: router keys mismatch: {set(nr.keys()) ^ expect_nr}")

print(f"checked {n_checked} JSON files in overlay_26.3")
if errors:
    print(f"\nERRORS ({len(errors)}):")
    for e in errors[:40]: print("  -", e)
    sys.exit(1)
print("NO ERRORS — overlay_26.3 is clean")
