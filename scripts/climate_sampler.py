#!/usr/bin/env python3
"""Offline Minecraft 26.3 climate sampler for Usphere biome-source analysis.

Reimplements (from decompiled mojang_26.3.jar):
- Xoroshiro128PlusPlus / XoroshiroRandomSource / RandomSupport (MD5 hash seeds)
- GradientNoise/PerlinNoise (float32 core, per-octave PerlinNoise via string-hashed seeds)
- NormalNoise (NoiseStack: first stack + second stack at freq*1.0181268882175227)
- Density functions: noise, spline (hermite, linearExtend), add, mul, abs, cache, gradient
- Climate fitness metric: sum of squared fixed-point (x10000) interval gaps over 7 axes
"""
import json, os, hashlib, math
import numpy as np

U64 = (1 << 64) - 1

def rotl(x, n):
    x &= U64
    return ((x << n) | (x >> (64 - n))) & U64

def stafford13(z):
    z &= U64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & U64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & U64
    return (z ^ (z >> 31)) & U64

class Xoroshiro128PlusPlus:
    __slots__ = ("lo", "hi")
    def __init__(self, lo, hi):
        self.lo, self.hi = lo & U64, hi & U64
        if (self.lo | self.hi) == 0:
            self.lo, self.hi = (-7046029254386353131) & U64, 7640891576956012809 & U64
    def next_long(self):
        s0, s1 = self.lo, self.hi
        result = (rotl((s0 + s1) & U64, 17) + s0) & U64
        s1 ^= s0
        self.lo = rotl(s0, 49) ^ s1 ^ ((s1 << 21) & U64)
        self.hi = rotl(s1, 28)
        return result

def upgrade_seed_128(seed):
    lo = (seed & U64) ^ 0x6A09E667F3BCC909
    hi = (lo + 0x9E3779B97F4A7C15) & U64
    return stafford13(lo), stafford13(hi)

def md5_128(name):
    d = hashlib.md5(name.encode("utf-8")).digest()
    lo = int.from_bytes(d[0:8], "big")
    hi = int.from_bytes(d[8:16], "big")
    return lo, hi

class XoroshiroRandomSource:
    def __init__(self, lo, hi):
        self.rng = Xoroshiro128PlusPlus(lo, hi)
    def next_long(self):
        return self.rng.next_long()
    def next_int(self):
        n = self.rng.next_long() & U64
        # (int) nextLong -> lower 32 bits, as unsigned for toUnsignedLong
        return n & 0xFFFFFFFF
    def next_bits(self, bits):
        return self.rng.next_long() >> (64 - bits)
    def next_double(self):
        # nextBits(53) * 1.110223E-16F  (float constant)
        return self.next_bits(53) * float(np.float32(1.1102230246251565e-16))
    def next_int_bound(self, bound):
        assert bound > 0
        random_bits = self.next_int()
        mult = random_bits * bound
        frac = mult & 0xFFFFFFFF
        if frac < bound:
            unbiased_start = ((~bound & 0xFFFFFFFF) + 1 & 0xFFFFFFFF) % bound
            # Integer.remainderUnsigned(~bound + 1, bound) with int overflow semantics
            nb = (~bound) & 0xFFFFFFFF
            unbiased_start = (nb + 1) % bound if (nb + 1) < (1 << 32) else (nb + 1 - (1 << 32)) % bound
            while frac < unbiased_start:
                random_bits = self.next_int()
                mult = random_bits * bound
                frac = mult & 0xFFFFFFFF
        return (mult >> 32) & 0xFFFFFFFF  # (int) integerPart
    def fork_positional(self):
        lo = self.rng.next_long()
        hi = self.rng.next_long()
        return PositionalFactory(lo, hi)

class PositionalFactory:
    def __init__(self, lo, hi):
        self.seed_lo, self.seed_hi = lo & U64, hi & U64
    def from_hash_of(self, name):
        hlo, hhi = md5_128(name)
        return XoroshiroRandomSource(hlo ^ self.seed_lo, hhi ^ self.seed_hi)

# ---------------- Gradient (Perlin) noise ----------------
GRADIENT = [(1,1,0),(-1,1,0),(1,-1,0),(-1,-1,0),(1,0,1),(-1,0,1),(1,0,-1),(-1,0,-1),
            (0,1,1),(0,-1,1),(0,1,-1),(0,-1,-1),(1,1,0),(0,-1,1),(-1,1,0),(0,-1,-1)]
