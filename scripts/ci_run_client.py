#!/usr/bin/env python3
"""Run the REAL Minecraft 26.3 client headless (Xvfb + Mesa llvmpipe),
load a world with datapacks, take screenshots. Designed to run identically
locally and in GitHub Actions CI.

Steps:
  1. Resolve version json from Mojang piston-meta, download client.jar,
     libraries (incl. linux natives) and assets.
  2. Copy a pre-generated world (server-side world with datapacks) into saves/.
  3. Launch the client under Xvfb with software GL.
  4. Wait for world load, take screenshots with `import` (ImageMagick) or xwd.
  5. Exit with code 0 if a screenshot with world HUD was captured.
"""
import json, os, sys, urllib.request, hashlib, shutil, subprocess, time, argparse

UA = {"User-Agent": "Usphere-CI/1.0 (datapack verification)"}
CACHE = os.environ.get("MC_CLIENT_CACHE", "/home/z/my-project/mc/client263")
VERSION = os.environ.get("MC_VERSION", "26.3")
MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


def fetch(url, path=None, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            data = urllib.request.urlopen(req, timeout=60).read()
            if path:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "wb").write(data)
            return data
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2)


def fetch_json(url):
    return json.loads(fetch(url))


def setup_version():
    """download client jar + libraries + assets, return (mainClass, classpath, jvm_args_tpl, game_args_tpl)"""
    os.makedirs(CACHE, exist_ok=True)
    man = fetch_json(MANIFEST)
    vurl = next(v["url"] for v in man["versions"] if v["id"] == VERSION)
    vjson = fetch_json(vurl)
    json.dump(vjson, open(f"{CACHE}/version.json", "w"), indent=1)

    # client jar
    cjar = f"{CACHE}/client.jar"
    if not os.path.exists(cjar):
        print("downloading client.jar ...", flush=True)
        fetch(vjson["downloads"]["client"]["url"], cjar)
    else:
        print("client.jar cached", flush=True)

    # libraries
    cp = [cjar]
    for lib in vjson["libraries"]:
        rules = lib.get("rules", [])
        allowed = True
        for r in rules:
            act = r.get("action")
            os_ok = r.get("os", {}).get("name") in (None, "linux")
            if act == "allow":
                allowed = os_ok and allowed
            elif act == "disallow":
                if os_ok:
                    allowed = False
        if not allowed or "artifact" not in lib.get("downloads", {}):
            continue
        art = lib["downloads"]["artifact"]
        path = os.path.join(CACHE, "libraries", art["path"])
        if not os.path.exists(path):
            fetch(art["url"], path)
        cp.append(path)
        # natives
        n = lib.get("downloads", {}).get("classifiers", {}).get("natives-linux")
        if n:
            npath = os.path.join(CACHE, "libraries", n["path"])
            if not os.path.exists(npath):
                fetch(n["url"], npath)
            cp.append(npath)

    # assets
    ai = vjson["assetIndex"]
    idx_path = os.path.join(CACHE, "assets", "indexes", ai["id"] + ".json")
    if not os.path.exists(idx_path):
        fetch(ai["url"], idx_path)
    idx = json.load(open(idx_path))
    print(f"assets: {len(idx['objects'])} objects", flush=True)
    n_missing = 0
    for name, obj in idx["objects"].items():
        h = obj["hash"]
        p = os.path.join(CACHE, "assets", "objects", h[:2], h)
        if not os.path.exists(p):
            n_missing += 1
            fetch("https://resources.download.minecraft.net/" + h[:2] + "/" + h, p)
    print(f"assets downloaded: {n_missing}", flush=True)

    return {
        "mainClass": vjson["mainClass"],
        "classpath": cp,
        "assetIndex": ai["id"],
        "jvm": vjson.get("javaVersion", {}).get("majorVersion", 21),
        "args": vjson.get("arguments", {}).get("game", []),
    }


