@echo off
:: Request administrator privileges to write to the Registry
NET FILE 1>NUL 2>NUL
if '%errorlevel%' == '0' ( goto gotPrivileges ) else ( goto getPrivileges )

:getPrivileges
    echo Requesting administrative privileges...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /B

:gotPrivileges
echo ---------------------------------------------------
echo Installing File Organizer Context Menus (Local/Dev)
echo ---------------------------------------------------

:: Get the directory where this batch file is located
set "APP_DIR=%~dp0"
:: Remove trailing slash
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

:: Paths
set "LOGO_PATH=%APP_DIR%\Logo.ico"
set "PYTHON_SCRIPT=%APP_DIR%\organizer.py"

:: Ensure python is available
python --version >nul 2>&1
if "%errorlevel%" NEQ "0" (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /B
)

:: Get absolute path to pythonw.exe using python itself
python -c "import sys; print(sys.executable.replace('python.exe', 'pythonw.exe'))" > "%TEMP%\pywpath.txt"
set /p PYTHONW_PATH=<"%TEMP%\pywpath.txt"
del "%TEMP%\pywpath.txt"

:: The command we use to run the script via python w/o a permanent console window
set "CMD_BASE=\"%PYTHONW_PATH%\" \"%PYTHON_SCRIPT%\""

:: =====================================================
:: DIRECTORY BACKGROUND
:: =====================================================
echo Installing Directory Background menus...

set "KEY=HKCR\Directory\Background\shell\FileOrganizer"
reg add "%KEY%" /v MUIVerb /t REG_SZ /d "File Organizer" /f >nul
reg add "%KEY%" /v Icon /t REG_SZ /d "%LOGO_PATH%" /f >nul
reg add "%KEY%" /v SubCommands /t REG_SZ /d "" /f >nul

:: 01 By Category
reg add "%KEY%\shell\01_ByCategory" /v MUIVerb /t REG_SZ /d "By Category..." /f >nul
reg add "%KEY%\shell\01_ByCategory\command" /ve /t REG_SZ /d "%CMD_BASE% category \"%%V\" --background" /f >nul

:: 02 By Source
reg add "%KEY%\shell\02_BySource" /v MUIVerb /t REG_SZ /d "By Source" /f >nul
reg add "%KEY%\shell\02_BySource\command" /ve /t REG_SZ /d "%CMD_BASE% source \"%%V\" --background" /f >nul

:: 03 By Type
reg add "%KEY%\shell\03_ByType" /v MUIVerb /t REG_SZ /d "By Type" /f >nul
reg add "%KEY%\shell\03_ByType\command" /ve /t REG_SZ /d "%CMD_BASE% type \"%%V\" --background" /f >nul

:: 04 File Puller Submenu
reg add "%KEY%\shell\04_FilePuller" /v MUIVerb /t REG_SZ /d "File Puller" /f >nul
reg add "%KEY%\shell\04_FilePuller" /v SubCommands /t REG_SZ /d "" /f >nul

reg add "%KEY%\shell\04_FilePuller\shell\01_PullHere" /v MUIVerb /t REG_SZ /d "Move Out - All Files" /f >nul
reg add "%KEY%\shell\04_FilePuller\shell\01_PullHere\command" /ve /t REG_SZ /d "%CMD_BASE% pull_here \"%%V\" --background" /f >nul

:: 05 Manage Presets
reg add "%KEY%\shell\05_Manage" /v MUIVerb /t REG_SZ /d "Manage Presets..." /f >nul
reg add "%KEY%\shell\05_Manage\command" /ve /t REG_SZ /d "%CMD_BASE% manage \"%%V\"" /f >nul

:: 06 Delete Empty
reg add "%KEY%\shell\06_DeleteEmpty" /v MUIVerb /t REG_SZ /d "Delete Empty Folders" /f >nul
reg add "%KEY%\shell\06_DeleteEmpty\command" /ve /t REG_SZ /d "%CMD_BASE% delete_empty \"%%V\" --background" /f >nul

:: 07 Undo All
reg add "%KEY%\shell\07_UndoAll" /v MUIVerb /t REG_SZ /d "Undo All" /f >nul
reg add "%KEY%\shell\07_UndoAll\command" /ve /t REG_SZ /d "%CMD_BASE% undo_all \"%%V\"" /f >nul

