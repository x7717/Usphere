#!/usr/bin/env python3
"""
Port Still Life 0.3 (1.21.5-1.21.8, format 71-83) -> Minecraft 26.3 (format 121.0).
Produces Usphere Nature pack (data preserved under still_life/c/minecraft/towns_and_towers namespaces).
Reuses validated transform logic from port_to_263.py (noise parity formula etc.).
"""
import json, os, shutil, sys, zipfile

sys.path.insert(0, "/home/z/my-project/mc/scripts")
from port_to_263 import (convert_noise, block_state_deep,
                         surface_transform, norm_type, w, r, jcopy)
from port_to_263 import df_transform as _df_transform_orig

ROOT = "/home/z/my-project/mc"
SRC = f"{ROOT}/downloads/sl03"
WORK = f"{ROOT}/packs/usphere-nature-26.3"
VAN = f"{ROOT}/datagen/26.3/generated/data/minecraft"
OUT_ZIP = f"{ROOT}/downloads/usphere-nature-0.3-26.3.zip"

# blocks removed/renamed in 26.3 that Still Life 0.3 uses
BLOCK_RENAMES = {
    "minecraft:chain": "minecraft:iron_chain",
    "still_life:momsoon_forest": "still_life:monsoon_forest",  # upstream typo in SL 0.3
}

def apply_block_renames(o):
    if isinstance(o, dict):
        return {k: apply_block_renames(v) for k, v in o.items()}
    if isinstance(o, list):
        return [apply_block_renames(v) for v in o]
    if isinstance(o, str) and o in BLOCK_RENAMES:
        return BLOCK_RENAMES[o]
    return o

# override w() so every written file gets block renames
_w_orig = w
def w(path, obj):
    _w_orig(path, apply_block_renames(obj))

# block_state_provider registry entries that legally exist as references
BSP_ENTRIES = {"minecraft:cave_vines_body", "minecraft:cave_vines_head", "minecraft:flower_flower_forest",
               "minecraft:flower_meadow", "minecraft:flower_plain", "minecraft:mangrove_propagule",
               "minecraft:podzol_beneath_tree", "minecraft:soil_beneath_tree"}
PROVIDER_KEYS = {"state_provider", "trunk_provider", "foliage_provider", "below_trunk_provider",
                 "block_provider", "stem_provider", "fallback", "then", "leaves_provider",
                 "dirt_provider", "root_provider", "trunk_foliage_provider", "to_place"}

def fix_provider_strings(o, key=None):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            out[k] = fix_provider_strings(v, k)
        return out
    if isinstance(o, list):
        return [fix_provider_strings(v, key) for v in o]
    if (key in PROVIDER_KEYS and isinstance(o, str) and o.startswith("minecraft:")
            and o not in BSP_ENTRIES and ":" not in o[10:]):
        return {"id": o}
    return o

_w2 = w
def w(path, obj):
    _w2(path, fix_provider_strings(obj))


COORD_DF_BOUNDS = {"from_coordinate": -4064, "from_value": -4064.0, "to_coordinate": 4062, "to_value": 4062.0}
COORD_TYPES = ("x", "y", "z", "minecraft:x", "minecraft:y", "minecraft:z",
               "moredfs:x", "moredfs:y", "moredfs:z")
CACHE_TYPES = {"flat_cache", "cache_2d", "cache_once", "cache_all_in_cell"}
ARG_TO_INPUT = {"abs", "blend_density", "cube", "half_negative", "quarter_negative", "square", "squeeze", "invert", "interpolated"}
BINARY = {"add", "mul", "min", "max", "sub"}
INTERP_CELL = {"cell_size_xz": 4, "cell_size_y": 8}

