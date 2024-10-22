# File name you want to keep for the JSON report
$originalFileName = "ServiceHealth"

# Define a constant file name (no timestamp)
$newFileName = "${originalFileName}.json"

# Local file path (ensures the file is overwritten each time)
$outputFile = "D:\Service Status\Status\$newFileName"

# OneDrive remote name (configured with rclone)
$oneDriveRemoteName = "aiib daily report"

# OneDrive folder path
$oneDriveFolderPath = "/Purbanchal- AIIB+Assam/Service Health"

# Construct the OneDrive path using proper variable expansion
$oneDrivePath = "${oneDriveRemoteName}:${oneDriveFolderPath}"

# List of services to monitor
$servicesToMonitor = @("CrystalHESGapReadingService", "CrystalHESBackGroundServices", "CrystalHESMQTTService", "CrystalHESNodeManagementService", "CrystalHESMQTTPullService", "CrystalHESNotifierService") 

# Initialize an empty array to store the results
$results = @()

# Function to map status codes to readable values
function Get-ServiceStatusDescription {
    param($status)
    switch ($status) {
        "Running"       { return "Running" }
        "Stopped"       { return "Stopped" }
        "StartPending"  { return "Start Pending" }
        "StopPending"   { return "Stop Pending" }
        "Paused"        { return "Paused" }
        "PausePending"  { return "Pause Pending" }
        "ContinuePending" { return "Continue Pending" }
        default         { return "Unknown" }
    }
}

# Function to map StartType codes to readable values (using WMI)
function Get-ServiceStartTypeDescription {
    param($startType)
    switch ($startType) {
        "Automatic" { return "Automatic" }
        "Manual"    { return "Manual" }
        "Disabled"  { return "Disabled" }
        default     { return "Unknown" }
    }
}

# Check status and map values
foreach ($service in $servicesToMonitor) {
    $serviceInfo = Get-Service -Name $service -ErrorAction SilentlyContinue
    if ($serviceInfo) {
        $statusDescription = Get-ServiceStatusDescription $serviceInfo.Status.ToString()
        # Get StartType from WMI (Win32_Service)
        $startType = (Get-WmiObject -Query "SELECT StartMode FROM Win32_Service WHERE Name='$($serviceInfo.Name)'").StartMode
        $startTypeDescription = Get-ServiceStartTypeDescription $startType

        # Collect the results
        $results += [PSCustomObject]@{
            Name        = $serviceInfo.DisplayName
            Status      = $statusDescription
            StartupType = $startTypeDescription
        }
    } else {
        # Handle the case where the service is not found or an error occurs
        $results += [PSCustomObject]@{
            Name        = $service
            Status      = "Unknown"
            StartupType = "Unknown"
        }
    }
}

# Export to JSON (overwrite file if it exists locally)
$results | ConvertTo-json  | Out-File -FilePath $outputFile -Force

Write-Host "Service status exported to $outputFile"

# Upload the JSON file to OneDrive using rclone (overwrite existing file on OneDrive)
try {
    $rcloneOutput = rclone copy $outputFile $oneDrivePath --update --ignore-times
    Write-Host "rclone output: $rcloneOutput"
    Write-Host "File has been uploaded to $oneDrivePath"
}
catch {
    Write-Host "An error occurred during rclone operation: $_"
}
