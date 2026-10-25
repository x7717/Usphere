# Usphere Roadmap

Community-driven plan. Everything below was collected by reading the **Jayzet's Worldgen** Discord
(all suggestion forums, feedback channels and ~500 screenshots, October 2026) — the community literally
told us what "the best of everything" means.

## ✅ Shipped in v2.0

| Item | Source |
|---|---|
| Still Life 0.3 ported to 26.3 (176+3 biomes, 406 features) | most-requested compat (aoes' backports thread, "AN/SL for 26.x" threads) |
| Modular pack split: `core` (terrain) + `nature` (biomes) | "Fuse Lithosphere/Still Life/… into one" thread — community wants compartmentalized packs |
| `dappled_forest`, `abandoned_camp_*` and all vanilla 26.3 content preserved | verified live |

## ✅ Shipped in v2.1 (October 2026)

| Item | Notes |
|---|---|
| **Real-life biome pack** — `grand_canyon`, `celtic_highlands`, `norwegian_alpine_tundra`, `redwood_coast`, `northern_hardwood_forest` | climate-carved from neighbors; all five `/locate`-verified on seed 31337 |
| **Hot springs** | `still_life:hot_spring` feature + placement in volcanic/cold biomes |
| **Usphere Plus `classic`** | mountains ×1.3, wider rivers, cave-free beaches (3 density-function overlays) |
| **Usphere Plus `colossal`** | mountains ×2.2 variant for the "more and taller mountains" crowd |
| **Offline climate sampler** (`scripts/climate_sampler.py`) | reimplements 26.3 xoroshiro→Perlin→NoiseStack + density functions in numpy; finds where rare biomes generate without brute-force `/locate` |
| **Real-client CI** | GitHub Actions boots an actual Minecraft 26.3 client (Xvfb + llvmpipe + custom GLX shim `scripts/glshim.c` + screenshot javaagent) and uploads world screenshots |

⚠️ **Paper gotcha discovered while verifying:** Paper 26.3 bakes world-gen settings into
`dimensions/…/world_gen_settings.dat` at world creation — updating `world_preset/normal.json`
in an existing world's datapacks does NOT change its biome layout. Recreate the world
after upgrading the pack.

## 🎯 v2.2 — next community wishes (implementation-ready)

1. **Scale presets** — the single most repeated request (5+ threads: "Add a config", "Scale options",
   "Bigger terrain", "more and taller mountains", "make hills/highlands more common + extreme").
   Plan: ship `classic` (current), `grand` (≈1.5× vertical, more highlands), `colossal` variants.
2. **Rivers rework** — 10+ threads ("Rivers are so damn sparse", deltas, widening towards coast,
   sand guaranteed, mud bottoms). Plan: increased `lithosphere:rivers` xz_scale (the community-verified
   tweak), wider river valleys near coasts, guaranteed sand/mud floors.
3. **Hot springs** — the most popular Still Life suggestion (Jayzet himself wants a realistic version
   in SL 1.0). Plan: Iceland-style springs in volcanic/cold biomes, no fantasy calderas.
4. **No caves on beaches** — "caves should not cut through sand" + boulder ring entrances.
5. **Real-life biome pack (screenshots-driven)**: Alpine Tundra (Norwegian highlands concept by
   allyjamy), Celtic Highlands, Northern Hardwood Forest, Redwood/Big Sur coast, Finland cold regions,
   Grand Canyon, Mesas/Tepuis.

## 🔭 Later

- Abyssaline Nether 26.3 port (beta by alacem exists upstream — coordinate instead of duplicating)
- River deltas & waterfalls (needs terrain-level work, "nearly impossible to generate good-looking
  deltas procedurally" per Jayzet's Discord, but gradual widening is doable)
- Vanilla-caves option, deeper worlds (Y=-256) — engine limits permitting
- Tree sapling support / regrowth (community ports it via TreePlacer; a datapack solution may exist
  via sapling feature swaps)
- `random_patch` spread audit: keep every `xz_spread` ≤ 8–10 to avoid the famous
  "Detected setBlock in far chunk" spam (Apollo's diagnosis in #bugs-issues)

## Attribution

Original worldgen design: **Lithosphere** & **Still Life** by [Jayzet](https://modrinth.com/user/Jayzet)
(All Rights Reserved). This repository hosts unofficial compatibility ports — see NOTICE.
