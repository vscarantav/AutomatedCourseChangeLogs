Set WshShell = CreateObject("WScript.Shell")
' Change working directory to the project folder
WshShell.CurrentDirectory = "C:\Users\vscaran\Desktop\DevProjects\Automated Course Change Logs"
' Run the python script invisibly (0 = vbHide)
WshShell.Run "python src\main.py", 0, False
