# FlashData RPM repository

English | [简体中文](README.zh-CN.md)

The official signed RPM repository for [FlashData CLI](https://github.com/flashdatadev/flashdata-cli). [FlashData](https://flashdata.dev) provides structured web data through APIs; the CLI supports account onboarding, queries, bulk downloads and resumable runs. The packages contain the official standalone executable and require no Go, Python or Node.js runtime.

Supports Fedora 43/44 and RHEL 8/9/10 userspace on **x86_64 and aarch64**. CI tests Fedora containers and Red Hat's public UBI 8/9/10 containers on matching native CPUs. UBI tests cover RHEL userspace; full RHEL host configurations, subscription repositories, SELinux policy changes and FIPS mode have not been separately certified.

## Install

Run this once on a supported DNF-based system with sudo access. It verifies the downloaded signing certificate's full fingerprint before trusting it, enables both package and repository metadata signature checks, and installs `flashdata`.

```bash
(
  set -eu
  case "$(rpm --eval '%{_arch}')" in
    x86_64|aarch64) ;;
    *) echo 'Supported RPM architectures: x86_64, aarch64' >&2; exit 1 ;;
  esac
  sudo dnf install -y ca-certificates gnupg2
  if ! command -v curl >/dev/null 2>&1; then sudo dnf install -y curl; fi
  work_dir="$(mktemp -d)"
  trap 'rm -rf -- "$work_dir"' EXIT
  curl -fsSL https://flashdatadev.github.io/rpm/flashdata.asc -o "$work_dir/flashdata.asc"
  expected=23AB58683E85FE7236D369713D19EA52D181CC36
  actual="$(gpg --batch --show-keys --with-colons "$work_dir/flashdata.asc" 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')"
  test "$actual" = "$expected" || { echo 'FlashData RPM key fingerprint mismatch' >&2; exit 1; }
  sudo install -d -m 0755 /etc/pki/rpm-gpg
  sudo install -m 0644 "$work_dir/flashdata.asc" /etc/pki/rpm-gpg/RPM-GPG-KEY-flashdata
  sudo rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-flashdata
  sudo tee /etc/yum.repos.d/flashdata.repo >/dev/null <<'EOF'
[flashdata]
name=FlashData CLI stable
baseurl=https://flashdatadev.github.io/rpm/stable/$basearch/
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-flashdata
sslverify=1
includepkgs=flashdata
metadata_expire=6h
skip_if_unavailable=0
EOF
  sudo dnf -y --refresh install flashdata
  flashdata --version
  flashdata --help
)
```

You may see a second key import for metadata verification: DNF keeps its repository metadata keyring separately from RPM's package keyring. Both use the same fingerprint-verified local certificate. Compare the fingerprint independently with [the public key in this repository](keys/fingerprint.txt).

After installation, set up your agent:

```bash
flashdata setup
```

Setup selects Codex, Claude Code or Cursor, installs bundled skills and verifies access without a paid query. Content queries in skills use plain text by default; bulk exports stay JSONL. CLI v1.2.1 bundles bulk guides for the main skill and five YouTube skills. Rerun `flashdata setup` after upgrading to refresh unmodified skills; MCP is optional. To use an existing key, run `flashdata auth login` before setup. For the uv installation option, see the [CLI setup guide](https://github.com/flashdatadev/flashdata-cli#readme).

Installation and the offline checks above need no API key. If a previous manual or Homebrew installation exists, check `command -v flashdata`; RPM installs `/usr/bin/flashdata`, which another entry earlier in `PATH` can shadow. Avoid managing the same executable with multiple package managers.

## Upgrade and remove

```bash
sudo dnf --refresh upgrade flashdata
rpm -q flashdata
/usr/bin/flashdata --version
```

```bash
sudo dnf remove flashdata
```

Uninstalling preserves your profiles, credentials and run history. No package scripts modify user state. To stop using the repository, remove `/etc/yum.repos.d/flashdata.repo`; you can also remove its local certificate file. An imported RPM certificate remains in the system RPM key database until an administrator explicitly removes it after checking other uses.

## Packages and trust

- Stable endpoint: [flashdatadev.github.io/rpm](https://flashdatadev.github.io/rpm/); [repository configuration](https://flashdatadev.github.io/rpm/flashdata.repo), [public certificate](https://flashdatadev.github.io/rpm/flashdata.asc), [package inventory](https://flashdatadev.github.io/rpm/packages.json).
- CLI **1.2.1**, RPM version/release **1.2.1-1**, package name **flashdata**. Both architectures contain the byte-identical executable from the [official v1.2.1 release](https://github.com/flashdatadev/flashdata-cli/releases/tag/v1.2.1), with documentation, examples, a man page and third-party licenses.
- Dedicated RSA-4096 RPM signing certificate: `23AB58683E85FE7236D369713D19EA52D181CC36`, identity `FlashData RPM Signing <support@flashdata.dev>`. Individual RPMs and `repomd.xml` are signed with SHA-256. This certificate is separate from the APT certificate.
- `gpgcheck=1`, `repo_gpgcheck=1` and HTTPS verification remain enabled. `includepkgs=flashdata` limits what this repository supplies. RPM package certificates are imported into the system-wide RPM trust database; they are not scoped to one repository. DNF's metadata keyrings are per repository.
- Package bytes and SHA-256 values are pinned in [manifest.json](manifest.json). Existing package versions are never rebuilt or re-signed in place. Updated metadata is published only after candidate installation, upgrade and rejection tests pass. Old packages and hash-named indexes are retained.
- `metadata_expire=6h` controls DNF cache freshness, not a cryptographic expiry guarantee. RPM repository metadata has no APT-style `Valid-Until`. The signing certificate expires after two years; signing refuses certificates within 30 days of expiry. Maintainers must rotate before expiry. Weekly runs refresh metadata and repeat the full checks.

See [CI results](https://github.com/flashdatadev/rpm/actions/workflows/publish.yml), [maintenance and recovery](docs/maintaining.md) and [security reporting](SECURITY.md). Every candidate/public container upgrades the actual signed **1.2.0-1** package to **1.2.1-1**, verifies the installed executable hash and preserves user state. Tests also check a signed **1.2.1-0.upgradetest** packaging fixture, which is never publicly indexed. The original signed 1.0.0 packages remain available unchanged.

Support: [support@flashdata.dev](mailto:support@flashdata.dev) · [flashdata.dev](https://flashdata.dev)
