@echo off
:: Request administrator privileges to write to the Registry
NET FILE 1>NUL 2>NUL
if '%errorlevel%' == '0' ( goto gotPrivileges ) else ( goto getPrivileges )

:getPrivileges
    echo Requesting administrative privileges...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /B

:gotPrivileges
echo -----------------------------------------------------
echo Uninstalling File Organizer Context Menus (Local/Dev)
echo -----------------------------------------------------

echo Removing Directory Background menus...
reg delete "HKCR\Directory\Background\shell\FileOrganizer" /f >nul 2>&1

echo Removing Selected Folder (Legacy) menus...
reg delete "HKCR\Directory\shell\FileOrganizer" /f >nul 2>&1

echo Removing Selected Items menus...
reg delete "HKCR\AllFileSystemObjects\shell\FileOrganizer" /f >nul 2>&1

echo.
echo [SUCCESS] Local Context Menus successfully removed!
pause