def df_transform_sl(o):
    """26.3 density function transform incl. coordinate DFs (x/y/z from vanilla-1.21 and moredfs)."""
    if isinstance(o, list):
        return [df_transform_sl(v) for v in o]
    if not isinstance(o, dict):
        return o
    t = o.get("type")
    if isinstance(t, str):
        nt = norm_type(t)
        if nt in COORD_TYPES and len(o) == 1:
            out = {"type": "minecraft:gradient", "axis": nt.split(":")[-1]}
            out.update(COORD_DF_BOUNDS)
            return out
        if nt in CACHE_TYPES:
            return {"type": "minecraft:cache", "input": df_transform_sl(o["argument"])}
        if nt == "shifted_noise":
            out = {"type": "minecraft:noise"}
            for k in ("noise", "xz_scale", "y_scale"):
                if k in o: out[k] = o[k]
            for k in ("shift_x", "shift_z"):
                if k in o: out[k] = df_transform_sl(o[k])
            return out
        if nt == "y_clamped_gradient":
            return {"type": "minecraft:gradient", "axis": "y",
                    "from_coordinate": o["from_y"], "to_coordinate": o["to_y"],
                    "from_value": o["from_value"], "to_value": o["to_value"]}
        if nt == "interpolated":
            out = {"type": "minecraft:interpolated", "input": df_transform_sl(o["argument"])}
            out.update(INTERP_CELL)
            return out
        if nt == "invert":
            return {"type": "minecraft:negate", "input": df_transform_sl(o["argument"])}
        if nt in ARG_TO_INPUT:
            return {"type": "minecraft:" + nt, "input": df_transform_sl(o["argument"])}
        if nt in BINARY:
            out = {"type": "minecraft:" + nt}
            if nt == "lerp":
                out["first"] = df_transform_sl(o["argument1"])
                out["second"] = df_transform_sl(o["argument2"])
                if "alpha" in o: out["alpha"] = df_transform_sl(o["alpha"])
                elif "argument" in o: out["alpha"] = df_transform_sl(o["argument"])
            else:
                out["left"] = df_transform_sl(o["argument1"])
                out["right"] = df_transform_sl(o["argument2"])
            return out
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k == "type":
                out[k] = ("minecraft:" + norm_type(v)) if isinstance(v, str) and ":" not in v else v
            else:
                out[k] = df_transform_sl(v)
        return out
    return o


def _trapezoid(n):
    if isinstance(n, (int, float)):
        return {"type": "minecraft:trapezoid", "min": -n, "max": n, "plateau": 0}
    return n

def convert_random_patch_flat(o):
    """o: flattened random_patch node (config unwrapped) -> placed-feature pair (chains flattened)."""
    feat = o.get("feature")
    place = [
        {"type": "minecraft:count", "count": o.get("tries", 96)},
        {"type": "minecraft:offset", "x": _trapezoid(o.get("xz_spread", 7)),
         "y": _trapezoid(o.get("y_spread", 3)), "z": _trapezoid(o.get("xz_spread", 7))},
    ] + list(o.get("placement") or [])
    # flatten chains: nested placed-feature pairs and nested random_patch nodes
    while True:
        if isinstance(feat, dict) and norm_type(feat.get("type")) == "random_patch":
            sub = convert_random_patch_flat(feat.get("config", feat))
            place = place + sub["placement"]
            feat = sub["feature"]
            continue
        if isinstance(feat, dict) and "type" not in feat and "feature" in feat:
            place = place + list(feat.get("placement") or [])
            feat = feat["feature"]
            continue
        break
    return {"feature": feat, "placement": place}

def convert_seagrass(o):
    """{probability: p} -> weighted_random_selector tall/short (vanilla 26.3 rule)."""
    pr = o.get("probability", 0.0)
    w_tall = int(round(pr * 100))
    w_short = 100 - w_tall
    feats = []
    if w_tall > 0:
        feats.append({
            "data": {
                "feature": {"type": "minecraft:simple_block",
                            "to_place": {"id": "minecraft:tall_seagrass", "properties": {"half": "lower"}}},
                "placement": [{"type": "minecraft:block_predicate_filter",
                               "predicate": {"type": "minecraft:matching_blocks",
                                             "blocks": "minecraft:water", "offset": [0, 1, 0]}}],
            },
            "weight": w_tall,
        })
    if w_short > 0:
        feats.append({
            "data": {
                "feature": {"type": "minecraft:simple_block", "to_place": {"id": "minecraft:seagrass"}},
                "placement": [],
            },
            "weight": w_short,
        })
    return {"type": "minecraft:weighted_random_selector", "features": feats}

