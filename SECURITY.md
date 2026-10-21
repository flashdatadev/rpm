# Security

Report vulnerabilities or suspected signing-key exposure privately to [support@flashdata.dev](mailto:support@flashdata.dev). Include affected versions and reproduction details, without API keys or credentials. [FlashData](https://flashdata.dev) maintains this repository.

The dedicated RPM public certificate is in [keys/flashdata.asc](keys/flashdata.asc); its full fingerprint is `23AB58683E85FE7236D369713D19EA52D181CC36`. RPM package trust uses the system RPM database. Metadata verification uses DNF's separate per-repository keyring. Keep both `gpgcheck` and `repo_gpgcheck` enabled. The APT signing certificate is different.

On a suspected compromise, pause deployment, preserve evidence, revoke and replace the certificate through an independently reviewed announcement, and distribute replacement configuration. Do not advise users to bypass signature checks. See [maintenance and recovery](docs/maintaining.md).