GRAD = np.array(GRADIENT, dtype=np.int32)

class PerlinNoise:
    def __init__(self, rs: XoroshiroRandomSource):
        self.off_x = rs.next_double() * 256.0
        self.off_y = rs.next_double() * 256.0
        self.off_z = rs.next_double() * 256.0
        perms = list(range(256))
        for i in range(256):
            off = rs.next_int_bound(256 - i)
            perms[i], perms[off + i] = perms[off + i], perms[i]
        self.perms = np.array(perms, dtype=np.int32)
    def sample(self, X, Y, Z):
        """Vectorized float32 perlin over numpy arrays (float64 in, float32 out)."""
        x = X + self.off_x
        y = Y + self.off_y
        z = Z + self.off_z
        fx = np.floor(x); fy = np.floor(y); fz = np.floor(z)
        rx = (x - fx).astype(np.float32)
        ry = (y - fy).astype(np.float32)
        rz = (z - fz).astype(np.float32)
        ix = fx.astype(np.int64); iy = fy.astype(np.int64); iz = fz.astype(np.int64)
        p = self.perms
        def perm(v):  # v int64 array
            return p[v & 0xFF].astype(np.int64)
        x0 = perm(ix); x1 = perm(ix + 1)
        xy00 = perm(x0 + iy); xy01 = perm(x0 + iy + 1)
        xy10 = perm(x1 + iy); xy11 = perm(x1 + iy + 1)
        def gdot(cell, gx, gy, gz):
            g = GRAD[p[cell & 0xFF] & 15]  # (N,3)
            return (g[:,0]*gx + g[:,1]*gy + g[:,2]*gz).astype(np.float32)
        d000 = gdot(perm(xy00 + iz), rx, ry, rz)
        d100 = gdot(perm(xy10 + iz), (rx - np.float32(1.0)), ry, rz)
        d010 = gdot(perm(xy01 + iz), rx, (ry - np.float32(1.0)), rz)
        d110 = gdot(perm(xy11 + iz), (rx - np.float32(1.0)), (ry - np.float32(1.0)), rz)
        d001 = gdot(perm(xy00 + iz + 1), rx, ry, (rz - np.float32(1.0)))
        d101 = gdot(perm(xy10 + iz + 1), (rx - np.float32(1.0)), ry, (rz - np.float32(1.0)))
        d011 = gdot(perm(xy01 + iz + 1), rx, (ry - np.float32(1.0)), (rz - np.float32(1.0)))
        d111 = gdot(perm(xy11 + iz + 1), (rx - np.float32(1.0)), (ry - np.float32(1.0)), (rz - np.float32(1.0)))
        def smooth(v): return (v*v*v*(v*(v*np.float32(6.0) - np.float32(15.0)) + np.float32(10.0))).astype(np.float32)
        ax = smooth(rx); ay = smooth(ry); az = smooth(rz)
        def lerp(a, b, t): return (a + t*(b - a)).astype(np.float32)
        def lerp2(t1, t2, a00, a10, a01, a11):
            return lerp(lerp(a00, a10, t1), lerp(a01, a11, t1), t2)
        return lerp(lerp2(ax, ay, d000, d100, d010, d110),
                    lerp2(ax, ay, d001, d101, d011, d111), az)

SECOND_FREQ = 1.0181268882175227

