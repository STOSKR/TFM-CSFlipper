param(
    [int]$Limit = 5,
    [switch]$Fast,
    [switch]$Show,
    [switch]$Json,
    [switch]$Steam,
    [switch]$Persist,
    [string]$Output,
    [switch]$NoOutput,
    [string]$SessionState,
    [switch]$NoSessionState,
    [switch]$Login,
    [int]$LoginWait,
    [double]$Min,
    [double]$Max,
    [int]$Vol,
    [switch]$NoBuff,
    [switch]$Uu,
    [switch]$NoUu,
    [switch]$C5
)

$argsList = @("$Limit")

if ($Fast) { $argsList += "--fast" }
if ($Show) { $argsList += "--show" }
if ($Json) { $argsList += "--json" }
if ($Steam) { $argsList += "--steam" }
if ($Persist) { $argsList += "--persist" }
if ($PSBoundParameters.ContainsKey("Output")) { $argsList += @("--output", "$Output") }
if ($NoOutput) { $argsList += "--no-output" }
if ($PSBoundParameters.ContainsKey("SessionState")) { $argsList += @("--session-state", "$SessionState") }
if ($NoSessionState) { $argsList += "--no-session-state" }
if ($Login) { $argsList += "--login" }
if ($PSBoundParameters.ContainsKey("LoginWait")) { $argsList += @("--login-wait", "$LoginWait") }
if ($PSBoundParameters.ContainsKey("Min")) { $argsList += @("--min", "$Min") }
if ($PSBoundParameters.ContainsKey("Max")) { $argsList += @("--max", "$Max") }
if ($PSBoundParameters.ContainsKey("Vol")) { $argsList += @("--vol", "$Vol") }
if ($NoBuff) { $argsList += "--no-buff" }
if ($Uu) { $argsList += "--uu" }
if ($NoUu) { $argsList += "--no-uu" }
if ($C5) { $argsList += "--c5" }

python "$PSScriptRoot\steamdt.py" @argsList
exit $LASTEXITCODE
