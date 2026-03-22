# Lattice CLI — Standalone Binaries

Pre-built binaries for the `lattice` CLI. No Python installation required.

## Download

| Platform | Architecture | Filename |
|----------|-------------|----------|
| macOS | arm64 (Apple Silicon) | `lattice-macos-arm64.tar.gz` |
| macOS | x86_64 (Intel) | `lattice-macos-x86_64.tar.gz` |
| Linux | x86_64 | `lattice-linux-x86_64.tar.gz` |
| Windows | x86_64 | `lattice-windows-x86_64.zip` |

Grab the latest from the [Releases](../../releases) page.

## Quick start

```bash
# macOS / Linux
tar xzf lattice-macos-arm64.tar.gz
chmod +x lattice
./lattice --help

# Windows (PowerShell)
Expand-Archive lattice-windows-x86_64.zip -DestinationPath .
.\lattice.exe --help
```

Optionally move the binary to a directory on your `PATH`:

```bash
# macOS / Linux
sudo mv lattice /usr/local/bin/

# Windows — copy to a folder on your PATH
move lattice.exe C:\tools\
```

## Build from source

If you prefer to build locally:

```bash
# macOS / Linux
./release/build.sh

# with OpenAI + Anthropic SDKs baked in
./release/build.sh --with-llm
```

```powershell
# Windows
.\release\build.ps1

# with LLM SDKs
.\release\build.ps1 -WithLLM
```

The binary is written to `dist/lattice` (or `dist\lattice.exe` on Windows).

### Requirements for building

- Python 3.9+
- pip

The build scripts install PyInstaller and project dependencies automatically.

## Automated releases (GitHub Actions)

The workflow at `.github/workflows/release.yml` builds binaries for all platforms when you push a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

This creates a GitHub Release with downloadable archives for every platform.

You can also trigger a build manually from the Actions tab using **workflow_dispatch**.

## What's included

The binary bundles:

- The full `lattice` CLI (`discover`, `match`, `generate`, `visualize`, `validate`, `register`, `run`, `bind`)
- `click`, `pyyaml`, `rich` dependencies
- When built with `--with-llm`: `openai` and `anthropic` SDKs

## LLM API keys

The binary does **not** embed API keys. Set them via environment variables:

```bash
export OPENAI_API_KEY=sk-...
# or
export ANTHROPIC_API_KEY=sk-ant-...
```

Then use LLM-powered commands:

```bash
lattice match --spec api.yaml --provider openai
lattice generate --spec api.yaml --name VendorOnboarding --provider anthropic
```