class NormalNoise:
    """NoiseStack of two branches; params from 26.3 JSON."""
    def __init__(self, params, factory: PositionalFactory):
        base_oct = int(params["base_octave"])
        count = int(params.get("octave_count", len(params.get("amplitude_modifiers", [1]))))
        mods = params.get("amplitude_modifiers") or [1.0]*count
        base_amp = float(params.get("base_amplitude", 1.0))
        normalize = params.get("normalize", "enabled") in (None, "enabled", True)
        freq = 2.0 ** base_oct
        amp = base_amp
        if normalize:
            amp = base_amp * (0.5 ** (-(count - 1))) / (0.5 ** (-count) - 1.0)
        octs = []
        for i in range(count):
            m = mods[i] if i < len(mods) else 1.0
            if m != 0.0:
                octs.append((base_oct + i, freq, amp * m))
            freq *= 2.0
            amp *= 0.5
        target_amp = sum(abs(a) for _, _, a in octs)
        dev = math.sqrt(sum((0.2702247831245211 * abs(a)) ** 2 for _, _, a in octs))
        norm = 0.0 if dev == 0 else (target_amp / 3.0) / (dev * math.sqrt(2.0))
        f1 = factory.fork_positional()
        f2 = factory.fork_positional()
        self.layers = []  # (perlin, frequency, amplitude_float32)
        for idx, f, a in octs:
            vf = np.float32(norm * a)
            p1 = PerlinNoise(f1.from_hash_of(f"octave_{idx}"))
            p2 = PerlinNoise(f2.from_hash_of(f"octave_{idx}"))
            self.layers.append((p1, f, vf))
            self.layers.append((p2, f * SECOND_FREQ, vf))
    def sample(self, X, Y, Z):
        val = np.zeros(X.shape, dtype=np.float32)
        for p, f, a in self.layers:
            val = (val + a * p.sample(X * f, Y * f, Z * f)).astype(np.float32)
        return val

# ---------------- Density function evaluator ----------------
PACKS = {
    "still_life": ["/tmp/n4/data/still_life"],
    "lithosphere": ["/tmp/core/overlay_26.3/data/lithosphere", "/tmp/core/data/lithosphere"],
    "minecraft_pack": ["/tmp/n4/data/minecraft"],  # pack overrides for minecraft ns
    "minecraft_vanilla": ["/home/z/my-project/mc/datagen/26.3/generated/data/minecraft"],
}
NOISE_DIRS = [
    "/tmp/n4/data/still_life/worldgen/noise",
    "/tmp/core/overlay_26.3/data/lithosphere/worldgen/noise",
    "/tmp/core/data/lithosphere/worldgen/noise",
    "/home/z/my-project/mc/datagen/26.3/generated/data/minecraft/worldgen/noise",
]
WORLD_SEED = 31337
_master_factory = None
_noise_cache = {}
_df_cache = {}
_noise_params_cache = {}

def master_factory():
    global _master_factory
    if _master_factory is None:
        lo, hi = upgrade_seed_128(WORLD_SEED & U64)
        rs = XoroshiroRandomSource(lo, hi)
        _master_factory = rs.fork_positional()
    return _master_factory

def noise_params(nid):
    if nid not in _noise_params_cache:
        path = None
        if nid.startswith("minecraft:"):
            p = os.path.join("/home/z/my-project/mc/datagen/26.3/generated/data/minecraft/worldgen/noise", nid.split(":",1)[1] + ".json")
            path = p if os.path.exists(p) else None
        else:
            ns, name = nid.split(":",1)
            for d in NOISE_DIRS:
                p = os.path.join(d, name + ".json")
                if os.path.exists(p):
                    path = p; break
        if path is None:
            raise KeyError(f"noise params not found: {nid}")
        _noise_params_cache[nid] = json.load(open(path))
    return _noise_params_cache[nid]

def get_noise(nid):
    if nid not in _noise_cache:
        _noise_cache[nid] = NormalNoise(noise_params(nid), master_factory().from_hash_of(nid))
    return _noise_cache[nid]

def load_df(ref):
    """ref: 'ns:path' density function id -> dict json"""
    if ref in _df_cache:
        return _df_cache[ref]
    ns, name = ref.split(":",1) if ":" in ref else ("minecraft", ref)
    dirs = PACKS.get(ns if ns != "minecraft" else "minecraft_pack", [])
    if ns == "minecraft":
        dirs = dirs + PACKS["minecraft_vanilla"]
    for d in dirs:
        p = os.path.join(d, "worldgen/density_function", name + ".json")
        if os.path.exists(p):
            _df_cache[ref] = json.load(open(p))
            return _df_cache[ref]
    raise KeyError(f"density function not found: {ref} (searched {dirs})")