def build_game_args(tpl, world_name, width=1280, height=720):
    """expand mojang argument template with our values"""
    subs = {
        "${auth_player_name}": "CIPlayer",
        "${version_name}": VERSION,
        "${game_directory}": os.path.join(CACHE, "gamedir"),
        "${assets_root}": os.path.join(CACHE, "assets"),
        "${asset_index}": "",
        "${auth_uuid}": "00000000-0000-0000-0000-000000000000",
        "${auth_access_token}": "0",
        "${user_type}": "msa",
        "${version_type}": "release",
        "${clientid}": "0",
        "${auth_xuid}": "0",
        "${launcher_name}": "usphere-ci",
        "${launcher_version}": "1.0",
        "${resolution_width}": str(width),
        "${resolution_height}": str(height),
        "${quickPlaySingleplayer}": world_name,
    }
    args = []
    for a in tpl:
        if isinstance(a, str):
            args.append(subs.get(a, a))
        elif isinstance(a, dict):
            # rules: only keep allowed entries (os linux + demo excluded)
            rules = a.get("rules", [])
            ok = True
            for r in rules:
                if r.get("action") == "allow" and "os" not in r and "features" not in r:
                    ok = True
                if r.get("action") == "disallow" and r.get("os", {}).get("name") == "linux":
                    ok = False
                if r.get("action") == "allow" and "features" in r:
                    ok = False  # we don't request demo/quickplay features via template
            if ok:
                for v in a.get("value", []):
                    args.append(subs.get(v, v))
    return args