PATCH_CONV = {}   # "ns:rel" -> extra placement list (for top-level random_patch files)


def flatten_feature_pairs(o):
    """Post-pass: {feature: {feature: F, placement: P2}, placement: P1} -> {feature: F, placement: P1+P2}.
    Repeats until fixpoint. Returns (obj, changed)."""
    if isinstance(o, list):
        out, ch = [], False
        for v in o:
            r, c = flatten_feature_pairs(v)
            out.append(r); ch = ch or c
        return out, ch
    if not isinstance(o, dict):
        return o, False
    changed = False
    # children first
    out = {}
    for k, v in o.items():
        r, c = flatten_feature_pairs(v)
        out[k] = r
        changed = changed or c
    fv = out.get("feature")
    if ("feature" in out and "placement" in out and isinstance(fv, dict)
            and "type" not in fv and "feature" in fv):
        out = {"feature": fv["feature"],
               "placement": list(out["placement"]) + list(fv.get("placement") or [])}
        changed = True
        # the new feature may itself be a pair
        fv2 = out["feature"]
        if isinstance(fv2, dict) and "type" not in fv2 and "feature" in fv2:
            out = {"feature": fv2["feature"],
                   "placement": list(out["placement"]) + list(fv2.get("placement") or [])}
    return out, changed

def flatten_fixpoint(o):
    for _ in range(12):
        o, ch = flatten_feature_pairs(o)
        if not ch:
            break
    return o


def build_type_samples():
    """Map: feature type -> vanilla 26.3 sample keys (for required-key defaulting)."""
    samples = {}
    d = f"{VAN}/worldgen/feature"
    for root, dirs, files in os.walk(d):
        for f in files:
            if not f.endswith(".json"):
                continue
            try:
                j = json.load(open(os.path.join(root, f)))
            except Exception:
                continue
            t = j.get("type")
            if isinstance(t, str) and t not in samples:
                samples[t] = j
    return samples

def fill_required_keys(j, samples, where=""):
    """Recursively fill keys that a vanilla sample of the same feature type has but our node lacks."""
    if isinstance(j, list):
        return [fill_required_keys(v, samples, where) for v in j]
    if not isinstance(j, dict):
        return j
    t = j.get("type")
    if isinstance(t, str) and t in samples:
        samp = samples[t]
        for k, v in samp.items():
            if k not in j and k != "type":
                j[k] = jcopy(v)
    return {k: fill_required_keys(v, samples, where) for k, v in j.items()}


# 26.3 inline biome-source climate parameters keep plain names (verified against vanilla codecs)
SPAWN_KEY_MAP2 = {}

def convert_biome_source_inline(src):
    """1.21.8 inline multi_noise biome source -> 26.3 format (renamed params, no depth/offset)."""
    out = {"type": "minecraft:multi_noise"}
    if "preset" in src:
        out["preset"] = src["preset"]
        return out
    biomes = []
    for e in src.get("biomes", []):
        p_in = e.get("parameters", {})
        p_out = {}
        for k, v in p_in.items():
            p_out[k] = v          # keep depth/offset + plain names (26.3 biome source = 1.21.8 format?)
        biomes.append({"biome": e["biome"], "parameters": p_out})
    out["biomes"] = biomes
    return out

def port_dimension_and_preset():
    """SL overrides data/minecraft/dimension/overworld.json with an inline biome source.
    Port it and mirror it into world_preset/normal.json so the default world uses it."""
    src = r(f"{SRC}/data/minecraft/dimension/overworld.json")
    gen = src.get("generator", {})
    bs = convert_biome_source_inline(gen.get("biome_source", {}))
    dim = {"type": "minecraft:overworld",
           "generator": {"type": "minecraft:noise", "settings": gen.get("settings", "minecraft:overworld"),
                         "biome_source": bs}}
    w(f"{WORK}/data/minecraft/dimension/overworld.json", dim)
    # world preset: vanilla 26.3 structure with SL overworld generator
    wp = r(f"{VAN}/worldgen/world_preset/normal.json")
    wp["dimensions"]["minecraft:overworld"] = dim
    w(f"{WORK}/data/minecraft/worldgen/world_preset/normal.json", wp)
    # debug: drop dimension file (bisect variant 1)
    os.remove(f"{WORK}/data/minecraft/dimension/overworld.json")
    return len(bs.get("biomes", []))

