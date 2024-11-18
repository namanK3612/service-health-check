# Service Health Monitoring Dashboard  

A comprehensive solution for monitoring the health of critical services, integrating **PowerShell** scripts for service health checks, **Microsoft OneDrive** for data synchronization, and a **Python-powered real-time dashboard** built with Dash.  

## Features  
- **Service Monitoring**: Periodically checks the status of defined services on a Windows server.  
- **JSON Reporting**: Outputs service health details as a JSON file for seamless integration.  
- **Cloud Integration**: Automatically syncs JSON reports to Microsoft OneDrive using `rclone`.  
- **Real-time Dashboard**: Displays service health information in an interactive web-based dashboard using Dash.  
- **Microsoft Teams Alerts**: Sends notifications to Teams channels when services stop or recover.  

## Prerequisites  
### PowerShell Script  
- Windows PowerShell  
- `rclone` configured for OneDrive synchronization  

### Python Dashboard  
- Python 3.7+  
- Required libraries (install via `pip`):  
  ```bash
  pip install dash dash-bootstrap-components requests pytz pandas python-dotenv office365-rest-client
  ```
- Access to a SharePoint folder with JSON service health reports.  

## Setup  

### 1. PowerShell Script  
1. Update the `$serviceNameMapping` with your service names and descriptions.  
2. Modify `$servicesToMonitor` to include the services you want to monitor.  
3. Ensure `rclone` is configured and replace `$oneDriveRemoteName` and `$oneDriveFolderPath` with your OneDrive details.  
4. Run the script to generate and upload JSON reports.  

### 2. Python Dashboard  
1. Clone the repository:  
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```
2. Create a `.env` file with the following environment variables:  
   ```plaintext
   site_url=<Your SharePoint Site URL>
   sharepoint_username=<Your SharePoint Username>
   password=<Your SharePoint Password>
   teams_webhook_url=<Your Teams Webhook URL>
   ```
3. Run the dashboard:  
   ```bash
   python app.py
   ```
4. Access the dashboard at [http://127.0.0.1:8050](http://127.0.0.1:8050).  

## PowerShell Script Details  

### Functionality  
1. **Monitor Services**: Checks the status (`Running`, `Stopped`, etc.) and startup type (`Automatic`, `Manual`, etc.) of defined services.  
2. **JSON Export**: Outputs the data to a fixed local file path.  
3. **OneDrive Sync**: Uploads the JSON file to OneDrive using `rclone`.  

### Configuration Example  
```powershell
$serviceNameMapping = @{
    "YourServiceName" = "Your Readable Service Name"
}
$servicesToMonitor = @("YourServiceName1", "YourServiceName2")
```

### Execution  
Run the script on a schedule using Task Scheduler for automated monitoring.  

## Python Dashboard Details  

### Functionality  
1. **Fetch JSON Reports**: Retrieves service health data from SharePoint.  
2. **Display Status**: Show statuses on a visually appealing web interface.  
3. **Send Alerts**: Notifies via Microsoft Teams if a service stops or resumes.  

### Alerts  
- **Stopped Alert**: Sent every 5 minutes for services that remain stopped.  
- **Recovery Alert**: Sent once when a service resumes.  
