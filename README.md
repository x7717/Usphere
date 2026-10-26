# Usphere

[![worldgen-tests](https://github.com/x7717/Usphere/actions/workflows/worldgen-test.yml/badge.svg)](https://github.com/x7717/Usphere/actions/workflows/worldgen-test.yml)

**An unofficial compatibility port of the [Lithosphere](https://modrinth.com/datapack/lithosphere) world-generation datapack to Minecraft 26.3 "Wilderness Bound".**

Lithosphere (by **Jayzet**) replaces vanilla overworld terrain with a fully custom landscape: orogeny-built mountain ranges, karst cave systems, underground rivers, volcanic island chains, reworked river valleys and more — while staying a pure datapack with no mods required.

The upstream project currently ships **1.8.2, which supports Minecraft up to 26.2 only**. This repository carries a ported build that runs on **Minecraft 26.3 (datapack format 121.0)** and was verified on live servers.


## 🌊 What's new in v2.2 — the community wishlist continues

| Pack | File | What it does |
|---|---|---|
| **Usphere Nature 0.6** | `usphere-nature-0.6-26.3.zip` | Still Life port + **2 new real-life biomes**: `tepui_plateau` (Venezuelan tabletop mountains) and `finnish_taiga` (snowy Fennoscandian taiga with berry bushes, granite boulders, fallen spruce logs) + **vanilla 26.3 biomes restored** into the climate map |
| **Usphere Rivers 0.1** | `usphere-rivers-0.1-26.3.zip` | The single most requested feature after scale presets: **guaranteed river floors** — sand bottoms in warm rivers, gravel in cold ones, mud bottoms in bayou/mangrove marshes |
| **Usphere Plus grand 0.1** | `usphere-plus-grand-0.1-26.3.zip` | The missing middle scale preset: mountains ×1.5 (between classic ×1.3 and colossal ×2.2) |

Engineering highlights (all live-verified on Paper 26.3-223, seed 31337):

- **Climate-gap discovery**: Still Life's own tropical family (tropical_rainforest, monsoon_forest, humid_savanna, tropical_highlands) is **unreachable on 26.3** — its temperature windows sit above the maximum the ported climate fields produce (verified by live `/locate` MISSes and an offline climate sampler). The new biomes therefore live in verified climate gaps / tie-overtake slices of LIVE donor biomes instead of dead climate windows.
- **Tie-overtake pattern**: copies of a live donor's climate entries inserted *before* the donor win the R-tree's stable tie-break, so a new biome grows inside the donor's area while the donor keeps the edges (`tepui_plateau` @ 2249 blocks, `finnish_taiga` @ 3696, `painted_peaks` still alive 64 blocks away).
- **Vanilla merge**: Still Life's inline biome source silently replaced *all* vanilla surface biomes (villages lost their host biomes, `dappled_forest` vanished). v2.2 appends the true vanilla 26.3 grid (7594 entries, dumped from the engine's own `OverworldBiomeBuilder`) after the SL entries — SL keeps ties, vanilla fills the gaps, villages are back (`/locate structure minecraft:village_plains` → found), and protected community biomes are shielded from vanilla boxes by an interval-overlap filter.
- **Feature-order cycle fix**: mixing Still Life and vanilla biomes created `Feature order cycle` crashes (`patch_sugar_cane`/`patch_pumpkin`, `fossil_*`/`monster_room`, `emeralds`/`underwater_magma`, mossy/dripstone caves...). The full pair-graph is now rebuilt per step and re-sorted so the combined pack is provably acyclic (526-node graph, topological sort passes).
- Live locate matrix (seed 31337): all 7 community/real-life biomes + `dappled_forest` + village structures verified.

## 🌿 What's new in v2.0 — Usphere Nature (Still Life for 26.3)

Usphere is now **modular**:

| Pack | File | What it does |
|---|---|---|
| **Usphere Core** | `lithosphere-1.8.2-26.3.zip` | terrain engine — ported Lithosphere 1.8.2 (26.2 → 26.3) |
| **Usphere Nature** | `usphere-nature-0.6-26.3.zip` | **Still Life 0.3 ported (1.21.5-1.21.8 → 26.3)**: 179 biomes, 406 features, 452 placed features, custom climate (temperature-by-latitude!), requires Core |

Install **both** zips (nature must load after core). Verified live on Paper 26.3-222, seed 31337:
both packs load with **0 errors**, SL biomes generate (`bayou` @ 3162 blocks, spawn inside
`cacti_savanna`), villages still locate, 24×24-chunk forceload exercise clean.

The ported content: block-state/provider format migration (26.3 inline shorthands),
`random_patch` → inlined placed-features (Mojang's own conversion rule), `seagrass` →
`weighted_random_selector`, spawner data → biome `attributes`, music/effects split into
`minecraft:audio/*` + `minecraft:visual/*`, `find_top_surface` bounds, x/y/z coordinate
density functions → `gradient` (including replacing the `moredfs:z` mod dependency with a
vanilla-only equivalent), and the full inline multi-noise biome source (2818 climate entries)
carried through `dimension/overworld.json` + `world_preset/normal.json`.

Port scripts: [`verification/port-scripts/port_sl_to_263.py`](./verification/port-scripts/port_sl_to_263.py).

## 🗺️ Roadmap

See [`ROADMAP.md`](./ROADMAP.md) — built from a full read of the Jayzet's Worldgen Discord
(100+ suggestion threads, screenshots included): scale presets, rivers rework, hot springs,
no-caves-on-beaches, real-life biome pack and more.

## Download

Grab [`lithosphere-1.8.2-26.3.zip`](./lithosphere-1.8.2-26.3.zip) (or check the [Releases](../../releases) page) and drop it into your world's `datapacks` folder.

| | |
|---|---|
| Upstream | Lithosphere 1.8.2 by Jayzet ([Modrinth](https://modrinth.com/datapack/lithosphere)) |
| Target | Minecraft **26.3 "Wilderness Bound"** (datapack format **121.0**, data version 5023) |
| Java | **Java 25+** (required by 26.3 itself) |
| Loaders tested | Paper 26.3-218 (worldgen is engine-driven, so Vanilla / Fabric / NeoForge behave the same) |
| Test seed | 31337 |

## How the port works

The port **adds an `overlay_26.3` layer** to the pack (following Lithosphere's own multi-version overlay convention) instead of touching existing layers, so the 1.20 – 26.2 fallbacks stay byte-identical. 88 files were ported: 30 noises, 49 density functions, 2 noise settings, 1 material rule, 3 carvers, 4 features.

Minecraft 26.3 broke worldgen formats heavily; every one of these was migrated:

- `configured_feature` → `feature`, `configured_carver` → `carver`, the `config` wrapper was removed
- Block states: `Name`/`Properties` → `id`/`properties` (plus string shorthand)
- Density functions: four cache types merged into `minecraft:cache`; `shifted_noise` removed (→ `noise` + `shift_x/z`); `y_clamped_gradient` → `gradient`; `invert` → `negate`; `interpolated` now requires `cell_size_xz`/`cell_size_y`
- Noise settings: `surface_rule` → `material_rule` registry; `aquifers_enabled` → `aquifers` object; ore veins → material rules; `preliminary_surface_level` → `chunk_surface_level`; `spawn_target` now references namespaced parameters
- Noise format: `firstOctave` → `base_octave`, `amplitudes` → `amplitude_modifiers`, and the new `base_amplitude` field — **the formula is undocumented, so it was reverse-engineered from the 26.3 server bytecode** (`NormalNoise#computeParityBaseAmplitude`) and validated against all 63 vanilla noises with 1e-9 accuracy
- Noise math now runs in **float32** (previously float64) — see [limitations](#known-limitations)

## Verification results

Two identical servers (Paper 26.2-134 / 26.3-218, seed 31337) were diffed with a custom check plugin:

| Check | Result |
|---|---|
| Datapack load on 26.3 | 0 errors, 0 warnings |
| Biome grid near spawn (17×17 × 4 Y-levels) | **1156/1156 = 100%** |
| Biome grid far from spawn (11×11) | **484/484 = 100%** |
| Structures `/locate` (22 types) | **22/22 identical** |
| Registries | only expected vanilla 26.3 additions |
| Terrain heights | 74.7% exactly identical, ±1–12 elsewhere — **vanilla itself drifts more (53.6%)** between 26.2 → 26.3 |
| New vanilla 26.3 content (`dappled_forest` biome, `abandoned_camp_*` structures) | verified generating in the ported world |

The height drift comes from Mojang's switch to float32 noise math and their own spline tweaks — it is engine-level and cannot be fixed from a datapack. Notably, the port tracks vanilla's own 26.2 → 26.3 changes *better* than vanilla does itself.

Raw reports: [`verification/`](./verification) · new-26.3-content protocol: [`locates-26.3-new-content.txt`](./verification/locates-26.3-new-content.txt)

## Installation

**Server** — put the zip into `<world folder>/datapacks/`, then restart the server.

**Singleplayer** — Edit world → Open World Folder → `datapacks/` → drop the zip in → `/reload`.

Requires Minecraft 26.3.

## Known limitations

- Terrain heights may differ from a 26.2 world by ±1–12 blocks in places — this is float32 noise in the 26.3 engine and affects vanilla as well.
- Mojang removed several carver options in 26.3 (`replaceable`, `lava_level`, `yScale`); the affected Lithosphere carver settings are approximated where possible.
- Where exactly new 26.3 biomes/structures appear follows Lithosphere's reshaped climate, so their layout differs from pure vanilla — presence is guaranteed, placement is Lithosphere's.

## Credits & licensing

- The **Lithosphere** datapack and all original worldgen design — **[Jayzet](https://modrinth.com/user/Jayzet)**, upstream on [Modrinth](https://modrinth.com/datapack/lithosphere). Upstream is **All Rights Reserved** — see [`NOTICE`](./NOTICE). All credit and rights belong to the original author; this unofficial port is hosted for community convenience, and the format migration itself is documented openly in [`verification/port-scripts/`](./verification/port-scripts).
- 26.3 format migration, base-amplitude reverse engineering and verification tooling — this repository's contributors.

## Repository layout

```
├── lithosphere-1.8.2-26.3.zip   ← the datapack (drop into datapacks/)
├── NOTICE                        attribution & upstream licensing note
└── verification/                 parity reports, locate logs, port scripts
```
