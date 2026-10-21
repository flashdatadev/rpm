"""Generate an atomic RPM repository from immutable signed packages."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET

from common import ARCHES, ROOT, manifest, run, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "dist")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty output directory; never update a live repository in place")
    output.mkdir(parents=True, exist_ok=True)
    releases = manifest()["releases"]
    inventory = []
    for arch in ARCHES:
        final = output / "stable" / arch
        metadata = final / "repodata"
        metadata.mkdir(parents=True)
        for end in range(1, len(releases) + 1):
            # Regenerate historical prefix indexes to retain immutable, hash-named metadata.
            with tempfile.TemporaryDirectory(prefix="fd-rpm-index-") as directory:
                stage = pathlib.Path(directory)
                (stage / "Packages").mkdir()
                package_paths = []
                for release in releases[:end]:
                    name = f"flashdata-{release['version']}-{release['release']}.{arch}.rpm"
                    payload = (ROOT / "packages" / name).read_bytes()
                    if sha(payload) != release["packages"][arch]:
                        raise ValueError(f"Immutable RPM checksum mismatch: {name}")
                    dest = stage / "Packages" / name
                    dest.write_bytes(payload)
                    os.utime(dest, (release["source_date_epoch"], release["source_date_epoch"]))
                    package_paths.append("Packages/" + name)
                listing = stage / "package-list.txt"
                listing.write_text("\n".join(sorted(package_paths)) + "\n")
                run(["createrepo_c", "--no-database", "--checksum", "sha256", "--compress-type", "gz", "--general-compress-type", "gz",
                     "--unique-md-filenames", "--revision", str(int(time.time())), "--pkglist", listing, stage])
                for path in (stage / "repodata").iterdir():
                    if path.name != "repomd.xml":
                        shutil.copyfile(path, metadata / path.name)
                if end == len(releases):
                    shutil.copyfile(stage / "repodata/repomd.xml", metadata / "repomd.xml")
                    shutil.copytree(stage / "Packages", final / "Packages")
        document = ET.parse(metadata / "repomd.xml")
        namespace = {"r": "http://linux.duke.edu/metadata/repo"}
        for data in document.findall("r:data", namespace):
            location = data.find("r:location", namespace).attrib["href"]
            expected = data.find("r:checksum", namespace)
            blob = (final / location).read_bytes()
            if expected.attrib["type"] != "sha256" or sha(blob) != expected.text:
                raise ValueError("Generated metadata checksum mismatch")
        for release in releases:
            inventory.append({"name": "flashdata", "version": release["version"], "release": release["release"], "architecture": arch,
                "url": f"stable/{arch}/Packages/flashdata-{release['version']}-{release['release']}.{arch}.rpm", "sha256": release["packages"][arch],
                "executableSHA256": release["executables"][arch], "sourceCommit": release["source_commit"]})
    for name in ("index.html", "flashdata.repo", ".nojekyll"):
        shutil.copyfile(ROOT / "web" / name, output / name)
    shutil.copyfile(ROOT / "keys/flashdata.asc", output / "flashdata.asc")
    shutil.copyfile(ROOT / "keys/fingerprint.txt", output / "fingerprint.txt")
    (output / "packages.json").write_text(json.dumps(inventory, indent=2) + "\n")
    lines = []
    for path in sorted(output.rglob("*.rpm")):
        lines.append(f"{sha(path.read_bytes())}  {path.relative_to(output).as_posix()}\n")
    (output / "SHA256SUMS").write_text("".join(lines))
    print(json.dumps({"output": str(output), "packages": inventory}))


if __name__ == "__main__":
    main()
