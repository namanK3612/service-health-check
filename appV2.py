import os
import json
import pandas as pd
from dotenv import load_dotenv
from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential

load_dotenv() 

site_url = os.getenv('site_url')
username = os.getenv('sharepoint_username')  # Updated
password = os.getenv('password')

# Create Dash application with a dark theme
app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

# Define layout for the dashboard
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Service Health Dashboard - AIIB TnD", className="text-center text-light my-4"), width=12)
    ]),
    dcc.Interval(id="interval-component", interval=(600*1000)/10, n_intervals=0),  # Refresh every 5 minutes
    dbc.Row([
        dbc.Col(html.Div(id='service-health-container'), width=12)  # This will hold the service status info
    ])
], fluid=True, style={"backgroundColor": "#2c2f33"})  # Dark background

# Define callback to refresh data and update the dashboard
@app.callback(
    Output('service-health-container', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_dashboard(n):

    # Connect to SharePoint
    ctx = ClientContext(site_url).with_credentials(UserCredential(username, password))

    # Specify the folder path where JSON files are stored
    folder_url = "/sites/CSDataVault/Shared Documents/DB Data dump by AppSupport/Purbanchal- AIIB+Assam/Service Health"

    # Get files from the specified folder
    files = ctx.web.get_folder_by_server_relative_url(folder_url).files
    ctx.load(files)
    ctx.execute_query()

    # Initialize variables to track the latest file
    latest_file = None
    latest_modified_date = None

    # Loop through the files and find the latest JSON file
    for file in files:
        if file.name.endswith('.json'):
            if latest_modified_date is None or file.time_last_modified > latest_modified_date:
                latest_file = file
                latest_modified_date = file.time_last_modified

    # If a latest file was found, read the file content and update the dashboard
    if latest_file:
        file_content = latest_file.read()  # Get file content as bytes

        try:
            json_content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            json_content = file_content.decode('utf-16')

        # Load the JSON content into a Python dictionary
        data = json.loads(json_content)
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(data)
        
        # Create dynamic dashboard content with service status
        service_status_divs = [
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H5(
                            service,
                            className="card-title text-light",
                            style={
                                "whiteSpace": "nowrap", 
                                "overflow": "hidden", 
                                "textOverflow": "ellipsis"
                            }  # Ensures the service name fits in a single line or gets truncated gracefully
                        ),
                        dbc.Badge(
                            "Running" if status.lower() == 'running' else "Stopped",
                            color="success" if status.lower() == 'running' else "danger",
                            className="p-2",
                        ),
                    ]),
                    className="shadow-sm mb-4 bg-dark",  # Dark card background
                    style={'width': '18rem'}
                ),
                width=4,  # Adjust the width as per requirement
                className="mb-4"
            ) for service, status in zip(df['Name'], df['Status'])  # Replace with actual column names
        ]

        # Arrange service statuses into rows
        rows = []
        for i in range(0, len(service_status_divs), 3):  # 3 cards per row
            rows.append(dbc.Row(service_status_divs[i:i+3], justify="center"))

        return rows

    else:
        return dbc.Alert("No JSON files found in the specified folder.", color="warning")

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
