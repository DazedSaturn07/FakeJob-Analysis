param(
    [Parameter(Mandatory=$true)][int]$Port,
    [Parameter(Mandatory=$true)][string]$QueryFile,
    [string]$ClientLibrary
)
# Read-only DAX probe of the model currently open in Power BI Desktop.
$ErrorActionPreference = 'Stop'
if (-not $ClientLibrary) {
    $package = Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop'
    if (-not $package) { throw 'Supply -ClientLibrary with the installed Microsoft.PowerBI.AdomdClient.dll path.' }
    $installedLibrary = Join-Path $package.InstallLocation 'bin\Microsoft.PowerBI.AdomdClient.dll'
    # Store apps can deny direct assembly loading while allowing a read-only copy.
    $verificationFolder = Join-Path $PSScriptRoot '.verification'
    $null = New-Item -ItemType Directory -Path $verificationFolder -Force
    $ClientLibrary = Join-Path $verificationFolder 'Microsoft.PowerBI.AdomdClient.dll'
    Copy-Item -LiteralPath $installedLibrary -Destination $ClientLibrary -Force
}
$null = [Reflection.Assembly]::LoadFrom($ClientLibrary)
$connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$Port")
try {
    $connection.Open()
    $command = $connection.CreateCommand()
    $command.CommandText = Get-Content -LiteralPath $QueryFile -Raw
    $reader = $command.ExecuteReader()
    $rows = @()
    while ($reader.Read()) {
        $row = [ordered]@{}
        for ($index = 0; $index -lt $reader.FieldCount; $index++) {
            $row[$reader.GetName($index)] = if ($reader.IsDBNull($index)) { $null } else { $reader.GetValue($index) }
        }
        $rows += [pscustomobject]$row
    }
    $reader.Close()
    ConvertTo-Json -InputObject $rows -Depth 8
} finally {
    $connection.Close()
}
