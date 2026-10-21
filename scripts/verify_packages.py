"""Native RPM signature, package metadata, ownership and executable verification."""
import argparse
import json
import pathlib
import tempfile

from common import ARCHES, ROOT, manifest, run, sha


def verify(package, release, arch, database, check_hash=True):
    signatures = run(["rpmkeys", "--dbpath", database, "--checksig", "--verbose", package]).decode()
    if "Signature" not in signatures or "OK" not in signatures or any(word in signatures for word in ("NOKEY", "NOT OK", "BAD")):
        raise ValueError(f"Signature was not verified: {package.name}: {signatures}")
    metadata = run(["rpm", "--dbpath", database, "-qp", "--qf", "%{NAME} %{VERSION} %{RELEASE} %{ARCH}", package]).decode()
    if metadata != f"flashdata {release['version']} {release['release']} {arch}":
        raise ValueError(f"Unexpected RPM metadata: {metadata}")
    if run(["rpm", "--dbpath", database, "-qp", "--scripts", package]).strip():
        raise ValueError("Packages must not contain maintainer scripts")
    owners = run(["rpm", "--dbpath", database, "-qp", "--qf", "[%{FILENAMES}\t%{FILEMODES}\t%{FILEUSERNAME}\t%{FILEGROUPNAME}\n]", package]).decode()
    for line in owners.splitlines():
        name, mode, user, group = line.split("\t")
        if not name.startswith("/usr/") or int(mode) & 0o7022 or user != "root" or group != "root":
            raise ValueError(f"Unexpected payload ownership/mode: {line}")
    cpio = run(["rpm2cpio", package])
    binary = run(["cpio", "--extract", "--to-stdout", "./usr/bin/flashdata"], input=cpio)
    if sha(binary) != release["executables"][arch]:
        raise ValueError("Packaged executable is not the exact upstream release")
    if check_hash and sha(package.read_bytes()) != release["packages"][arch]:
        raise ValueError("Signed package checksum differs from manifest")
    return {"file": package.name, "sha256": sha(package.read_bytes()), "executableSHA256": sha(binary), "signatureVerified": True, "architecture": arch}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages", type=pathlib.Path, default=ROOT / "packages")
    parser.add_argument("--fixtures", type=pathlib.Path)
    parser.add_argument("--bootstrap", action="store_true")
    args = parser.parse_args()
    records = []
    with tempfile.TemporaryDirectory(prefix="fd-rpm-db-") as directory:
        database = pathlib.Path(directory)
        run(["rpm", "--dbpath", database, "--initdb"])
        run(["rpm", "--dbpath", database, "--import", ROOT / "keys/flashdata.asc"])
        for release in manifest()["releases"]:
            for arch in ARCHES:
                name = f"flashdata-{release['version']}-{release['release']}.{arch}.rpm"
                records.append(verify(args.packages / name, release, arch, database, not args.bootstrap))
                if args.fixtures:
                    old = {**release, "release": "0.upgradetest"}
                    old_name = f"flashdata-{old['version']}-{old['release']}.{arch}.rpm"
                    verify(args.fixtures / old_name, old, arch, database, False)
    report = {"fingerprint": (ROOT / "keys/fingerprint.txt").read_text().strip(), "packages": records}
    print(json.dumps(report))
    (args.packages.parent / "verification.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
