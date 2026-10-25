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

## 🎯 v2.1 — top community wishes (implementation-ready)

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
