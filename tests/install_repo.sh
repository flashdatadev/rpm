#!/usr/bin/env bash
# Run in disposable Fedora/Red Hat UBI containers only.
set -euo pipefail
trap 'echo "RPM test failed at line $LINENO" >&2; for log in /tmp/wrong-key.log /tmp/bad-metadata.log /tmp/bad-package.log /tmp/unsigned.log; do if [ -f "$log" ]; then tail -n 25 "$log" >&2; fi; done' ERR
base_url="${1:?repository URL required}"
fixtures="${2:?fixture directory required}"
mode="${3:-candidate}"
arch="$(rpm --eval '%{_arch}')"
fingerprint=23AB58683E85FE7236D369713D19EA52D181CC36
# Fedora's minimal container defaults omit %doc files; test a full installation.
for config in /etc/dnf/dnf.conf /etc/yum.conf; do
  if [ -f "$config" ]; then sed -i '/^[[:space:]]*tsflags[[:space:]]*=/d' "$config"; fi
done
dnf install -y ca-certificates gnupg2 python3
version="$(python3 -c "import json;print(json.load(open('/work/manifest.json'))['releases'][-1]['version'])")"
package_version="$(python3 -c "import json;m=json.load(open('/work/manifest.json'))['releases'][-1];print(m['version']+'-'+m['release'])")"
if ! command -v curl >/dev/null 2>&1; then dnf install -y curl; fi
if [ "$mode" = live ]; then
  dnf install -y sudo
  python3 - > /tmp/documented-install.sh <<'PY'
import pathlib,re
first=lambda name: re.search(r'```bash\n(.*?)```',pathlib.Path('/work',name).read_text(),re.S).group(1)
assert first('README.md')==first('README.zh-CN.md')
print(first('README.md'))
PY
  bash /tmp/documented-install.sh
fi
curl -fsSL "$base_url/flashdata.asc" -o /tmp/flashdata.asc
actual="$(gpg --batch --show-keys --with-colons /tmp/flashdata.asc 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')"
test "$actual" = "$fingerprint"
install -d -m 0755 /etc/pki/rpm-gpg
install -m 0644 /tmp/flashdata.asc /etc/pki/rpm-gpg/RPM-GPG-KEY-flashdata
rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-flashdata
cat > /etc/yum.repos.d/flashdata.repo <<EOF
[flashdata]
name=FlashData CLI stable
baseurl=$base_url/stable/\$basearch/
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-flashdata
sslverify=1
includepkgs=flashdata
metadata_expire=6h
skip_if_unavailable=0
EOF
dnf -y --refresh --disablerepo='*' --enablerepo=flashdata makecache
dnf install -y flashdata
test "$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}' flashdata)" = "$package_version.$arch"
flashdata --version --json | tee /tmp/flashdata-version.json
python3 - <<'PY'
import json
v=json.load(open('/tmp/flashdata-version.json'))
m=json.load(open('/work/manifest.json'))['releases'][-1]
assert v['ok'] and v['data']=={'version':m['version'],'commit':m['source_commit']}
PY
flashdata --help
flashdata discover plans --help
flashdata discover status --help
flashdata commands --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert {"auth","bulk","query","runs","setup","skills"} <= {c["name"] for c in d["data"]["commands"]}'
# Exercise the bundled skills without credentials or paid queries.
skill_project="$(mktemp -d)"
flashdata setup --skip-auth --agent codex --directory "$skill_project" --non-interactive
flashdata skills verify --agent codex --directory "$skill_project" --non-interactive
test -s "$skill_project/.agents/skills/flashdata/SKILL.md"
test -s "$skill_project/.agents/skills/youtube-transcript/SKILL.md"
test -s /usr/share/doc/flashdata/README.zh-CN.md
test -s /usr/share/doc/flashdata/examples/query.json
test -s /usr/share/man/man1/flashdata.1.gz
test -s /usr/share/licenses/flashdata/LICENSE
rpm -V flashdata
mkdir -p "$HOME/.local/state/flashdata"
printf 'preserve user profiles and run history\n' > "$HOME/.local/state/flashdata/package-test-marker"
chmod 0600 "$HOME/.local/state/flashdata/package-test-marker"
python3 /work/tests/upgrade_state.py prepare "$HOME/.local/state/flashdata"
dnf reinstall -y flashdata
test -s "$HOME/.local/state/flashdata/package-test-marker"
dnf remove -y flashdata
test ! -e /usr/bin/flashdata
# Upgrade the actual signed previous release, preserving user state.
previous="$(python3 -c "import json;m=json.load(open('/work/manifest.json'))['releases'][-2];print(m['version']+'-'+m['release'])")"
rpmkeys --checksig "/work/packages/flashdata-$previous.$arch.rpm"
rpm -Uvh "/work/packages/flashdata-$previous.$arch.rpm"
test "$(rpm -q --qf '%{VERSION}-%{RELEASE}' flashdata)" = "$previous"
flashdata --version
python3 /work/tests/upgrade_state.py check "$HOME/.local/state/flashdata"
dnf -y --refresh upgrade flashdata
test "$(rpm -q --qf '%{VERSION}-%{RELEASE}' flashdata)" = "$package_version"
rpm -V flashdata
python3 /work/tests/upgrade_state.py check "$HOME/.local/state/flashdata"
test -s "$HOME/.local/state/flashdata/package-test-marker"
dnf remove -y flashdata
rpmkeys --checksig "$fixtures/flashdata-$version-0.upgradetest.$arch.rpm"
rpm -Uvh "$fixtures/flashdata-$version-0.upgradetest.$arch.rpm"
test "$(rpm -q --qf '%{RELEASE}' flashdata)" = 0.upgradetest
dnf -y --refresh upgrade flashdata
test "$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}' flashdata)" = "$package_version.$arch"
rpm -V flashdata
python3 /work/tests/upgrade_state.py check "$HOME/.local/state/flashdata"
test -s "$HOME/.local/state/flashdata/package-test-marker"
python3 - "$arch" <<'PY'
import hashlib,json,sys
m=json.load(open('/work/manifest.json'))['releases'][-1]
assert hashlib.sha256(open('/usr/bin/flashdata','rb').read()).hexdigest()==m['executables'][sys.argv[1]]
PY
dnf remove -y flashdata
test ! -e /usr/bin/flashdata
test -s "$HOME/.local/state/flashdata/package-test-marker"
curl -fsSL "$base_url/stable/$arch/Packages/flashdata-$package_version.$arch.rpm" -o /tmp/flashdata.rpm
rpmkeys --checksig --verbose /tmp/flashdata.rpm

