#requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('ContentCheck', 'ContentPrepare', 'ReconcileFixture', 'RenewCredentials', 'VectorizeG5')][string]$Mode,
    [Parameter(Mandatory = $true)][string]$NamesJson
)

$decoded = ConvertFrom-Json -InputObject $NamesJson -NoEnumerate
if ($decoded -isnot [array] -or @($decoded | Where-Object { $_ -isnot [string] }).Count -ne 0) {
    throw 'G5 private file inventory is invalid.'
}
$names = @($decoded)
$expected = @(1..$names.Count | ForEach-Object { "g5-38852775454-$_.json" })
if ($names.Count -lt 2 -or
    @($names | Where-Object { $expected -cnotcontains $_ }).Count -ne 0 -or
    @($expected | Where-Object { $names -cnotcontains $_ }).Count -ne 0 -or
    ($Mode -ceq 'ContentPrepare' -and $names.Count -ne 2) -or
    ($Mode -ceq 'VectorizeG5' -and $names.Count -cnotin @(2, 4)) -or
    ($Mode -ceq 'ReconcileFixture' -and $names.Count -ne 4)) {
    throw 'G5 private fixture files differ from the exact allowed batch.'
}

$generation = if ($Mode -ceq 'RenewCredentials') { $names.Count + 1 }
    elseif ($Mode -cin @('ContentCheck', 'VectorizeG5', 'ReconcileFixture')) { [Math]::Max(3, $names.Count) }
    else { 3 }
Write-Output "g5-38852775454-$generation.json"
