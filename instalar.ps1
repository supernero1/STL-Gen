param([switch]$SinModelos, [switch]$Multivista)
$ErrorActionPreference = 'Stop'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
Set-Location -LiteralPath $PSScriptRoot

function Ejecutar { param([string]$Exe, [string[]]$Argumentos)
    & $Exe @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "El comando fallo con codigo $LASTEXITCODE : $Exe" }
}

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if ($pythonCmd) { Ejecutar $pythonCmd.Source @('-3.12', '-m', 'venv', '.venv') }
    elseif (Test-Path -LiteralPath $bundledPython) { Ejecutar $bundledPython @('-m', 'venv', '.venv') }
    else { throw 'Instala Python 3.12 de python.org (con py launcher) y vuelve a ejecutar instalar.ps1.' }
}
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Ejecutar $pythonExe @('-m', 'pip', '--version')
Ejecutar $pythonExe @('-m', 'app.bootstrap')
Ejecutar $pythonExe @('-m', 'pip', 'install', '-r', 'requirements-ai.txt')

$vendorPath = Join-Path $PSScriptRoot 'vendor\Hunyuan3D-2'
$revision = 'f8db63096c8282cb27354314d896feba5ba6ff8a'
if (-not (Test-Path -LiteralPath "$vendorPath\hy3dgen")) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Instala Git desde git-scm.com.' }
    Ejecutar 'git' @('clone', 'https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git', $vendorPath)
    Ejecutar 'git' @('-C', $vendorPath, 'checkout', $revision)
} else {
    $head = & git -C $vendorPath rev-parse HEAD
    if ($head -ne $revision) { throw "La revision del motor no coincide. Se esperaba $revision. Conserva tus cambios y usa una copia de esa revision." }
}

if (-not (Test-Path -LiteralPath 'node_modules\three\build\three.module.js')) {
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    $pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
    $bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node'
    if ($npmCommand) { Ejecutar $npmCommand.Source @('install', '--no-audit', '--no-fund') }
    elseif ($pnpmCommand) { Ejecutar $pnpmCommand.Source @('install', '--frozen-lockfile') }
    elseif (Test-Path -LiteralPath "$bundledNode\node_modules\pnpm\bin\pnpm.cjs") {
        Ejecutar "$bundledNode\bin\node.exe" @("$bundledNode\node_modules\pnpm\bin\pnpm.cjs", 'install', '--frozen-lockfile')
    } else { throw 'Instala Node.js LTS desde nodejs.org para preparar el visor 3D.' }
}
if (-not $SinModelos) { Ejecutar $pythonExe @('-m', 'app.download', '--engine', 'mini') }
if ($Multivista) { Ejecutar $pythonExe @('-m', 'app.download', '--engine', 'multiview') }
Ejecutar $pythonExe @('-m', 'app.doctor')
Write-Host 'Instalacion terminada. Abre Iniciar.cmd.' -ForegroundColor Green
