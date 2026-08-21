# Run this script as Administrator to set up the Task Scheduler

$taskName = "CanvasCourseChangeLogAutomator"
$actionScriptPath = Join-Path -Path $PSScriptRoot -ChildPath "..\src\main.py"
$workingDir = Join-Path -Path $PSScriptRoot -ChildPath ".."
$pythonExe = "python"

# Create action to run the python script
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$actionScriptPath`"" -WorkingDirectory $workingDir

# Create trigger for user logon
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Ensure it only runs when network is available (since it scrapes the web)
$settings = New-ScheduledTaskSettingsSet -RunOnlyIfNetworkAvailable

# Register the task
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName $taskName -Description "Runs the Canvas Course Change Log automator on logon." -Settings $settings -Force

Write-Host "Task '$taskName' registered successfully. It will run on user logon."
Write-Host "Note: The python script internally handles ensuring it only does the heavy scraping once per week."