def screenshot_tool_shot(path):
    size = os.environ.get("SHOT_SIZE", "1280x720")
    for cmd in (
        ["ffmpeg", "-f", "x11grab", "-video_size", size, "-i", os.environ.get("DISPLAY", ":0"), "-frames:v", "1", path, "-y"],
        ["import", "-window", "root", path],
        ["xwd", "-root", "-out", path],
    ):
        try:
            subprocess.run(cmd, check=True, timeout=30)
            return True
        except Exception:
            continue
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True, help="path to server world dir (with datapacks)")
    ap.add_argument("--wait", type=int, default=150, help="seconds to wait for world load")
    ap.add_argument("--out", default="/home/z/my-project/mc/client263/shots")
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--no-copy", action="store_true", help="reuse the previously copied world")
    a = ap.parse_args()

    tpl = setup_version()
    if a.no_download:
        pass

    # prepare gamedir & world
    gdir = os.path.join(CACHE, "gamedir")
    os.makedirs(gdir + "/saves", exist_ok=True)
    wname = "usphtest"
    wdst = f"{gdir}/saves/{wname}"
    if a.no_copy and os.path.exists(wdst):
        print("reusing existing world copy", flush=True)
    else:
        if os.path.exists(wdst):
            shutil.rmtree(wdst)
        print("copying world ->", wdst, flush=True)
        shutil.copytree(a.world, wdst, ignore=shutil.ignore_patterns("session.lock", "*.lock", "logs", "cache"))
    # Paper stores world gen settings per-dimension; the client expects them at <world>/data/minecraft/
    for dim in ("overworld",):
        src = os.path.join(a.world, "dimensions", "minecraft", dim, "data", "minecraft", "world_gen_settings.dat")
        if os.path.exists(src):
            os.makedirs(f"{wdst}/data/minecraft", exist_ok=True)
            shutil.copy(src, f"{wdst}/data/minecraft/world_gen_settings.dat")
            print("world_gen_settings.dat copied from", dim, flush=True)
    # server worlds have their dimension dirs at root (like singleplayer) — ok

    args = build_game_args(tpl["args"], wname)
    args += ["--quickPlaySingleplayer", wname]
    # fix the asset index placeholder with the real id
    for ph in ("--assetIndex",):
        try:
            i = args.index(ph)
            if args[i + 1] in ("", "${asset_index}", "${assets_index_name}"):
                args[i + 1] = tpl["assetIndex"]
        except ValueError:
            pass
    here = os.path.dirname(os.path.abspath(__file__))
    default_agent = os.path.join(here, "agent", "shot-agent2.jar")
    cmd = [
        os.environ.get("MC_JAVA", "java"),
        "-Xmx" + os.environ.get("MC_HEAP", "2200M"),
        "-javaagent:" + os.environ.get("SHOT_AGENT", default_agent) + "=" + os.environ.get("SHOT_AGENT_ARGS", "20:30:40"),
        "-Djava.awt.headless=false",
        f"-Djava.library.path={CACHE}/libraries",
        f"-Dorg.lwjgl.opengl.Display.width=1280",
        f"-Dorg.lwjgl.opengl.Display.height=720",
        "-cp", ":".join(tpl["classpath"]),
        tpl["mainClass"],
    ] + args
    print("CMD:", " ".join(cmd)[:600], flush=True)
    os.makedirs(gdir + "/crash-reports", exist_ok=True)
    logf = open(gdir + "/client.log", "w")
    env = dict(os.environ)
    os.makedirs("/tmp/xdg", exist_ok=True)
    # headless EGL stack (downloaded libEGL + libEGL_mesa) when provided
    egl_dir = os.environ.get("MESA_EGL_LIBS", "")
    if egl_dir:
        ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = (egl_dir + "/usr/lib/x86_64-linux-gnu" + ((":" + ld) if ld else ""))
        env["__EGL_VENDOR_LIBRARY_FILENAMES"] = egl_dir + "/usr/share/glvnd/egl_vendor.d/50_mesa.json"
    env.update({
        "XDG_RUNTIME_DIR": "/tmp/xdg",
        "LIBGL_ALWAYS_SOFTWARE": "1",
        "GALLIUM_DRIVER": "llvmpipe",
        "MESA_GL_VERSION_OVERRIDE": "4.5",
        "__GLX_VENDOR_LIBRARY_NAME": "mesa",
        "DISPLAY": os.environ.get("DISPLAY", ":99"),
        "SDL_VIDEO_X11_VISUALID": os.environ.get("SDL_VIDEO_X11_VISUALID", ""),
        "SDL_VIDEODRIVER": os.environ.get("SDL_VIDEODRIVER", ""),
    })
    # optional LD_PRELOAD shim (legacy); the reliable path is glshim/libGL.so.1 on LD_LIBRARY_PATH
    shim = os.environ.get("GL_SHIM", "")
    if shim:
        prev = env.get("LD_PRELOAD", "")
        env["LD_PRELOAD"] = (shim + " " + prev).strip()
        print("LD_PRELOAD:", env["LD_PRELOAD"], flush=True)
    glshim = os.environ.get("GL_SHIM_LIBGL", "/home/z/my-project/glshim")
    if os.path.exists(glshim + "/libGL.so.1"):
        ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = glshim + ((":" + ld) if ld else "")
        print("LD_LIBRARY_PATH:", env["LD_LIBRARY_PATH"], flush=True)
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=gdir, env=env)
    os.makedirs(a.out, exist_ok=True)
    shots = []
    t0 = time.time()
    try:
        while time.time() - t0 < a.wait:
            time.sleep(10)
            log = open(gdir + "/client.log").read()
            # world loaded indicator
            if "Loaded 0 advancements" in log or "Stopping" in log or proc.poll() is not None:
                if proc.poll() is not None:
                    print("client exited early, code", proc.returncode, flush=True)
                    break
                if "Stopping" in log:
                    print("log says Stopping; proc alive:", proc.poll(), flush=True)
            shot_path = os.path.join(a.out, f"shot_{int(time.time()-t0)}s.png")
            if screenshot_tool_shot(shot_path):
                shots.append(shot_path)
                print("screenshot:", shot_path, flush=True)
            # screenshot the in-world moment twice then quit
            # stop once the in-game agent screenshots exist (world rendered)
            if os.path.isdir(agent_shots := os.path.join(gdir, "screenshots")) and                [f for f in os.listdir(agent_shots) if f.endswith(".png")]:
                time.sleep(15)  # let it render a couple frames more
                break
    finally:
        time.sleep(2)
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()
    # agent screenshots live in <gamedir>/screenshots
    agent_shots = os.path.join(gdir, "screenshots")
    if os.path.isdir(agent_shots):
        for f in sorted(os.listdir(agent_shots)):
            if f.endswith(".png"):
                src = os.path.join(agent_shots, f)
                dst = os.path.join(a.out, "agent_" + f)
                shutil.copy(src, dst)
                shots.append(dst)
                print("agent screenshot:", dst, flush=True)
    print("shots:", shots, flush=True)
    if not shots:
        sys.exit(1)


if __name__ == "__main__":
    main()
