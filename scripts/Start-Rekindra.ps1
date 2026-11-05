param([Parameter(ValueFromRemainingArguments=$true)][string[]]$HermesArgs)
. (Join-Path $PSScriptRoot 'dev-environment.ps1')
$launcher = '<local path>\home\bin\hermes.exe'
if (-not (Test-Path -LiteralPath $launcher)) { throw 'The D: Hermes development installation is missing.' }
& $launcher @HermesArgs
exit $LASTEXITCODE
