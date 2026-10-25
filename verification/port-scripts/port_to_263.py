#!/usr/bin/env python3
"""
Port Lithosphere datapack 1.8.2 (26.2, data pack format 107.1) -> Minecraft 26.3 (format 121.0).
Creates overlay_26.3 with fully converted files. Strategy:
  - copy original pack
  - add overlay_26.3 (min_format 121.0, max_format 900) LAST in overlay list (later overlays win)
  - overlay_26.3 shadows every file whose lower-layer content is invalid in 121.0
"""
import json, os, shutil, math, sys, zipfile

ROOT = "/home/z/my-project/mc"
SRC = f"{ROOT}/datapacks/litho-26.2"
VAN = f"{ROOT}/datagen/26.3/generated/data/minecraft"
WORK = f"{ROOT}/datapacks/lithosphere-26.3"
OUT_ZIP = f"{ROOT}/downloads/lithosphere-1.8.2-26.3.zip"

PERLIN_DEV = 0.2702247831245211

# ---------------- noise parity conversion (validated 63/63 vs vanilla) ----------------
def get_mod(mods, i):
    return 1.0 if not mods else mods[i]

def parity_base_amplitude(first_octave, modifiers):
    count = len(modifiers)
    scale = 2.0 ** first_octave
    amp = (2.0 ** (count - 1)) / (2.0 ** count - 1)     # legacy fbm factor
    amps = []
    for i in range(count):
        m = get_mod(modifiers, i)
        if m != 0:
            amps.append(amp * m)
        scale *= 2.0
        amp *= 0.5
    est = math.sqrt(sum((PERLIN_DEV * abs(a)) ** 2 for a in amps))
    if est == 0:
        return 1.0
    nf = (sum(amps) / 3.0) / (est * math.sqrt(2.0))
    if nf == 0:
        return 1.0
    nz = [i for i in range(count) if get_mod(modifiers, i) != 0]
    spread = max(nz) - min(nz)
    parity_norm = (0.5 * (1.0 / 3.0)) / (0.1 * (1.0 + 1.0 / (spread + 1)))
    return parity_norm / nf

def convert_noise(j):
    out = {}
    if "firstOctave" in j:
        out["base_octave"] = j["firstOctave"]
    elif "base_octave" in j:
        out["base_octave"] = j["base_octave"]
    else:
        raise ValueError("noise without octave: " + json.dumps(j))
    amps = j.get("amplitudes", j.get("amplitude_modifiers"))
    if amps is not None:
        out["amplitude_modifiers"] = amps
        out["octave_count"] = len(amps)
        out["base_amplitude"] = parity_base_amplitude(out["base_octave"], amps)
    else:
        # single-octave vanilla style: base_amplitude constant for unit modifier
        out["base_amplitude"] = parity_base_amplitude(out["base_octave"], [1.0])
    return out

# ---------------- density function transforms ----------------
CACHE_TYPES = {"flat_cache", "cache_2d", "cache_once", "cache_all_in_cell"}
ARG_TO_INPUT = {"abs", "blend_density", "cube", "half_negative", "quarter_negative", "square", "squeeze", "invert", "interpolated"}
BINARY = {"add", "mul", "min", "max", "sub"}
INTERP_CELL = {"cell_size_xz": 4, "cell_size_y": 8}

def norm_type(t):
    return t.split(":", 1)[1] if isinstance(t, str) and ":" in t else t

def df_transform(o):
    if isinstance(o, list):
        return [df_transform(v) for v in o]
    if not isinstance(o, dict):
        return o
    t = norm_type(o.get("type"))
    if t is None:
        return {k: df_transform(v) for k, v in o.items()}
    out = {}
    if t in CACHE_TYPES:
        out["type"] = "minecraft:cache"
        out["input"] = df_transform(o["argument"])
        return out
    if t == "shifted_noise":
        out["type"] = "minecraft:noise"
        for k in ("noise", "xz_scale", "y_scale"):
            if k in o: out[k] = o[k]
        for k in ("shift_x", "shift_z"):
            if k in o: out[k] = df_transform(o[k])
        return out
    if t == "y_clamped_gradient":
        out["type"] = "minecraft:gradient"
        out["axis"] = "y"
        out["from_coordinate"] = o["from_y"]
        out["to_coordinate"] = o["to_y"]
        out["from_value"] = o["from_value"]
        out["to_value"] = o["to_value"]
        return out
    if t == "interpolated":
        out["type"] = "minecraft:interpolated"
        out["input"] = df_transform(o["argument"])
        out.update(INTERP_CELL)
        return out
    if t == "invert":
        out["type"] = "minecraft:negate"
        out["input"] = df_transform(o["argument"])
        return out
    if t in ARG_TO_INPUT:  # abs, blend_density, cube, half_negative, quarter_negative, square, squeeze
        out["type"] = "minecraft:" + t
        out["input"] = df_transform(o["argument"])
        return out
    if t in BINARY:
        out["type"] = "minecraft:" + t
        if t == "lerp":
            out["first"] = df_transform(o["argument1"])
            out["second"] = df_transform(o["argument2"])
            if "alpha" in o: out["alpha"] = df_transform(o["alpha"])
            elif "argument" in o: out["alpha"] = df_transform(o["argument"])
        else:
            out["left"] = df_transform(o["argument1"])
            out["right"] = df_transform(o["argument2"])
        return out
    # generic: normalize type, recurse all values (keep foreign namespaces intact)
    out["type"] = ("minecraft:" + t) if ":" not in t else t
    for k, v in o.items():
        if k == "type": continue
        out[k] = df_transform(v)
    return out