def eval_df(node, X, Y, Z):
    """Vectorized evaluation. X,Y,Z float64 arrays."""
    if isinstance(node, str):
        return eval_df(load_df(node), X, Y, Z)
    if isinstance(node, (int, float)):
        return np.full(X.shape, np.float32(node), dtype=np.float32)
    t = node.get("type", "")
    if t == "minecraft:noise":
        n = get_noise(node["noise"])
        xs = float(node.get("xz_scale", 1)); ys = float(node.get("y_scale", 1))
        return n.sample(X * xs, Y * ys, Z * xs)
    if t == "minecraft:shifted_noise":
        n = get_noise(node["noise"])
        sh = eval_df(node["shift_xz"], X, Y, Z) if "shift_xz" in node else 0
        xs = float(node.get("xz_scale", 1)); ys = float(node.get("y_scale", 1))
        SX = X + (sh * 4.0 if "shift_xz" in node else 0)
        SZ = Z + (sh * 4.0 if "shift_xz" in node else 0)
        return n.sample(SX * xs, Y * ys, SZ * xs)
    if t in ("minecraft:add", "minecraft:min", "minecraft:max", "minecraft:mul"):
        a = eval_df(node["left"] if "left" in node else node[  "argument1"], X, Y, Z)
        b = eval_df(node["right"] if "right" in node else node.get("argument2"), X, Y, Z)
        if t == "minecraft:add": return (a + b).astype(np.float32)
        if t == "minecraft:mul": return (a * b).astype(np.float32)
        if t == "minecraft:min": return np.minimum(a, b).astype(np.float32)
        return np.maximum(a, b).astype(np.float32)
    if t == "minecraft:abs":
        return np.abs(eval_df(node.get("input", node.get("argument")), X, Y, Z)).astype(np.float32)
    if t == "minecraft:cache":
        return eval_df(node.get("input", node.get("argument")), X, Y, Z)
    if t == "minecraft:gradient":
        axis = node.get("axis", "y")
        C = {"x": X, "y": Y, "z": Z}[axis]
        f0 = float(node["from_coordinate"]); f1c = float(node["to_coordinate"])
        v0 = float(node["from_value"]); v1 = float(node["to_value"])
        tclamp = np.clip((C - f0) / (f1c - f0), 0.0, 1.0)
        return (v0 + (v1 - v0) * tclamp).astype(np.float32)
    if t == "minecraft:y_clamped_gradient":
        C = Y
        f0 = float(node["from_y"]); f1c = float(node["to_y"])
        v0 = float(node["from_value"]); v1 = float(node["to_value"])
        tclamp = np.clip((C - f0) / (f1c - f0), 0.0, 1.0)
        return (v0 + (v1 - v0) * tclamp).astype(np.float32)
    if t == "minecraft:constant":
        return np.full(X.shape, np.float32(node["value"]), dtype=np.float32)
    if t == "minecraft:clamp":
        v = eval_df(node["input"], X, Y, Z)
        lo = eval_df(node["min"], X, Y, Z).astype(np.float64)
        hi = eval_df(node["max"], X, Y, Z).astype(np.float64)
        return np.clip(v, lo, hi).astype(np.float32)
    if t == "minecraft:spline":
        return eval_spline(node["spline"], X, Y, Z)
    if t == "minecraft:range_choice":
        inp = eval_df(node["input"], X, Y, Z)
        lo = float(node["min_inclusive"]); hi = float(node["max_exclusive"])
        mask = (inp >= lo) & (inp < hi)
        out = eval_df(node["when_in_range"], X, Y, Z)
        out_o = eval_df(node["when_out_of_range"], X, Y, Z)
        return np.where(mask, out, out_o).astype(np.float32)
    raise KeyError(f"unsupported density function type: {t}")

