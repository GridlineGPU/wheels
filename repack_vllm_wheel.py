"""GRI-696: the Inkling 2 Mini vLLM wheel, rebuilt byte for byte from what the upstream image installed.

vllm/vllm-openai@sha256:a485440c… installs vllm-0.1.dev25855+g7cb5dae22.cu130 from a wheel built in the same
Docker build and never published. This takes the image's one layer that installed it, keeps exactly the files
the wheel's own RECORD lists under vllm/ and its .dist-info (dropping what the installer added: INSTALLER,
REQUESTED, direct_url.json, bytecode, scripts outside the package), checks every kept file's sha256 and size
against RECORD, and writes the wheel with that RECORD, fixed timestamps and sorted entries (dist-info last), so
the same layer always gives the same bytes.

    python3 -I repack_vllm_wheel.py --work <empty dir> --out <dir>

Prints the wheel's name, sha256 and size. Downloads ~175 MB (one layer) from Docker Hub, anonymously.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import os
import stat
import tarfile
import urllib.error
import urllib.request
import zipfile

IMAGE = "vllm/vllm-openai"
DIGEST = "sha256:a485440c62099c39659a7b723636073ed726dcb41f94cf6326e16af3a1d6f6bc"
SITE = "usr/local/lib/python3.14/dist-packages/"
DIST = "vllm-0.1.dev25855+g7cb5dae22.cu130.dist-info"
WHEEL = "vllm-0.1.dev25855+g7cb5dae22.cu130-cp38-abi3-linux_x86_64.whl"
INSTALLER_FILES = {"INSTALLER", "REQUESTED", "direct_url.json", "uv_cache.json", "uv_build.json"}
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
LAYER = "sha256:7dd4c79b3181"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def hub(path, token, accept=None):
    headers = {"Authorization": f"Bearer {token}"}
    if accept:
        headers["Accept"] = accept
    try:
        return urllib.request.build_opener(NoRedirect).open(urllib.request.Request(
            f"https://registry-1.docker.io/v2/{IMAGE}/{path}", headers=headers), timeout=600)
    except urllib.error.HTTPError as error:
        if error.code in (301, 302, 307, 308):  # the blob's CDN, without the registry token
            return urllib.request.urlopen(error.headers["Location"], timeout=1800)
        raise


def record_hash(data):
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    token = json.load(urllib.request.urlopen(
        f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{IMAGE}:pull", timeout=60))["token"]
    manifest = json.load(hub(f"manifests/{DIGEST}", token, "application/vnd.docker.distribution.manifest.v2+json"))
    # The one layer that installed the wheel (found on the 2026-11-21 probe pods: 11,645 vllm files).
    layer = next(layer for layer in manifest["layers"] if layer["digest"].startswith(LAYER))
    blob = os.path.join(args.work, "layer.tar.gz")
    digest = hashlib.sha256()
    with hub(f"blobs/{layer['digest']}", token) as stream, open(blob, "wb") as handle:
        while chunk := stream.read(8 << 20):
            digest.update(chunk)
            handle.write(chunk)
    assert "sha256:" + digest.hexdigest() == layer["digest"], "layer digest mismatch"

    files = {}
    with tarfile.open(blob, "r:gz") as tar:
        for member in tar:
            if member.isfile() and member.name.startswith(SITE):
                rel = member.name[len(SITE):]
                if rel.startswith(("vllm/", DIST + "/")):
                    files[rel] = (tar.extractfile(member).read(), member.mode)
    record = list(csv.reader(io.StringIO(files[f"{DIST}/RECORD"][0].decode())))
    kept, dropped = [], []
    for row in record:
        path, hashed, size = row[0], row[1], row[2]
        name = path.rsplit("/", 1)[-1]
        if (not path.startswith(("vllm/", DIST + "/")) or "/__pycache__/" in path or path.endswith(".pyc")
                or (path.startswith(DIST + "/") and name in INSTALLER_FILES)):
            dropped.append(path)
            continue
        if path == f"{DIST}/RECORD":
            continue
        data, _ = files[path]
        assert record_hash(data) == hashed and str(len(data)) == size, f"RECORD mismatch: {path}"
        kept.append(row)
    listed = {row[0] for row in kept} | {f"{DIST}/RECORD"}
    stray = sorted(p for p in files if p not in listed and "/__pycache__/" not in p
                   and p.rsplit("/", 1)[-1] not in INSTALLER_FILES)
    assert not stray, f"files not in RECORD: {stray[:5]}"

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    order = sorted(kept, key=lambda row: (row[0].startswith(DIST + "/"), row[0]))
    for row in order:
        writer.writerow(row[:3])
    writer.writerow([f"{DIST}/RECORD", "", ""])
    path = os.path.join(args.out, WHEEL)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in order:
            data, mode = files[row[0]]
            info = zipfile.ZipInfo(row[0], ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((stat.S_IFREG | (0o755 if mode & 0o111 else 0o644)) << 16)
            archive.writestr(info, data)
        info = zipfile.ZipInfo(f"{DIST}/RECORD", ZIP_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        archive.writestr(info, out.getvalue().encode())
    whl = open(path, "rb").read()
    print(json.dumps({"wheel": WHEEL, "sha256": hashlib.sha256(whl).hexdigest(), "bytes": len(whl),
                      "files": len(order) + 1, "dropped": dropped, "layer": layer["digest"],
                      "image": f"{IMAGE}@{DIGEST}"}, indent=1))


if __name__ == "__main__":
    main()