stats = {}

# ---------------- state providers ----------------
def int_provider(o):
    return o  # 1.21.8 int providers are format-stable (plain int or typed)

def provider_transform(o):
    """Transform block state providers 1.21.8 -> 26.3. Returns new dict/scalar."""
    if isinstance(o, list):
        return [provider_transform(v) for v in o]
    if not isinstance(o, dict):
        return o
    t = o.get("type")
    if isinstance(t, str):
        nt = norm_type(t)
        if nt == "simple_state_provider":
            st = block_state_deep(jcopy(o.get("state")))
            if isinstance(st, str):
                return {"id": st}
            return st
        if nt == "weighted_state_provider":
            entries = []
            for e in o.get("entries", []):
                entries.append({"data": block_state_deep(e.get("data", e.get("state"))),
                                "weight": e.get("weight", 1)})
            return {"type": "minecraft:weighted", "entries": entries}
        if nt == "rule_based_state_provider":
            out = {"type": "minecraft:rule_based"}
            for k, v in o.items():
                if k != "type":
                    out[k] = provider_transform(v)
            return out
        if nt == "randomized_int_state_provider":
            out = {"type": "minecraft:randomized_int"}
            out["property"] = o["property"]
            out["source"] = provider_transform(o.get("source") or o.get("state"))
            out["values"] = o["values"]
            return out
        if nt == "noise_provider":
            out = {"type": "minecraft:noise"}
            out["noise"] = convert_noise(o["noise"])
            for k in ("scale", "seed"):
                if k in o: out[k] = o[k]
            out["states"] = [block_state_deep(s) if isinstance(s, dict) else s
                             for s in o.get("states", o.get("entries", []))]
            return out
        if nt == "dual_noise_provider":
            out = {"type": "minecraft:dual_noise"}
            out["noise"] = convert_noise(o["noise"])
            out["slow_noise"] = convert_noise(o["slow_noise"])
            for k in ("scale", "slow_scale", "seed", "variety"):
                if k in o: out[k] = o[k]
            out["states"] = [block_state_deep(s) if isinstance(s, dict) else s
                             for s in o.get("states", o.get("entries", []))]
            return out
        if nt == "noise_threshold_provider":
            out = {"type": "minecraft:noise_threshold"}
            out["noise"] = convert_noise(o["noise"])
            for k in ("scale", "seed", "threshold", "lower_variability", "upper_variability",
                      "default_state", "low_chance", "low_states", "high_chance", "high_states"):
                if k in o:
                    out[k] = provider_transform(o[k]) if k.endswith(("state", "states")) else o[k]
            return out
        if nt == "rotated_block_provider":
            return {"type": "minecraft:rotated", "state": block_state_deep(o["state"])}
        # any other typed provider: keep, recurse
        out = {}
        for k, v in o.items():
            out[k] = provider_transform(v)
        return out
    return {k: provider_transform(v) for k, v in o.items()}

# ---------------- feature / placement transforms ----------------
FEATURE_TYPE_RENAMES = {
    "minecraft:kelp": "minecraft:block_column",
    "minecraft:twisting_vines": "minecraft:block_column",
    "minecraft:nether_forest_vegetation": "minecraft:simple_block",
    "minecraft:sea_pickle": "minecraft:simple_block",
    "minecraft:glowstone_blob": "minecraft:random_neighbor_spread",
    "minecraft:sculk_patch": "minecraft:sequence",
    "minecraft:seagrass": "minecraft:weighted_random_selector",
    "minecraft:basalt_columns": "minecraft:weighted_random_selector",
    "minecraft:weeping_vines": "minecraft:block_column",
}
UNPORTABLE = {"minecraft:basalt_pillar", "minecraft:desert_well", "minecraft:coral_mushroom"}

