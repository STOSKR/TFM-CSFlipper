param(
    [int]$Limit = 5,
    [switch]$Fast,
    [switch]$Show,
    [switch]$Json,
    [switch]$Steam,
    [switch]$Persist,
    [double]$Min,
    [double]$Max,
    [int]$Vol,
    [switch]$NoBuff,
    [switch]$NoUu,
    [switch]$C5
)

$argsList = @("$Limit")

if ($Fast) { $argsList += "--fast" }
if ($Show) { $argsList += "--show" }
if ($Json) { $argsList += "--json" }
if ($Steam) { $argsList += "--steam" }
if ($Persist) { $argsList += "--persist" }
if ($PSBoundParameters.ContainsKey("Min")) { $argsList += @("--min", "$Min") }
if ($PSBoundParameters.ContainsKey("Max")) { $argsList += @("--max", "$Max") }
if ($PSBoundParameters.ContainsKey("Vol")) { $argsList += @("--vol", "$Vol") }
if ($NoBuff) { $argsList += "--no-buff" }
if ($NoUu) { $argsList += "--no-uu" }
if ($C5) { $argsList += "--c5" }

python "$PSScriptRoot\steamdt.py" @argsList
exit $LASTEXITCODE
