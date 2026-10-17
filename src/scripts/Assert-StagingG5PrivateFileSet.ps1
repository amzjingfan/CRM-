#requires -Version 7.0

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('ContentCheck', 'ContentPrepare', 'RenewCredentials', 'VectorizeG5')][string]$Mode,
    [Parameter(Mandatory = $true)][string]$NamesJson
)

$original = @('g5-38852775454-1.json', 'g5-38852775454-2.json')
$renewed = @($original + 'g5-38852775454-3.json')
$decoded = ConvertFrom-Json -InputObject $NamesJson -NoEnumerate
if ($decoded -isnot [array] -or @($decoded | Where-Object { $_ -isnot [string] }).Count -ne 0) {
    throw 'G5 private file inventory is invalid.'
}
$names = @($decoded)
$expected = if ($Mode -ceq 'ContentCheck' -and $names.Count -eq 3) { $renewed } else { $original }
if ($names.Count -ne $expected.Count -or
    @($names | Where-Object { $expected -cnotcontains $_ }).Count -ne 0 -or
    @($expected | Where-Object { $names -cnotcontains $_ }).Count -ne 0) {
    throw 'G5 private fixture files differ from the exact allowed batch.'
}