def feature_content_transform(o):
    """Recursive transform inside configured features (after config unwrap)."""
    if isinstance(o, list):
        return [feature_content_transform(v) for v in o]
    if not isinstance(o, dict):
        return o
    # typeless rule-based provider shorthand: {fallback, rules} -> add type
    if "type" not in o and "fallback" in o and "rules" in o:
        o = {"type": "minecraft:rule_based_state_provider", **o}
        return provider_transform(o)
    # generic config unwrap: {type, config:{...}} -> {type, ...} (any nesting depth)
    if "type" in o and isinstance(o.get("config"), dict):
        flat = {"type": o["type"]}
        flat.update(o["config"])
        return feature_content_transform(flat)
    t = o.get("type")
    nt0 = norm_type(t) if isinstance(t, str) else None
    if nt0 == "random_patch":
        pair = convert_random_patch_flat(o.get("config", o))
        return feature_content_transform(pair)
    if nt0 == "seagrass":
        return convert_seagrass(o.get("config", o))
    if nt0 == "constant" and "value" in o and len(o) == 2:
        return o["value"]
    # 1.21.x int/float providers wrap range in "value" — 26.3 is flat
    if (isinstance(o.get("value"), dict) and nt0 in ("uniform", "trapezoid", "clamped", "clamped_normal")
            and len(o) == 2):
        flat = {"type": "minecraft:" + nt0}
        flat.update(o["value"])
        return flat
    if nt0 == "tree":
        out = {k: feature_content_transform(v) for k, v in o.items() if k not in ("dirt_provider", "force_dirt")}
        out.setdefault("below_trunk_provider", "minecraft:soil_beneath_tree")
        return out
    # placement modifier conversion
    if t == "minecraft:random_offset":
        xz = o.get("xz_spread", 0)
        y = o.get("y_spread", 0)
        return {"type": "minecraft:offset", "x": int_provider(xz), "y": int_provider(y), "z": int_provider(xz)}
    if isinstance(t, str):
        nt = norm_type(t)
        if nt in ("simple_state_provider", "weighted_state_provider", "rule_based_state_provider",
                  "randomized_int_state_provider", "noise_provider", "dual_noise_provider",
                  "noise_threshold_provider", "rotated_block_provider"):
            return provider_transform(o)
        if nt in UNPORTABLE:
            raise ValueError(f"unportable feature/provider type used: {t}")
        out = {}
        new_t = "minecraft:" + norm_type(FEATURE_TYPE_RENAMES.get(t, t))
        out["type"] = new_t
        for k, v in o.items():
            if k == "type": continue
            out[k] = feature_content_transform(v)
        return out
    return {k: feature_content_transform(v) for k, v in o.items()}

def unwrap_feature(j):
    """configured_feature {type, config:{...}} -> feature {type, ...config}"""
    out = {"type": "minecraft:" + norm_type(j["type"])}
    for k, v in j.get("config", {}).items():
        out[k] = v
    return out

# ---------------- biome transform ----------------
EFFECT_MOVE = {
    "sky_color": "minecraft:visual/sky_color",
    "fog_color": "minecraft:visual/fog_color",
    "water_fog_color": "minecraft:visual/water_fog_color",
    "music_volume": "minecraft:audio/music_volume",
}
EFFECTS_KEEP = {"water_color", "foliage_color", "grass_color", "grass_color_modifier", "dry_foliage_color"}

