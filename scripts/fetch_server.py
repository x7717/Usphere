#!/usr/bin/env python3
"""Download the official Mojang server jar for the configured MC version.

Usage: fetch_server.py <dest_dir>   (env MC_VERSION, default 26.3)
"""
import json, os, sys, urllib.request

UA = {"User-Agent": "Usphere-CI/1.0"}
VERSION = os.environ.get("MC_VERSION", "26.3")
MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(dest, exist_ok=True)
    man = json.load(urllib.request.urlopen(urllib.request.Request(MANIFEST, headers=UA), timeout=60))
    vurl = next(v["url"] for v in man["versions"] if v["id"] == VERSION)
    vjson = json.load(urllib.request.urlopen(urllib.request.Request(vurl, headers=UA), timeout=60))
    url = vjson["downloads"]["server"]["url"]
    jar = os.path.join(dest, "server.jar")
    print("downloading", VERSION, "server.jar ...")
    urllib.request.urlretrieve(url, jar)
    print("ok:", jar, os.path.getsize(jar), "bytes")


if __name__ == "__main__":
    main()