# ---------------- block state transform ----------------
def block_state(o):
    """{'Name': id, 'Properties': {...}} -> shorthand string or {'id', 'properties'}"""
    if isinstance(o, dict) and "Name" in o:
        name = o["Name"]
        props = o.get("Properties") or {}
        if props:
            return {"id": name, "properties": {k: str(v) for k, v in props.items()}}
        return name
    return o

def block_state_deep(o):
    if isinstance(o, dict):
        r = {k: block_state_deep(v) for k, v in o.items()}
        return block_state(r)
    if isinstance(o, list):
        return [block_state_deep(v) for v in o]
    return o

# ---------------- surface rule transform ----------------
SURFACE_COND_TYPES = {"condition", "sequence", "block", "bandlands", "biome", "hole", "not",
                      "noise_threshold", "steep", "stone_depth", "temperature", "vertical_gradient",
                      "water", "y_above", "above_preliminary_surface", "ore_vein"}

def surface_transform(o):
    if isinstance(o, list):
        return [surface_transform(v) for v in o]
    if not isinstance(o, dict):
        return o
    out = {}
    t = o.get("type")
    if isinstance(t, str):
        nt = norm_type(t)
        out["type"] = ("minecraft:" + nt) if nt in SURFACE_COND_TYPES else t
    for k, v in o.items():
        if k == "type": continue
        out[k] = surface_transform(v)
    return block_state(out)