def biome_transform(j):
    out = {}
    attrs = {}
    # temperature / downfall / precipitation / carvers / features stay
    for k in ("temperature", "downfall", "has_precipitation", "carvers", "features"):
        if k in j:
            out[k] = jcopy(j[k])
    # spawners + spawn_costs -> natural_mob_spawns attribute
    if "spawners" in j or "spawn_costs" in j:
        spawns_by_category = {}
        for cat, lst in (j.get("spawners") or {}).items():
            nl = []
            for e in lst:
                e = jcopy(e)
                if "minCount" in e or "maxCount" in e:
                    mn, mx = e.pop("minCount", 0), e.pop("maxCount", 0)
                    e["count"] = mn if mn == mx else {"type": "minecraft:uniform",
                                                       "min_inclusive": mn, "max_inclusive": mx}
                nl.append(e)
            spawns_by_category[cat] = nl
        spawn_costs = jcopy(j.get("spawn_costs", {}))
        attrs["minecraft:gameplay/natural_mob_spawns"] = {
            "argument": {"spawn_costs": spawn_costs, "spawns_by_category": spawns_by_category},
            "modifier": "overlay",
        }
    if "creature_spawn_probability" in j:
        attrs["minecraft:gameplay/creature_world_gen_spawn_probability"] = j["creature_spawn_probability"]
    # effects split
    eff = jcopy(j.get("effects", {}))
    new_eff = {}
    amb = {}
    for k, v in eff.items():
        if k in EFFECTS_KEEP:
            new_eff[k] = v
        elif k == "mood_sound":
            amb["mood"] = v
        elif k == "additions_sound":
            amb["additions"] = v
        elif k == "loop_sound":
            amb["loop"] = v
        elif k == "music":
            # 1.21.8: weighted list [{data:{...},weight:N},...] -> 26.3: single object
            if isinstance(v, list) and v:
                best = max(v, key=lambda e: e.get("weight", 1))
                m = jcopy(best.get("data", best))
            elif isinstance(v, dict):
                m = jcopy(v)
            else:
                m = None
            if m:
                m.pop("replace_current_music", None)
                attrs["minecraft:audio/background_music"] = {"default": m}
        elif k == "particle_color":
            attrs["minecraft:visual/ambient_particles"] = {"argument": [v], "modifier": "append"}
        elif k in EFFECT_MOVE:
            attrs[EFFECT_MOVE[k]] = v
        else:
            new_eff[k] = v   # unknown: keep in effects, warn later
    if amb:
        attrs["minecraft:audio/ambient_sounds"] = amb
    if new_eff:
        out["effects"] = new_eff
    if attrs:
        out["attributes"] = attrs
    return out

# ---------------- noise settings ----------------
def build_noise_settings(sl):
    van_ow = r(f"{VAN}/worldgen/noise_settings/overworld.json")
    nr = sl["noise_router"]
    # 1.21.8 initial_density_without_jaggedness -> 26.2 find_top_surface(preliminary) -> 26.3 chunk_surface_level
    van_prelim = r(f"{VAN}/worldgen/density_function/overworld/preliminary_surface_level.json")
    prelim = {"type": "minecraft:find_top_surface", "cell_height": 8,
              "density": df_transform_sl(nr["initial_density_without_jaggedness"]),
              "lower_bound": jcopy(van_prelim["lower_bound"]),
              "upper_bound": jcopy(van_prelim["upper_bound"])}
    chunk_surface = {"type": "minecraft:interpolated", "cell_size_xz": 16, "cell_size_y": 1,
                     "input": jcopy(prelim)}
    aquifers = jcopy(van_ow["aquifers"])
    aquifers["barrier"] = df_transform_sl(nr["barrier"])
    aquifers["fluid_level_floodedness"] = df_transform_sl(nr["fluid_level_floodedness"])
    aquifers["fluid_level_spread"] = df_transform_sl(nr["fluid_level_spread"])
    aquifers["lava"] = df_transform_sl(nr["lava"])
    aquifers["surface_level"] = jcopy(prelim)
    ns = {
        "aquifers": aquifers,
        "default_block": block_state_deep(jcopy(sl["default_block"])),
        "default_fluid": block_state_deep(jcopy(sl["default_fluid"])),
        "disable_mob_generation": sl["disable_mob_generation"],
        "legacy_random_source": sl["legacy_random_source"],
        "material_rule": "minecraft:still_life",
        "noise": {"height": sl["noise"]["height"], "min_y": sl["noise"]["min_y"]},
        "noise_router": {
            "temperature": nr["temperature"],
            "vegetation": nr["vegetation"],
            "continents": nr["continents"],
            "erosion": nr["erosion"],
            "ridges": nr["ridges"],
            "depth": nr["depth"],
            "final_density": nr["final_density"],
            "chunk_surface_level": chunk_surface,
        },
        "sea_level": sl["sea_level"],
        "spawn_target": convert_spawn_target(sl["spawn_target"]),
    }
    return ns

