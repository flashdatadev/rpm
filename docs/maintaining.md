# Maintaining the FlashData RPM repository

Official RPM distribution for [FlashData](https://flashdata.dev). [English installation](../README.md) · [简体中文安装](../README.zh-CN.md).

## Publishing

`manifest.json` is an append-only ledger of release version, RPM release, source commit, upstream archive and executable SHA-256 values, and final signed RPM SHA-256 values. `packages/` contains immutable signed packages. Never replace an existing version/release/architecture with new bytes. Increment the RPM release for packaging-only changes; increment the CLI version for executable changes. Preserve the original binary without stripping or ELF transformations.

The initial native build and signature verification ran in [bootstrap run 39664051959](https://github.com/flashdatadev/rpm/actions/runs/39664051959). `bootstrap.yml` builds only entries whose package hashes have not yet been sealed in the ledger, on matching x86_64/aarch64 Ubuntu runners. Download its verified artifact, inspect signatures and payload hashes, add the signed RPMs and final hashes, then review and push. QA fixtures never enter `packages/` or public indexes.

`publish.yml` validates signed packages and docs, builds older-release fixtures on both native CPUs, creates `createrepo_c` indexes, and signs metadata and fixtures in the protected `rpm-signing` environment. Ten candidate tests cover Fedora 43/44 and Red Hat UBI 8/9/10 on both CPUs. Deployment requires all candidate tests to pass; ten public HTTPS tests then execute the documented installer and check install, reinstall, upgrade, removal and preservation of user state. Candidate tests also reject wrong metadata keys, changed signed metadata, modified package bytes and unsigned local RPMs with local signature enforcement.

The fixture version **1.0.0-0.upgradetest** contains the actual 1.0.0 executable and sorts below **1.0.0-1**. It is retained only as a short-lived CI artifact. This tests DNF replacement, not compatibility across future CLI state/schema changes. Add tests using actual preceding releases when available.

Generate metadata in a fresh tree and deploy one Pages artifact; never mutate live directories in place. Existing RPMs retain their signatures. SHA-256 named historical indexes are regenerated from ledger prefixes with stable package mtimes. When changing `createrepo_c`, confirm previous index filenames/bytes remain available; preserve historical metadata explicitly if serialization changes. Never drop old packages while supported clients might reference them.

## Signing and recovery

The dedicated RPM key has an RSA-4096 certification-only primary and RSA-4096 signing subkey, two-year expiry and SHA-256 signatures. CI receives only a passphrase-encrypted signing-subkey export (stub primary) and passphrase, in environment secrets `RPM_SIGNING_PRIVATE_KEY` and `RPM_SIGNING_PASSPHRASE`. The `rpm-signing` environment permits only `main`. Signing imports into a mode-0700 temporary keyring outside artifacts, unlocks through stdin, stops its isolated agent and removes the keyring in `finally`. Never print secrets or put a passphrase on a command line.

The initial administrator's full primary-key recovery backup, passphrase and revocation certificate are encrypted with Windows DPAPI at `%LOCALAPPDATA%\FlashData\rpm-signing\signing-backup.dpapi`, with ACLs limited to the account and SYSTEM. This is machine/account-bound recovery, not an independent off-machine backup. Arrange a separately encrypted offline backup before changing computers. Never put backups, secret exports or the GPG home in Git or artifacts. CI's signing-only export cannot recover the primary key.

The signer refuses certificates expiring within 30 days. Rotate before expiry, review the new full fingerprint independently, update both languages, public key/configuration and CI secrets, and document migration for installed clients. Preserve prior public certificates for historical verification. On exposure, stop publishing and revoke through a trusted announcement; never disable verification to restore service.

## Operation

Pushes to `main`, manual dispatch and a weekly Monday schedule run all checks. GitHub can disable scheduled workflows in inactive public repositories after 60 days; monitor Actions and key expiry. DNF `metadata_expire` is a cache setting. RPM metadata has no signed APT-style `Valid-Until` and does not guarantee replay prevention.

For a packaging failure, leave the last good deployment intact, fix the candidate and rerun. Investigate signatures, CDN cache and architecture URLs on a public verification failure. Do not rewrite signed packages. Prefer a new package release over a version rollback. Removing repository files does not remove certificates from RPM's global key database.

UBI container results validate RHEL userspace without a subscription. Full hosts, subscription content, enterprise proxies, SELinux changes and FIPS mode require environment-specific testing. No signup was needed; ownership is `flashdatadev`, contact [support@flashdata.dev](mailto:support@flashdata.dev).