if [ "$mode" = candidate ]; then
  # Wrong metadata key, using a fresh repository ID/cache to avoid earlier imports.
  export GNUPGHOME="$(mktemp -d)"
  chmod 0700 "$GNUPGHOME"
  gpg --batch --passphrase '' --quick-generate-key 'RPM negative test <invalid@example.invalid>' rsa2048 sign 0
  gpg --armor --export > /tmp/wrong-key.asc
  sed -e 's/\[flashdata\]/[flashdata-wrong]/' -e 's|file:///etc/pki/rpm-gpg/RPM-GPG-KEY-flashdata|file:///tmp/wrong-key.asc|' /etc/yum.repos.d/flashdata.repo > /etc/yum.repos.d/flashdata-wrong.repo
  if dnf -y --refresh --disablerepo='*' --enablerepo=flashdata-wrong --setopt=cachedir=/tmp/wrong-cache makecache > /tmp/wrong-key.log 2>&1; then
    echo 'DNF accepted an unrelated metadata key' >&2; exit 1
  fi
  grep -Ei 'GPG|signature|key' /tmp/wrong-key.log
  # Change signed repomd bytes while retaining its original signature.
  cp -a /work/dist /tmp/tampered
  printf '\n<!-- altered -->\n' >> "/tmp/tampered/stable/$arch/repodata/repomd.xml"
  # RHEL 8's Python 3.6 predates http.server --directory.
  python3 -c 'import os,http.server; os.chdir("/tmp/tampered"); http.server.HTTPServer(("127.0.0.1",8766),http.server.SimpleHTTPRequestHandler).serve_forever()' >/tmp/tampered-server.log 2>&1 &
  server_pid=$!
  trap 'kill "$server_pid" 2>/dev/null || true' EXIT
  sed -e 's/\[flashdata\]/[flashdata-tampered]/' -e "s|$base_url|http://127.0.0.1:8766|" /etc/yum.repos.d/flashdata.repo > /etc/yum.repos.d/flashdata-tampered.repo
  sleep 1
  if dnf -y --refresh --disablerepo='*' --enablerepo=flashdata-tampered --setopt=cachedir=/tmp/bad-metadata-cache makecache > /tmp/bad-metadata.log 2>&1; then
    echo 'DNF accepted altered signed metadata' >&2; exit 1
  fi
  grep -Ei 'GPG|signature|verification' /tmp/bad-metadata.log
  # Restore signed metadata, but change the RPM itself; index/package checks must reject it.
  cp "/work/dist/stable/$arch/repodata/repomd.xml" "/tmp/tampered/stable/$arch/repodata/repomd.xml"
  # Keep length unchanged so rejection must exercise content verification.
  python3 - "$arch" <<'PY'
import pathlib,sys
import json
m=json.load(open('/work/manifest.json'))['releases'][-1]
p=pathlib.Path('/tmp/tampered/stable')/sys.argv[1]/'Packages'/('flashdata-'+m['version']+'-'+m['release']+'.'+sys.argv[1]+'.rpm')
data=bytearray(p.read_bytes())
data[-1]^=1
p.write_bytes(data)
PY
  if dnf -y --refresh --disablerepo='*' --enablerepo=flashdata-tampered --setopt=cachedir=/tmp/bad-package-cache install flashdata > /tmp/bad-package.log 2>&1; then
    echo 'DNF accepted modified package bytes' >&2; exit 1
  fi
  cat /tmp/bad-package.log
  grep -Ei 'checksum|digest|mismatch|does not match|doesn.t match' /tmp/bad-package.log
  # Metadata signatures do not substitute for the individual RPM signature.
  # Prepared on the build runner: installed clients do not need rpm-sign.
  cp "$fixtures/unsigned-$arch.rpm" /tmp/unsigned.rpm
  if dnf -y --disablerepo='*' --setopt=localpkg_gpgcheck=1 install /tmp/unsigned.rpm > /tmp/unsigned.log 2>&1; then
    echo 'DNF accepted an unsigned package under signature enforcement' >&2; exit 1
  fi
  grep -Ei 'GPG|signature|not signed|unsigned' /tmp/unsigned.log
fi
echo "PASS: $mode $(. /etc/os-release; echo "$ID $VERSION_ID") $arch install/reinstall/upgrade/remove and preserved user state"
