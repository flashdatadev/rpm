"""Use native rpmbuild to package pinned upstream binaries without altering them."""
import argparse
import datetime as dt
import io
import json
import os
import pathlib
import shutil
import tarfile
import tempfile

from common import ARCHES, ROOT, gz, manifest, run, sha, upstream


def payload(release, arch, files):
    doc = "usr/share/doc/flashdata/"
    entries = {"usr/bin/flashdata": (files["flashdata"], 0o755)}
    for name, content in files.items():
        if name not in ("flashdata", "LICENSE", "release-files.json") and not name.startswith("licenses/"):
            entries[doc + name] = (content, 0o644)
        elif name == "LICENSE" or name.startswith("licenses/"):
            entries["usr/share/licenses/flashdata/" + name] = (content, 0o644)
    provenance = {"version": release["version"], "release": release["release"], "source_commit": release["source_commit"], "architecture": arch,
                  "archive_sha256": release["archives"][arch], "executable_sha256": release["executables"][arch]}
    entries[doc + "build-info.json"] = ((json.dumps(provenance, indent=2) + "\n").encode(), 0o644)
    man = f'''.TH FLASHDATA 1 "2026-10" "FlashData {release['version']}" "User Commands"
.SH NAME
flashdata \\- Google Search, YouTube data and bulk workflows
.SH SYNOPSIS
.B flashdata
[command] [flags]
.SH DESCRIPTION
Standalone FlashData API client with secure profiles, background jobs, bulk exports and run recovery.
.SH COMMANDS
.TP
.B auth login
Import an API key using hidden terminal input. Obtain a key at https://flashdata.dev.
.TP
.B search QUERY
Run a Google search. Normal FlashData billing applies.
.TP
.B query --input FILE
Run a Data API JSON request.
.TP
.B bulk
Create, upload, control and export bulk tasks.
.TP
.B runs
Inspect or recover durable local runs.
.SH OPTIONS
.TP
.B --help
Show help. Use COMMAND --help for command-specific flags.
.TP
.B --version
Show the upstream version and source commit offline.
.TP
.B --json
Write a versioned JSON envelope.
.SH FILES
Examples and English/Chinese release docs: /usr/share/doc/flashdata/.
License notices: /usr/share/licenses/flashdata/.
Package removal preserves per-user credentials and run history.
.SH SEE ALSO
https://flashdata.dev/docs
.br
https://github.com/flashdatadev/flashdata-cli
'''
    entries["usr/share/man/man1/flashdata.1.gz"] = (gz(man.encode()), 0o644)
    output = io.BytesIO()
    epoch = release["source_date_epoch"]
    directories = {str(p) for name in entries for p in pathlib.PurePosixPath(name).parents if str(p) != "."}
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(directories):
            info = tarfile.TarInfo(name + "/")
            info.type, info.mode = tarfile.DIRTYPE, 0o755
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mtime = epoch
            archive.addfile(info)
        for name, (data, mode) in sorted(entries.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), mode, epoch
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            archive.addfile(info, io.BytesIO(data))
    return gz(output.getvalue())


def build(release, arch, files, destination):
    with tempfile.TemporaryDirectory(prefix="fd-rpmbuild-") as folder:
        top = pathlib.Path(folder)
        for name in ("SOURCES", "SPECS", "BUILD", "RPMS", "SRPMS", "BUILDROOT"):
            (top / name).mkdir()
        (top / "SOURCES/payload.tar.gz").write_bytes(payload(release, arch, files))
        date = dt.datetime.fromtimestamp(release["source_date_epoch"], dt.timezone.utc).strftime("%a %b %d %Y")
        spec = f'''%global debug_package %{{nil}}
%global _build_id_links none
%global __os_install_post %{{nil}}
%global _binary_payload w9.gzdio
%global _binary_filedigest_algorithm 8
%global _source_filedigest_algorithm 8
Name: flashdata
Version: {release['version']}
Release: {release['release']}
Summary: FlashData search, YouTube data and bulk workflows
License: MIT
URL: https://flashdata.dev
Packager: FlashData <support@flashdata.dev>
Vendor: FlashData
Source0: payload.tar.gz
BuildArch: {arch}
AutoReqProv: no
Requires: ca-certificates

%description
Standalone API client with secure profiles, background jobs, bulk exports and durable
run recovery. API use requires a FlashData key; offline version/help checks do not.

%prep
%setup -q -c

%build
# The verified upstream executable is already built and remains byte-for-byte unchanged.

%install
mkdir -p %{{buildroot}}
cp -a usr %{{buildroot}}/

%files
%attr(0755,root,root) /usr/bin/flashdata
%doc /usr/share/doc/flashdata
%license /usr/share/licenses/flashdata
/usr/share/man/man1/flashdata.1.gz

%changelog
* {date} FlashData <support@flashdata.dev> - {release['version']}-{release['release']}
- Package the verified upstream executable with docs, examples and license notices.
'''
        path = top / "SPECS/flashdata.spec"
        path.write_text(spec)
        env = {**os.environ, "SOURCE_DATE_EPOCH": str(release["source_date_epoch"]), "TZ": "UTC", "LC_ALL": "C.UTF-8"}
        run(["rpmbuild", "-bb", "--target", arch, "--define", f"_topdir {top}", "--define", "_buildhost build.flashdata.dev",
             "--define", "use_source_date_epoch_as_buildtime 1", "--define", "clamp_mtime_to_source_date_epoch 1", path], env=env)
        name = f"flashdata-{release['version']}-{release['release']}.{arch}.rpm"
        source = top / "RPMS" / arch / name
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination / name)
        return name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "unsigned/packages")
    parser.add_argument("--fixtures", type=pathlib.Path, default=ROOT / "unsigned/fixtures")
    args = parser.parse_args()
    if not shutil.which("rpmbuild"):
        raise RuntimeError("Native Linux rpmbuild is required; use the bootstrap workflow")
    report = {"rpmToolchain": run(["rpm", "--version"]).decode().strip(), "packages": []}
    for release in manifest()["releases"]:
        for arch in ARCHES:
            files = upstream(release, arch)
            name = build(release, arch, files, args.output)
            fixture = build({**release, "release": "0.upgradetest"}, arch, files, args.fixtures)
            report["packages"].append({"file": name, "architecture": arch, "unsignedSHA256": sha((args.output / name).read_bytes()), "fixture": fixture,
                                       "executableSHA256": release["executables"][arch], "sourceCommit": release["source_commit"]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    (args.output.parent / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
