@echo off
rem Chronify: instala/actualiza el acceso directo del escritorio y abre la app sin consola.
rem En un PC nuevo basta con descomprimir el zip de la release y hacer doble clic aqui.
setlocal
cd /d "%~dp0"

call :buscar_python
if not defined PYW (
  echo Chronify necesita Python 3.10 o superior y no lo encuentro. Intentando instalarlo con winget...
  where winget >nul 2>nul && winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  call :buscar_python
)
if not defined PYW (
  echo.
  echo No he podido instalar Python automaticamente.
  echo Instalalo desde https://www.python.org/downloads/ ^(marca "Add python.exe to PATH"^)
  echo y vuelve a abrir este archivo.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)

rem Icono con nombre versionado (Windows cachea los iconos por ruta y no veria el logo nuevo)
set "ICO=%~dp0web\logo.ico"
for %%f in ("%~dp0web\icono-*.ico") do set "ICO=%%~ff"

rem Acceso directo en el escritorio (se rehace siempre por si cambia Python o la carpeta)
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Chronify.lnk')); $s.TargetPath='%PYW%'; $s.Arguments='\"%~dp0app.py\"'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%ICO%,0'; $s.Description='Ordenar mis listas de Spotify por fecha real'; $s.Save()"

start "" "%PYW%" "%~dp0app.py"
exit /b 0

rem --- Busca pythonw.exe (Python sin ventana). Ignora el "python" falso de la Microsoft Store. ---
:buscar_python
set "PYW="
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%i in ('python -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%i"
  goto :eof
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%i in ('py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"') do set "PYW=%%i"
  goto :eof
)
rem Recien instalado con winget: aun no esta en el PATH de esta ventana
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%d\pythonw.exe" set "PYW=%%d\pythonw.exe"
goto :eof