def eval_spline(sp, X, Y, Z):
    coord = eval_df(sp["coordinate"], X, Y, Z).astype(np.float32)
    locs = np.array([float(p["location"]) for p in sp["points"]], dtype=np.float32)
    derivs = np.array([float(p.get("derivative", 0)) for p in sp["points"]], dtype=np.float32)
    vals = []
    for p in sp["points"]:
        v = p["value"]
        if isinstance(v, dict):
            vals.append(eval_spline(v, X, Y, Z))
        else:
            vals.append(np.full(X.shape, np.float32(v), dtype=np.float32))
    vals = np.stack(vals)  # (P, N)
    out = np.empty(X.shape, dtype=np.float32)
    # interval start: last i such that locs[i] <= input; use searchsorted side='right' - 1
    idx = np.searchsorted(locs, coord, side="right") - 1
    n = len(locs)
    left_mask = idx < 0
    right_mask = idx >= n - 1
    mid = ~(left_mask | right_mask)
    if left_mask.any():
        i = 0
        out[left_mask] = (vals[i][left_mask] + derivs[i] * (coord[left_mask] - locs[i])).astype(np.float32)
    if right_mask.any():
        i = n - 1
        out[right_mask] = (vals[i][right_mask] + derivs[i] * (coord[right_mask] - locs[i])).astype(np.float32)
    if mid.any():
        s = idx[mid]
        x1 = locs[s]; x2 = locs[s + 1]
        t = ((coord[mid] - x1) / (x2 - x1)).astype(np.float32)
        y1 = vals[s, np.arange(X.size)[mid]] if vals.ndim == 2 else vals[s]
        y2 = vals[s + 1, np.arange(X.size)[mid]] if vals.ndim == 2 else vals[s + 1]
        d1 = derivs[s]; d2 = derivs[s + 1]
        a = (d1 * (x2 - x1) - (y2 - y1)).astype(np.float32)
        b = (-d2 * (x2 - x1) + (y2 - y1)).astype(np.float32)
        l1 = (y1 + t * (y2 - y1)).astype(np.float32)
        l2 = (a + t * (b - a)).astype(np.float32)
        out[mid] = (l1 + t * (np.float32(1.0) - t) * l2).astype(np.float32)
    return out

# ---------------- Climate / biome matching ----------------
def load_biome_boxes(preset_path):
    d = json.load(open(preset_path))
    biomes = d["dimensions"]["minecraft:overworld"]["generator"]["biome_source"]["biomes"]
    ids, boxes = [], []  # boxes: (7,2) arrays in quantized units? keep float
    for e in biomes:
        p = e["parameters"]
        ids.append(e["biome"])
        boxes.append([
            p["temperature"], p["humidity"], p["continentalness"],
            p["erosion"], p["depth"], p["weirdness"], [p.get("offset", 0), p.get("offset", 0)],
        ])
    return ids, np.array(boxes, dtype=np.float64)

QUANT = 10000.0

def fitness(boxes, T, H, C, E, D, W):
    """boxes: (B,7,2) float; T..W: (N,) float arrays. Returns (B, N) float32 fitness in quantized units."""
    axes = [T, H, C, E, D, W]
    B = boxes.shape[0]
    out = np.zeros((B,) + T.shape, dtype=np.float32)
    for a in range(6):
        lo = (boxes[:, a, 0] * QUANT).astype(np.int64)[:, None]
        hi = (boxes[:, a, 1] * QUANT).astype(np.int64)[:, None]
        v = np.round(np.asarray(axes[a], dtype=np.float64) * QUANT).astype(np.int64)[None, :]
        gap = np.maximum(lo - v, 0) + np.maximum(v - hi, 0)
        out += (gap * gap).astype(np.float32)
    off = (boxes[:, 6, 0] * QUANT).astype(np.int64)[:, None]
    out += (off * off).astype(np.float32)
    return out

def climate_fields(X, Z, y=100.0):
    Y = np.full(X.shape, float(y))
    T = eval_df("still_life:temperature", X, Y, Z)
    H = eval_df("still_life:vegetation", X, Y, Z)
    C = eval_df("minecraft:overworld/continents", X, Y, Z)
    E = eval_df("minecraft:overworld/erosion", X, Y, Z)
    R = eval_df("minecraft:overworld/ridges", X, Y, Z)
    return T, H, C, E, R

