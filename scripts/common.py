import gzip
import hashlib
import io
import json
import pathlib
import struct
import subprocess
import tarfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
ARCHES = {"x86_64": "amd64", "aarch64": "arm64"}


def manifest():
    return json.loads((ROOT / "manifest.json").read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(args, **kwargs):
    result = subprocess.run([str(a) for a in args], capture_output=True, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace") + result.stdout.decode(errors="replace"))
    return result.stdout


def gz(data):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as stream:
        stream.write(data)
    return output.getvalue()


def upstream(release, arch):
    name = f"flashdata_{release['version']}_linux_{ARCHES[arch]}.tar.gz"
    cache = ROOT / ".cache" / name
    if not cache.exists():
        cache.parent.mkdir(exist_ok=True)
        url = f"https://github.com/flashdatadev/flashdata-cli/releases/download/v{release['version']}/{name}"
        with urllib.request.urlopen(url, timeout=90) as response:
            cache.write_bytes(response.read())
    payload = cache.read_bytes()
    if sha(payload) != release["archives"][arch]:
        raise ValueError(f"Upstream archive checksum mismatch: {name}")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            path = pathlib.PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or member.name in files:
                raise ValueError(f"Unexpected upstream archive member: {member.name}")
            files[member.name] = archive.extractfile(member).read()
    binary = files["flashdata"]
    if sha(binary) != release["executables"][arch]:
        raise ValueError("The upstream executable has changed")
    if binary[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", binary, 18)[0] != {"x86_64": 62, "aarch64": 183}[arch]:
        raise ValueError("Wrong executable architecture")
    return files
