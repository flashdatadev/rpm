"""Sign RPMs and/or repository metadata with a protected CI signing subkey."""
import argparse
import datetime as dt
import os
import pathlib
import shutil
import subprocess
import tempfile

from common import ROOT, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages", type=pathlib.Path, nargs="*")
    parser.add_argument("--metadata", type=pathlib.Path)
    args = parser.parse_args()
    secret = os.environ.pop("RPM_SIGNING_PRIVATE_KEY")
    password = os.environ.pop("RPM_SIGNING_PASSPHRASE")
    fingerprint = (ROOT / "keys/fingerprint.txt").read_text().strip()
    temporary_root = pathlib.Path(tempfile.gettempdir()).resolve()
    home = pathlib.Path(tempfile.mkdtemp(prefix="fd-rpm-sign-", dir=temporary_root)).resolve()
    home.chmod(0o700)
    env = {**os.environ, "GNUPGHOME": str(home)}

    def gpg(*options, data=None):
        return run(["gpg", "--homedir", home, "--batch", "--yes", *options], input=data, env=env)

    try:
        gpg("--import", data=secret.encode())
        listing = gpg("--with-colons", "--list-keys", fingerprint).decode()
        if next(line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:")) != fingerprint:
            raise ValueError("Incorrect signing key")
        for line in listing.splitlines():
            fields = line.split(":")
            if fields[0] in ("pub", "sub") and fields[6] and int(fields[6]) < dt.datetime.now(dt.timezone.utc).timestamp() + 30 * 86400:
                raise ValueError("Signing certificate expires within 30 days; rotate it first")
        if gpg("--armor", "--export", fingerprint).replace(b"\r\n", b"\n") != (ROOT / "keys/flashdata.asc").read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError("Public certificate differs from the reviewed repository key")
        # Unlock only this isolated agent; the passphrase is supplied on stdin, never argv.
        probe = home / "unlock-probe"
        probe.write_text("FlashData RPM signing agent readiness\n")
        gpg("--pinentry-mode", "loopback", "--passphrase-fd", "0", "--local-user", fingerprint, "--digest-algo", "SHA256",
            "--output", str(home / "unlock-probe.sig"), "--detach-sign", str(probe), data=(password + "\n").encode())
        for folder in args.packages or []:
            for package in sorted(folder.glob("*.rpm")):
                run(["rpmsign", "--define", f"_gpg_name {fingerprint}", "--define", f"_gpg_path {home}", "--define", "_gpg_digest_algo sha256",
                     "--define", "_gpg_sign_cmd_extra_args --batch --pinentry-mode loopback", "--addsign", package], input=b"", env=env, timeout=90)
                print(f"Signed RPM: {package.name}")
        if args.metadata:
            for metadata in sorted(args.metadata.glob("stable/*/repodata/repomd.xml")):
                gpg("--pinentry-mode", "loopback", "--passphrase-fd", "0", "--local-user", fingerprint, "--digest-algo", "SHA256", "--armor",
                    "--output", str(metadata) + ".asc", "--detach-sign", str(metadata), data=(password + "\n").encode())
                gpg("--verify", str(metadata) + ".asc", str(metadata))
                print(f"Signed repository metadata: {metadata.parent.parent.name}")
    finally:
        subprocess.run(["gpgconf", "--homedir", str(home), "--kill", "all"], capture_output=True)
        if home.parent != temporary_root or not home.name.startswith("fd-rpm-sign-"):
            raise RuntimeError("Refusing cleanup outside the generated keyring")
        shutil.rmtree(home)


if __name__ == "__main__":
    main()