:: 08 Undo Once
reg add "%KEY%\shell\08_UndoOnce" /v MUIVerb /t REG_SZ /d "Undo Once" /f >nul
reg add "%KEY%\shell\08_UndoOnce\command" /ve /t REG_SZ /d "%CMD_BASE% undo \"%%V\"" /f >nul


:: =====================================================
:: SELECTED FILES/FOLDERS (ALL FILE SYSTEM OBJECTS)
:: =====================================================
echo Installing Selected Items menus...

set "DKEY=HKCR\AllFileSystemObjects\shell\FileOrganizer"
reg add "%DKEY%" /v MUIVerb /t REG_SZ /d "File Organizer" /f >nul
reg add "%DKEY%" /v Icon /t REG_SZ /d "%LOGO_PATH%" /f >nul
reg add "%DKEY%" /v SubCommands /t REG_SZ /d "" /f >nul
reg add "%DKEY%" /v MultiSelectModel /t REG_SZ /d "Player" /f >nul

:: 01 By Category
reg add "%DKEY%\shell\01_ByCategory" /v MUIVerb /t REG_SZ /d "By Category..." /f >nul
reg add "%DKEY%\shell\01_ByCategory\command" /ve /t REG_SZ /d "%CMD_BASE% category \"%%1\" --items" /f >nul

:: 02 By Source
reg add "%DKEY%\shell\02_BySource" /v MUIVerb /t REG_SZ /d "By Source" /f >nul
reg add "%DKEY%\shell\02_BySource\command" /ve /t REG_SZ /d "%CMD_BASE% source \"%%1\" --items" /f >nul

:: 03 By Type
reg add "%DKEY%\shell\03_ByType" /v MUIVerb /t REG_SZ /d "By Type" /f >nul
reg add "%DKEY%\shell\03_ByType\command" /ve /t REG_SZ /d "%CMD_BASE% type \"%%1\" --items" /f >nul

:: 04 File Puller Submenu
reg add "%DKEY%\shell\04_FilePuller" /v MUIVerb /t REG_SZ /d "File Puller" /f >nul
reg add "%DKEY%\shell\04_FilePuller" /v SubCommands /t REG_SZ /d "" /f >nul

reg add "%DKEY%\shell\04_FilePuller\shell\01_ToBin" /v MUIVerb /t REG_SZ /d "Move Files To \"File Bin\"" /f >nul
reg add "%DKEY%\shell\04_FilePuller\shell\01_ToBin\command" /ve /t REG_SZ /d "%CMD_BASE% pull_all \"%%1\" --items" /f >nul

reg add "%DKEY%\shell\04_FilePuller\shell\02_PullAbove" /v MUIVerb /t REG_SZ /d "Move Files Out" /f >nul
reg add "%DKEY%\shell\04_FilePuller\shell\02_PullAbove\command" /ve /t REG_SZ /d "%CMD_BASE% pull_above \"%%1\" --items" /f >nul

:: 05 Manage Presets
reg add "%DKEY%\shell\05_Manage" /v MUIVerb /t REG_SZ /d "Manage Presets..." /f >nul
reg add "%DKEY%\shell\05_Manage\command" /ve /t REG_SZ /d "%CMD_BASE% manage \"%%1\"" /f >nul

:: 06 Delete Empty
reg add "%DKEY%\shell\06_DeleteEmpty" /v MUIVerb /t REG_SZ /d "Delete Empty Folders" /f >nul
reg add "%DKEY%\shell\06_DeleteEmpty\command" /ve /t REG_SZ /d "%CMD_BASE% delete_empty \"%%1\" --items" /f >nul

:: 07 Undo All
reg add "%DKEY%\shell\07_UndoAll" /v MUIVerb /t REG_SZ /d "Undo All" /f >nul
reg add "%DKEY%\shell\07_UndoAll\command" /ve /t REG_SZ /d "%CMD_BASE% undo_all \"%%1\"" /f >nul

:: 08 Undo Once
reg add "%DKEY%\shell\08_UndoOnce" /v MUIVerb /t REG_SZ /d "Undo Once" /f >nul
reg add "%DKEY%\shell\08_UndoOnce\command" /ve /t REG_SZ /d "%CMD_BASE% undo \"%%1\"" /f >nul

echo.
echo [SUCCESS] Local Context Menus successfully installed!
echo You can now right-click any folder or empty space to use the tool.
echo NOTE: Ensure you don't move the "organizer.py" directory, or the registry keys will break.
pause
