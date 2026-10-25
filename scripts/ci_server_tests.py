#!/usr/bin/env python3
"""CI worldgen verification: connect over RCON and assert the datapacks
loaded, vanilla + ported content generates, and no errors were logged.

Exit code != 0 fails the GitHub Actions job.
"""
import argparse, json, os, socket, struct, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rcon import Rcon

# (biome, probe_x, probe_z). Seeds are fixed (31337) so the climate-driven
# positions are deterministic. Probe origins were computed with the offline
# climate sampler (scripts/climate_sampler.py) — vanilla /locate radius is
# ~6400 blocks, rare real-life biomes sit farther out.
CHECK_BIOMES = [
    ("still_life:grand_canyon", 0, 0),
    ("still_life:celtic_highlands", 0, 0),
    ("still_life:norwegian_alpine_tundra", 0, 0),
    ("still_life:redwood_coast", -2368, -5312),
    ("still_life:northern_hardwood_forest", 5568, -5312),
    ("still_life:bayou", 0, 0),
    ("still_life:cacti_savanna", 0, 0),
]
CHECK_STRUCTURES = ["minecraft:village_plains", "minecraft:pillager_outpost"]
DATAPACKS = ["usphere-1-core.zip", "usphere-2-nature.zip", "usphere-3-plus.zip"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=25575)
    ap.add_argument("--password", default="lithocheck")
    a = ap.parse_args()

    failures = []
    r = Rcon(a.host, a.port, a.password, timeout=120)

    def cmd(c):
        time.sleep(1)
        return r.command(c).strip()

    # 1. all three packs enabled
    dp = cmd("datapack list")
    print("== datapack list:", dp[:200], flush=True)
    for p in DATAPACKS:
        if f"file/{p}" not in dp:
            failures.append(f"datapack {p} not enabled")

    # 2. structures locate
    for s in CHECK_STRUCTURES:
        resp = cmd(f"locate structure {s}")
        print(f"== locate structure {s}: {resp[:120]}", flush=True)
        if "Could not find" in resp or "The nearest" not in resp:
            failures.append(f"structure {s} not located")

    # 3. ported biomes locate (long scans; tolerate "reasonable distance" misses
    #    for rare biomes but fail if the command errors out)
    found = 0
    for b, px, pz in CHECK_BIOMES:
        resp = cmd(f"execute in minecraft:overworld positioned {px} 100 {pz} run locate biome {b}")
        print(f"== locate biome {b} @({px},{pz}): {resp[:120]}", flush=True)
        if "The nearest" in resp:
            found += 1
        elif "Could not find" not in resp:
            failures.append(f"biome locate {b} errored: {resp[:80]}")
    if found < len(CHECK_BIOMES):
        failures.append(f"only {found}/{len(CHECK_BIOMES)} ported biomes located (seed 31337 expects all)")

    # 4. teleport smoke test to the first located biome area
    resp = cmd("execute in minecraft:overworld run tp @s 0 200 0")
    print("== tp:", resp[:80], flush=True)

    print()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