def run_search(preset, targets, out_json):
    ids, boxes = load_biome_boxes(preset)
    ids = np.array(ids)
    print(f"boxes: {len(ids)} | targets: {targets}")
    step = 128
    xs = np.arange(-24000, 24000 + step, step, dtype=np.float64)
    zs = np.arange(-24000, 24000 + step, step, dtype=np.float64)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    Xf, Zf = X.ravel(), Z.ravel()
    N = Xf.size
    print(f"grid: {N} points")
    T, H, C, E, R = climate_fields(Xf, Zf)
    D = np.zeros_like(T)
    axes = [T, H, C, E, D, R]

    def fitness_axis(bx, A):
        """bx: (M,2) one axis of boxes; A: (N,) -> (M,N) int64 gap^2"""
        lo = np.round(bx[:, 0] * QUANT).astype(np.int64)[:, None]
        hi = np.round(bx[:, 1] * QUANT).astype(np.int64)[:, None]
        v = np.round(A[None, :] * QUANT).astype(np.int64)
        g = np.maximum(lo - v, 0) + np.maximum(v - hi, 0)
        return g * g

    # Stage 1: fitness of TARGET boxes at all points (cheap)
    tgt_idx = [i for i, b in enumerate(ids) if b in set(targets)]
    cand = np.zeros(N, dtype=bool)
    tgt_fitness = np.full(N, np.inf, dtype=np.float64)
    for i in tgt_idx:
        f = np.zeros(N, dtype=np.int64)
        for a in range(6):
            f += fitness_axis(boxes[i:i+1, a, :], axes[a])[0]
        f += int(round(boxes[i, 6, 0] * QUANT)) ** 2
        tf = f.astype(np.float64) / (QUANT * QUANT)
        tgt_fitness = np.minimum(tgt_fitness, tf)
        cand |= f < int(0.06 * QUANT * QUANT)
    print("candidate points:", int(cand.sum()))

    # Stage 2: full argmin only at candidates (+ random sample + spawn area)
    probe = cand.copy()
    rng = np.random.default_rng(7)
    sample = rng.choice(N, size=min(3000, N), replace=False)
    probe[sample] = True
    near_spawn = (np.abs(Xf) < 640) & (np.abs(Zf) < 640)
    probe |= near_spawn
    pidx = np.where(probe)[0]
    print("probe points:", pidx.size)

    B = boxes.shape[0]
    best_fit = np.full(pidx.size, np.iinfo(np.int64).max, dtype=np.int64)
    winner = np.zeros(pidx.size, dtype=np.int64)
    CH = 256
    for s in range(0, B, CH):
        e = min(s + CH, B)
        acc = np.zeros((e - s, pidx.size), dtype=np.int64)
        for a in range(6):
            acc += fitness_axis_chunk(boxes[s:e, a, :], axes[a][pidx])
        acc += (np.round(boxes[s:e, 6, 0] * QUANT).astype(np.int64)[:, None]) ** 2
        w = np.argmin(acc, axis=0)
        v = acc[w, np.arange(pidx.size)]
        upd = v < best_fit
        best_fit[upd] = v[upd]
        winner[upd] = (np.arange(s, e))[w][upd]
    win_ids = ids[winner]
    from collections import Counter
    sample_win = Counter(win_ids[np.isin(pidx, sample)].tolist())
    print("sampled-world top-20 biome shares:")
    tot = sum(sample_win.values())
    for b, c in sample_win.most_common(20):
        print(f"  {c/tot*100:5.1f}% {b}")
    spawn_win = Counter(win_ids[near_spawn[pidx]].tolist())
    print("spawn area:", spawn_win.most_common(6))
    result = {"grid_step": step, "sample_top20": sample_win.most_common(40),
              "spawn_area": spawn_win.most_common(10), "targets": {}}
    for tgt in set(targets):
        m = (win_ids == tgt) & cand[pidx]
        pts = np.stack([Xf[pidx[m]], Zf[pidx[m]]], axis=1)
        pts = sorted(pts.tolist(), key=lambda p: p[0] * p[0] + p[1] * p[1])
        result["targets"][tgt] = {"nearest_candidates": pts[:16], "probe_hits": int(m.sum())}
        print(f"{tgt}: probe hits {int(m.sum())}; nearest: {pts[:6]}")
    json.dump(result, open(out_json, "w"), indent=1)
    print("saved", out_json)

def fitness_axis_chunk(bx, A):
    """bx: (M,2), A: (N,) values -> (M,N) gap^2 int64"""
    lo = np.round(bx[:, 0] * QUANT).astype(np.int64)[:, None]
    hi = np.round(bx[:, 1] * QUANT).astype(np.int64)[:, None]
    v = np.round(A[None, :] * QUANT).astype(np.int64)
    g = np.maximum(lo - v, 0) + np.maximum(v - hi, 0)
    return g * g

if __name__ == "__main__":
    import sys
    preset = sys.argv[1] if len(sys.argv) > 1 else "/tmp/nature05/data/minecraft/worldgen/world_preset/normal.json"
    targets = sys.argv[2].split(",") if len(sys.argv) > 2 else [
        "still_life:redwood_coast", "still_life:northern_hardwood_forest", "still_life:birch_forest"]
    run_search(preset, targets, sys.argv[3] if len(sys.argv) > 3 else "/home/z/my-project/mc/results/climate_search.json")
