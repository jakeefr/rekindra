param([Parameter(ValueFromRemainingArguments=$true)][string[]]$HermesArgs)
# Launches Hermes with development storage and caches under the development root
# set by dev-environment.ps1. The launcher comes from REKINDRA_HERMES, else
# <development root>\home\bin\hermes.exe.
. (Join-Path $PSScriptRoot 'dev-environment.ps1')
$launcher = $env:REKINDRA_HERMES
if (-not $launcher) { $launcher = Join-Path $env:REKINDRA_DEV_ROOT 'home\bin\hermes.exe' }
if (-not (Test-Path -LiteralPath $launcher)) { throw "Hermes launcher not found: $launcher. Set REKINDRA_HERMES or REKINDRA_DEV_ROOT." }
& $launcher @HermesArgs
exit $LASTEXITCODE
