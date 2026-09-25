$ErrorActionPreference = 'Stop'
$exe = 'D:\KimiData\kimi\tasks\2026-09-14\08-32-13-31782a90\pmms-rehearsal\meqlab-wrapper.exe'
$cs  = 'D:\KimiData\kimi\tasks\2026-09-14\08-32-13-31782a90\pmms-rehearsal\meqlab-wrapper.cs'
Remove-Item $exe -Force -ErrorAction SilentlyContinue
try {
    Add-Type -OutputAssembly $exe -OutputType ConsoleApplication -TypeDefinition (Get-Content $cs -Raw -Encoding UTF8)
    if (Test-Path $exe) { Write-Output 'COMPILE_OK' } else { Write-Output 'COMPILE_FAIL_NOEXE' }
} catch {
    Write-Output 'COMPILE_FAIL'
    Write-Output $_.Exception.Message
}
