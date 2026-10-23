# FlashData RPM 软件仓库

[English](README.md) | 简体中文

这是 [FlashData CLI](https://github.com/flashdatadev/flashdata-cli) 的官方签名 RPM 仓库。[FlashData](https://flashdata.dev) 通过 API 提供结构化网页数据；CLI 支持账户初始化、查询、批量下载和任务恢复。软件包包含官方独立可执行文件，无需安装 Go、Python 或 Node.js 运行时。

支持 **x86_64 和 aarch64** 架构的 Fedora 43/44 及 RHEL 8/9/10 用户空间。CI 在对应架构的原生运行器上测试 Fedora 容器和 Red Hat 公开的 UBI 8/9/10 容器。UBI 测试覆盖 RHEL 用户空间；尚未单独认证完整 RHEL 主机配置、订阅软件源、SELinux 策略变更或 FIPS 模式。

## 安装

在受支持、具有 sudo 权限的 DNF 系统上运行一次。命令先核对下载证书的完整指纹，再信任该证书，同时启用软件包和仓库元数据的签名检查，最后安装 `flashdata`。

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

DNF 可能再次导入密钥以验证元数据：仓库元数据密钥环与 RPM 软件包密钥库相互独立，两者使用的都是已核对完整指纹的本地证书。可通过[本仓库的公开指纹](keys/fingerprint.txt)独立比对。

从 [FlashData 账户](https://flashdata.dev) 获取 API 密钥，然后参阅 CLI 的[初始化指南](https://github.com/flashdatadev/flashdata-cli/blob/main/docs/installation.zh-CN.md)。安装及上述离线验证无需 API 密钥。如果之前手动安装过 CLI 或通过 Homebrew 安装，请检查 `command -v flashdata`；RPM 安装位置为 `/usr/bin/flashdata`，可能被 `PATH` 中更靠前的同名文件遮蔽。避免让多个包管理器管理同一个可执行文件。

## 升级与卸载

```bash
sudo dnf --refresh upgrade flashdata
rpm -q flashdata
/usr/bin/flashdata --version
```

```bash
sudo dnf remove flashdata
```

卸载会保留用户配置、凭据和运行历史。软件包不包含修改用户数据的安装脚本。如需停用仓库，删除 `/etc/yum.repos.d/flashdata.repo`，也可删除对应的本地证书文件。已导入的 RPM 证书仍保留在系统 RPM 密钥库中，管理员应确认其他用途后再明确移除。

## 软件包与信任机制

- 稳定版入口：[flashdatadev.github.io/rpm](https://flashdatadev.github.io/rpm/)；[仓库配置](https://flashdatadev.github.io/rpm/flashdata.repo)、[公开证书](https://flashdatadev.github.io/rpm/flashdata.asc)、[软件包清单](https://flashdatadev.github.io/rpm/packages.json)。
- CLI 版本 **1.1.0**，RPM 版本/发行号 **1.1.0-1**，软件包名称 **flashdata**。两个架构的可执行文件均与[官方 v1.1.0 发布文件](https://github.com/flashdatadev/flashdata-cli/releases/tag/v1.1.0)逐字节一致，另附文档、示例、手册页和第三方许可证。
- 独立的 RSA-4096 RPM 签名证书指纹：`23AB58683E85FE7236D369713D19EA52D181CC36`，身份为 `FlashData RPM Signing <support@flashdata.dev>`。RPM 软件包与 `repomd.xml` 都使用 SHA-256 签名，与 APT 证书分开管理。
- 保持 `gpgcheck=1`、`repo_gpgcheck=1` 及 HTTPS 校验。`includepkgs=flashdata` 限制此仓库提供的软件包。RPM 软件包证书导入系统全局信任库，并非仅对单一仓库生效；DNF 元数据密钥环则按仓库隔离。
- [manifest.json](manifest.json) 固定软件包内容及 SHA-256。已发布版本不会原地重建或重新签名。候选仓库通过安装、升级和拒绝篡改测试后才部署元数据，并保留旧软件包及带哈希的索引。
- `metadata_expire=6h` 仅控制 DNF 缓存更新，不是密码学有效期保证。RPM 仓库元数据没有 APT 式 `Valid-Until`。签名证书有效期两年；距离到期不足 30 天时签名流程会拒绝继续，维护者必须提前轮换。每周任务刷新元数据并重新执行完整检查。

参阅 [CI 结果](https://github.com/flashdatadev/rpm/actions/workflows/publish.yml)、[维护与恢复](docs/maintaining.md)及[安全问题报告](SECURITY.md)。每个候选及公开仓库测试容器都从真实签名的 **1.0.1-1** 升级到 **1.1.0-1**，验证可执行文件哈希并保留用户状态。另用签名的 **1.1.0-0.upgradetest** 专用包验证打包修订升级，该测试包不进入公开索引。原有 1.0.0 签名软件包保持不变并继续提供。

支持：[support@flashdata.dev](mailto:support@flashdata.dev) · [flashdata.dev](https://flashdata.dev)