# ---------------- carvers ----------------
def _anchor_like(d):
    return isinstance(d, dict) and d and all(k in ("absolute", "above_bottom", "below_top") for k in d)

def deep_merge(base, override):
    out = jcopy(base)
    for k, v in override.items():
        if k in ("debug_settings", "yScale"):
            continue
        b = out.get(k)
        if isinstance(v, dict) and isinstance(b, dict):
            if _anchor_like(v) or _anchor_like(b):
                out[k] = jcopy(v)                     # alternative encodings: replace, never merge
            elif isinstance(v.get("type"), str) and v.get("type") == b.get("type"):
                out[k] = deep_merge(b, v)             # same typed structure: recurse
            else:
                merged = jcopy(b)                     # plain config dicts: flat union, override wins
                merged.update(jcopy(v))
                out[k] = merged
        else:
            out[k] = jcopy(v)
    return out

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

# ---------------- main ----------------
def main():
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)

    # pack.mcmeta
    w(f"{WORK}/pack.mcmeta", {
        "pack": {
            "pack_format": 121,
            "min_format": 121.0,
            "max_format": 900,
            "description": "Usphere Nature — Still Life 0.3 ported to Minecraft 26.3 (unofficial port of Jayzet's Still Life)",
        }
    })

    # pack.png
    if os.path.exists(f"{SRC}/pack.png"):
        shutil.copy(f"{SRC}/pack.png", f"{WORK}/pack.png")

    # tags: copy verbatim
    n_tags = 0
    for ns in ("c", "still_life", "minecraft", "towns_and_towers"):
        d = f"{SRC}/data/{ns}/tags"
        if not os.path.isdir(d): continue
        for dp, _, fn in os.walk(d):
            for f in fn:
                if not f.endswith(".json"): continue
                src = os.path.join(dp, f)
                rel = os.path.relpath(src, f"{SRC}/data")
                w(os.path.join(WORK, "data", rel), r(src))
                n_tags += 1
    stats["tags"] = n_tags

    # c/worldgen/biome_colors.json (custom file, copy)
    for extra in ("worldgen/biome_colors.json",):
        p = f"{SRC}/data/c/{extra}"
        if os.path.exists(p):
            w(os.path.join(WORK, "data/c", extra), r(p))

    # noises
    n = 0
    for ns in ("still_life", "minecraft"):
        d = f"{SRC}/data/{ns}/worldgen/noise"
        if not os.path.isdir(d): continue
        for f in sorted(os.listdir(d)):
            if not f.endswith(".json"): continue
            w(f"{WORK}/data/{ns}/worldgen/noise/{f}", convert_noise(r(os.path.join(d, f))))
            n += 1
    stats["noises"] = n

    # density functions (still_life + minecraft overrides)
    n = 0
    for ns in ("still_life", "minecraft"):
        base = f"{SRC}/data/{ns}/worldgen/density_function"
        if not os.path.isdir(base): continue
        for dp, _, fn in os.walk(base):
            for f in fn:
                if not f.endswith(".json"): continue
                src = os.path.join(dp, f)
                rel = os.path.relpath(src, base)
                w(f"{WORK}/data/{ns}/worldgen/density_function/{rel}", df_transform_sl(r(src)))
                n += 1
    stats["density_functions"] = n

    # configured_feature -> feature
    TYPE_SAMPLES = build_type_samples()
    n = 0
    errors = []
    for ns in ("still_life", "minecraft"):
        base = f"{SRC}/data/{ns}/worldgen/configured_feature"
        if not os.path.isdir(base): continue
        for dp, _, fn in os.walk(base):
            for f in fn:
                if not f.endswith(".json"): continue
                src = os.path.join(dp, f)
                rel = os.path.relpath(src, base)
                try:
                    j = unwrap_feature(r(src))
                    if norm_type(j.get("type")) == "random_patch":
                        conv = convert_random_patch_flat(j)
                        extra = feature_content_transform({"placement": conv["placement"]})["placement"]
                        PATCH_CONV[f"{ns}:{rel}"] = extra
                        j = conv["feature"]          # file becomes the inner feature
                        if isinstance(j, dict) and "type" not in j:
                            raise ValueError("random_patch inner has no type: " + rel)
                    j = block_state_deep(flatten_fixpoint(feature_content_transform(j)))
                    j = fill_required_keys(j, TYPE_SAMPLES, f"{ns}/{rel}")
                    w(f"{WORK}/data/{ns}/worldgen/feature/{rel}", j)
                    n += 1
                except Exception as ex:
                    errors.append(f"{ns}/{rel}: {ex}")
    stats["features"] = n
    stats["feature_errors"] = errors

    # placed_feature
    n = 0
    for ns in ("still_life", "minecraft"):
        base = f"{SRC}/data/{ns}/worldgen/placed_feature"
        if not os.path.isdir(base): continue
        for dp, _, fn in os.walk(base):
            for f in fn:
                if not f.endswith(".json"): continue
                src = os.path.join(dp, f)
                rel = os.path.relpath(src, base)
                j = r(src)
                def patch_refs(o):
                    if isinstance(o, dict):
                        fv = o.get("feature")
                        if isinstance(fv, str) and fv in PATCH_CONV:
                            o["placement"] = list(o.get("placement") or []) + PATCH_CONV[fv]
                        for v in list(o.values()):
                            patch_refs(v)
                    elif isinstance(o, list):
                        for v in o:
                            patch_refs(v)
                    return o
                j = patch_refs(j)
                j = flatten_fixpoint(feature_content_transform(j))
                if not (isinstance(j.get("feature"), (str, dict)) and "placement" in j):
                    errors.append(f"placed feature without feature/placement: {ns}/{rel}")
                w(f"{WORK}/data/{ns}/worldgen/placed_feature/{rel}", block_state_deep(j))
                n += 1
    stats["placed_features"] = n

    # configured_carver -> carver (vanilla 26.3 base + SL tweaks)
    n = 0
    for f in ("cave", "cave_extra_underground", "canyon"):
        p = f"{SRC}/data/minecraft/worldgen/configured_carver/{f}.json"
        if not os.path.exists(p):
            continue
        v3 = r(f"{VAN}/worldgen/carver/{f}.json")
        sl = r(p)
        merged = deep_merge(v3, sl.get("config", {}))
        w(f"{WORK}/data/minecraft/worldgen/carver/{f}.json", feature_content_transform(merged))
        n += 1
    stats["carvers"] = n

    # biomes
    n = 0
    for ns in ("still_life", "minecraft"):
        base = f"{SRC}/data/{ns}/worldgen/biome"
        if not os.path.isdir(base): continue
        for f in sorted(os.listdir(base)):
            if not f.endswith(".json"): continue
            w(f"{WORK}/data/{ns}/worldgen/biome/{f}", biome_transform(r(os.path.join(base, f))))
            n += 1
    stats["biomes"] = n

    # noise_settings/overworld.json + material_rule/still_life.json
    sl_ow = r(f"{SRC}/data/minecraft/worldgen/noise_settings/overworld.json")
    w(f"{WORK}/data/minecraft/worldgen/noise_settings/overworld.json", build_noise_settings(sl_ow))
    surface = surface_transform(sl_ow["surface_rule"])
    mr = {"type": "minecraft:sequence", "sequence": [
        "minecraft:overworld/copper_ore_vein",
        "minecraft:overworld/iron_ore_vein",
        surface,
    ]}
    w(f"{WORK}/data/minecraft/worldgen/material_rule/still_life.json", mr)
    stats["noise_settings"] = 1
    stats["material_rule"] = 1
    stats["preset_biomes"] = port_dimension_and_preset()

    # zip
    if os.path.exists(OUT_ZIP):
        os.remove(OUT_ZIP)
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fn in os.walk(WORK):
            for f in fn:
                p = os.path.join(dp, f)
                z.write(p, os.path.relpath(p, WORK))
    stats["zip"] = OUT_ZIP
    stats["zip_kb"] = os.path.getsize(OUT_ZIP) // 1024

    print(json.dumps({k: v for k, v in stats.items() if k != "feature_errors"}, indent=1))
    if stats["feature_errors"]:
        print("FEATURE ERRORS:")
        for e in stats["feature_errors"][:20]:
            print("  ", e)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
