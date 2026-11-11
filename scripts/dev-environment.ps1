# Process-local paths only. Do not change global environment or user credentials.
# Dot-source it: . ./scripts/dev-environment.ps1 [-DevRoot <folder>]
# The development root comes from -DevRoot, then REKINDRA_DEV_ROOT, then .local/dev
# inside this repository (git-ignored).
param([string]$DevRoot = $env:REKINDRA_DEV_ROOT)
if (-not $DevRoot) { $DevRoot = Join-Path (Split-Path $PSScriptRoot -Parent) '.local\dev' }
$DevRoot = [IO.Path]::GetFullPath($DevRoot)
$env:REKINDRA_DEV_ROOT = $DevRoot
$env:HERMES_HOME = Join-Path $DevRoot 'home'
$env:HERMES_RUNTIME_DIR = Join-Path $DevRoot 'home\tools'
$env:TEMP = Join-Path $DevRoot 'temp'
$env:TMP = $env:TEMP
$env:UV_CACHE_DIR = Join-Path $DevRoot 'cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $DevRoot 'python'
$env:PIP_CACHE_DIR = Join-Path $DevRoot 'cache\pip'
$env:npm_config_cache = Join-Path $DevRoot 'cache\npm'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $DevRoot 'browsers'
$env:HF_HOME = Join-Path $DevRoot 'cache\huggingface'
$env:XDG_CACHE_HOME = Join-Path $DevRoot 'cache'
$env:XDG_DATA_HOME = Join-Path $DevRoot 'data'
$env:XDG_CONFIG_HOME = Join-Path $DevRoot 'config'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
