# Process-local paths only. Do not change global environment or user credentials.
$env:HERMES_HOME = '<local path>\home'
$env:HERMES_RUNTIME_DIR = '<local path>\home\tools'
$env:TEMP = '<local path>\temp'
$env:TMP = $env:TEMP
$env:UV_CACHE_DIR = '<local path>\cache\uv'
$env:UV_PYTHON_INSTALL_DIR = '<local path>\python'
$env:PIP_CACHE_DIR = '<local path>\cache\pip'
$env:npm_config_cache = '<local path>\cache\npm'
$env:PLAYWRIGHT_BROWSERS_PATH = '<local path>\browsers'
$env:HF_HOME = '<local path>\cache\huggingface'
$env:XDG_CACHE_HOME = '<local path>\cache'
$env:XDG_DATA_HOME = '<local path>\data'
$env:XDG_CONFIG_HOME = '<local path>\config'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