# ---------------- helpers ----------------
def w(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")

def r(path):
    with open(path) as f:
        return json.load(f)

def jcopy(o): return json.loads(json.dumps(o))

# ---------------- main ----------------
def main():
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    shutil.copytree(SRC, WORK)
    OV = f"{WORK}/overlay_26.3"
    os.makedirs(OV, exist_ok=True)

    # 1) pack.mcmeta: append overlay entry
    mcmeta = r(f"{WORK}/pack.mcmeta")
    entries = mcmeta["overlays"]["entries"]
    assert not any(e["directory"] == "overlay_26.3" for e in entries)
    entries.append({"directory": "overlay_26.3", "formats": [121.0, 900], "min_format": 121.0, "max_format": 900})
    w(f"{WORK}/pack.mcmeta", mcmeta)

    # 2) noises: lithosphere custom + vanilla overrides
    count_noise = 0
    for sub in ("data/lithosphere/worldgen/noise", "data/minecraft/worldgen/noise"):
        d = os.path.join(SRC, sub)
        if not os.path.isdir(d): continue
        for dp, _, fn in os.walk(d):
            for f in fn:
                if not f.endswith(".json"): continue
                src = os.path.join(dp, f)
                rel = os.path.relpath(src, SRC)
                dst = os.path.join(OV, rel)
                w(dst, convert_noise(r(src)))
                count_noise += 1
    print(f"noises ported: {count_noise}")

    # 3) density functions: lithosphere + minecraft overrides
    count_df = 0
    for sub in ("data/lithosphere/worldgen/density_function", "data/minecraft/worldgen/density_function"):
        d = os.path.join(SRC, sub)
        if not os.path.isdir(d): continue
        for dp, _, fn in os.walk(d):
            for f in fn:
                if not f.endswith(".json"): continue
                src = os.path.join(dp, f)
                rel = os.path.relpath(src, SRC)
                dst = os.path.join(OV, rel)
                w(dst, df_transform(r(src)))
                count_df += 1
    print(f"density functions ported: {count_df}")

    # 4) noise_settings rebuild (overworld + large_biomes)
    litho_ow = r(f"{SRC}/overlay_26.2/data/minecraft/worldgen/noise_settings/overworld.json")
    litho_lb = r(f"{SRC}/overlay_26.2/data/minecraft/worldgen/noise_settings/large_biomes.json")
    van_ow = r(f"{VAN}/worldgen/noise_settings/overworld.json")

    SPAWN_KEY_MAP = {
        "continentalness": "minecraft:overworld/continents",
        "erosion": "minecraft:overworld/erosion",
        "humidity": "minecraft:overworld/vegetation",
        "weirdness": "minecraft:overworld/ridges",
        "temperature": "minecraft:overworld/temperature",
    }
    def convert_spawn_target(st):
        out = []
        for entry in st:
            e = {}
            for k, v in entry.items():
                if k in ("depth", "offset"):
                    continue
                e[SPAWN_KEY_MAP.get(k, k)] = v
            out.append(e)
        return out

    prelim = df_transform(litho_ow["noise_router"]["preliminary_surface_level"])  # find_top_surface, fields same in 26.3, inner density needs df transform
    chunk_surface = {"type": "minecraft:interpolated", "cell_size_xz": 16, "cell_size_y": 1,
                     "input": jcopy(prelim)}

    def build_noise_settings(litho):
        nr = litho["noise_router"]
        aquifers = jcopy(van_ow["aquifers"])   # vanilla structure (overworld refs — lithosphere uses overworld/* overrides for both presets)
        aquifers["barrier"] = df_transform(nr["barrier"])
        aquifers["fluid_level_floodedness"] = df_transform(nr["fluid_level_floodedness"])
        aquifers["fluid_level_spread"] = df_transform(nr["fluid_level_spread"])
        aquifers["lava"] = df_transform(nr["lava"])
        aquifers["surface_level"] = jcopy(prelim)
        router = {
            "temperature": df_transform(nr["temperature"]),
            "vegetation": df_transform(nr["vegetation"]),
            "continents": nr["continents"],
            "erosion": nr["erosion"],
            "ridges": nr["ridges"],
            "depth": nr["depth"],
            "final_density": nr["final_density"],
            "chunk_surface_level": chunk_surface,
        }
        ns = {
            "aquifers": aquifers,
            "default_block": litho["default_block"],
            "default_fluid": litho["default_fluid"],
            "disable_mob_generation": litho["disable_mob_generation"],
            "legacy_random_source": litho["legacy_random_source"],
            "material_rule": "minecraft:overworld",
            "noise": {"height": litho["noise"]["height"], "min_y": litho["noise"]["min_y"]},
            "noise_router": router,
            "sea_level": litho["sea_level"],
            "spawn_target": convert_spawn_target(litho["spawn_target"]),
        }
        return block_state_deep(ns)

    w(f"{OV}/data/minecraft/worldgen/noise_settings/overworld.json", build_noise_settings(litho_ow))
    w(f"{OV}/data/minecraft/worldgen/noise_settings/large_biomes.json", build_noise_settings(litho_lb))
    print("noise_settings rebuilt: overworld, large_biomes")

    # 5) material rule = ore veins (vanilla refs) + lithosphere surface rule
    surface = surface_transform(litho_ow["surface_rule"])
    mr = {"type": "minecraft:sequence", "sequence": [
        "minecraft:overworld/copper_ore_vein",
        "minecraft:overworld/iron_ore_vein",
        surface,
    ]}
    w(f"{OV}/data/minecraft/worldgen/material_rule/overworld.json", mr)
    print("material_rule/overworld.json written")

    # 6) carvers: vanilla 26.3 base + lithosphere tweaks (deep merge)
    def deep_merge(base, override):
        out = jcopy(base)
        for k, v in override.items():
            if k in ("debug_settings", "yScale"):
                continue
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = deep_merge(out[k], v)
            else:
                out[k] = jcopy(v)
        return out
    for f in ("cave", "cave_extra_underground", "canyon"):
        v3 = r(f"{VAN}/worldgen/carver/{f}.json")
        litho = r(f"{SRC}/overlay_1.21.5/data/minecraft/worldgen/configured_carver/{f}.json")
        merged = deep_merge(v3, litho.get("config", {}))
        merged = block_state_deep(merged)
        w(f"{OV}/data/minecraft/worldgen/carver/{f}.json", merged)
    print("carvers ported: cave, cave_extra_underground, canyon")

    # 7) features: spring_* -> feature/ with flattened config
    for f in ("spring_lava_frozen", "spring_lava_overworld", "spring_water"):
        litho = r(f"{SRC}/data/minecraft/worldgen/configured_feature/{f}.json")
        cfg = litho.get("config", {})
        out = {"type": "minecraft:" + norm_type(litho["type"])}
        for k, v in cfg.items():
            out[k] = v
        out = block_state_deep(out)
        w(f"{OV}/data/minecraft/worldgen/feature/{f}.json", out)
    print("features ported: spring_lava_frozen, spring_lava_overworld, spring_water")

    # 8) zip
    os.makedirs(os.path.dirname(OUT_ZIP), exist_ok=True)
    if os.path.exists(OUT_ZIP):
        os.remove(OUT_ZIP)
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fn in os.walk(WORK):
            for f in fn:
                p = os.path.join(dp, f)
                z.write(p, os.path.relpath(p, WORK))
    print(f"zip written: {OUT_ZIP} ({os.path.getsize(OUT_ZIP)/1024:.0f} KB)")

if __name__ == "__main__":
    main()
