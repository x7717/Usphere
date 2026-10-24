# Usphere

**An unofficial compatibility port of the [Lithosphere](https://modrinth.com/datapack/lithosphere) world-generation datapack to Minecraft 26.3 "Wilderness Bound".**

Lithosphere (by **Jayzet**) replaces vanilla overworld terrain with a fully custom landscape: orogeny-built mountain ranges, karst cave systems, underground rivers, volcanic island chains, reworked river valleys and more — while staying a pure datapack with no mods required.

The upstream project currently ships **1.8.2, which supports Minecraft up to 26.2 only**. This repository carries a ported build that runs on **Minecraft 26.3 (datapack format 121.0)** and was verified on live servers.

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
