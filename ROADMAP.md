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

## ✅ Shipped in v2.2 (October 2026)

| Item | Notes |
|---|---|
| **Usphere Plus `grand`** | mountains ×1.5 — the missing middle preset between classic (×1.3) and colossal (×2.2); scale presets were the single most repeated request (5+ threads) |
| **Usphere Rivers 0.1** | guaranteed river floors — sand in warm rivers, gravel in cold, mud in bayou/mangrove; "Rivers are so damn sparse" thread family (10+ threads) |
| **2 new real-life biomes** | `still_life:tepui_plateau` (Venezuelan tabletop mountains — "Mesas/Tepuis" request) and `still_life:finnish_taiga` (Finland cold regions request); both `/locate`-verified |
| **Vanilla 26.3 biome restoration** | Still Life's inline biome source had silently replaced every vanilla surface biome (villages lost their host biomes, `dappled_forest` was gone); the true vanilla grid (7594 entries, dumped from the engine) is merged behind the SL entries with a protected-zone filter for community biomes |
| **Feature-order cycle hardening** | the SL+vanilla mix produced `Feature order cycle` crashes; the combined 526-node feature graph is now provably acyclic (per-step topological sort in CI scripts) |
| **Discord token note** | the bot token provided for the Jayzet's Worldgen sweep returned 401 (reset/removed) by the time v2.2 work started; v2.2 priorities were executed from the v2.1 roadmap which was built from the full Discord read |

## 🎯 v2.3 — next community wishes

1. **Real-life biome pack, wave 2** — the remaining screenshot-driven requests: `mesa_plateau`
   (painted-badlands style), Alpine lakes (Norway/Italy), Mediterranean cliffs, Patagonia steppe.
2. **River deltas & waterfalls** — still the hardest request; needs terrain-level work. The
   community-verified trick (wider `lithosphere:rivers` xz_scale near coasts) ships in Plus packs;
   true deltas remain "nearly impossible to generate procedurally" per Jayzet's Discord.
3. **Abyssaline Nether 26.3 port** — coordinate with the upstream beta instead of duplicating.
4. **Deeper worlds (Y=-256) and vanilla-caves option** — engine limits permitting.
5. **`random_patch` spread audit** — keep every `xz_spread` ≤ 8–10 to avoid the famous
   "Detected setBlock in far chunk" spam (Apollo's diagnosis in #bugs-issues).
6. **In-game config screen / preset picker** — datapack-only equivalent: a generator that assembles
   Plus packs from user-selected toggles (scale preset × river style × biome pack).

## 🔭 Later

- Tree sapling support / regrowth (community ports it via TreePlacer; a datapack solution may exist
  via sapling feature swaps)
- Per-biome music/ambience polish passes from the Discord screenshot threads

## Attribution

Original worldgen design: **Lithosphere** & **Still Life** by [Jayzet](https://modrinth.com/user/Jayzet)
(All Rights Reserved). This repository hosts unofficial compatibility ports — see NOTICE.
