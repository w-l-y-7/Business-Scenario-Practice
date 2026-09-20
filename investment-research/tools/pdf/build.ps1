<#
.SYNOPSIS
  Markdown → PDF，按 CFA 研报的默认版式（A4 纵向、边距 17 mm、正文 10 pt）。

.DESCRIPTION
  本机实测可用的路线：pandoc 3.10 + MiKTeX xelatex + Microsoft YaHei。
  **边距与字号是默认值，不是硬规定** —— 拿到官方排版要求后，官方要求覆盖默认值，
  用 -Margin / -FontSize 传进去即可。字体改 tools/pdf/header.tex（见该文件注释）。

  产物默认落在项目根的 build/ 目录，该目录不入库。

  导出前先过输出门禁（tools/model/gate_check.py）。**门禁没过不要导出。**
  版式检查默认跑（-SkipCheck 可关）：它能挡住超宽表、丢页码、中文断行这些事故。

.EXAMPLE
  # 正式报告
  .\tools\pdf\build.ps1 -InputPath output\investment-report.md

  # 试排样张
  .\tools\pdf\build.ps1 -InputPath tools\pdf\smoke\试排.md
#>
param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [string]$OutputPath,
    [string]$Margin = "17mm",
    [string]$FontSize = "10pt",
    [string]$HeaderPath,
    [switch]$SkipCheck
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not (Test-Path $InputPath)) {
    throw "找不到输入文件：$InputPath"
}
$InputPath = (Resolve-Path $InputPath).Path

if (-not $OutputPath) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($InputPath)
    $OutputPath = Join-Path $root "build\$name.pdf"
}
$outDir = Split-Path -Parent $OutputPath
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Force $outDir | Out-Null
}

if (-not $HeaderPath) { $HeaderPath = Join-Path $PSScriptRoot "header.tex" }
if (-not (Test-Path $HeaderPath)) { throw "找不到 LaTeX 导言区文件：$HeaderPath" }

$pandoc = Get-Command pandoc -ErrorAction SilentlyContinue
if (-not $pandoc) { throw "本机没有 pandoc。装法：winget install --id JohnMacFarlane.Pandoc" }
if (-not (Get-Command xelatex -ErrorAction SilentlyContinue)) {
    throw "本机没有 xelatex（MiKTeX）。装法：winget install --id MiKTeX.MiKTeX"
}

Write-Host "pandoc:  $($pandoc.Source)"
Write-Host "输入:    $InputPath"
Write-Host "输出:    $OutputPath"
Write-Host "版式:    A4 纵向 / 边距 $Margin / 正文 $FontSize / 字体见 header.tex"

# --resource-path 必须给绝对路径：文稿写在 output/ 下，里面的 figures/xxx.png
# 是相对项目根写的，pandoc 默认会按「输入文件所在目录」去找，那样找不到。
$resourcePath = "$root;$root\figures"

$divFilter = Join-Path $PSScriptRoot "divs-to-latex.lua"
if (-not (Test-Path $divFilter)) { throw "找不到 Lua 过滤器：$divFilter" }

# 注意 --from=markdown-yaml_metadata_block：本项目用 --- 包住免责声明原文，
# 不关掉 YAML 元数据解析的话，pandoc 会把它当成元数据块并直接报解析错误。
& pandoc $InputPath `
    -o $OutputPath `
    --from=markdown-yaml_metadata_block `
    --pdf-engine=xelatex `
    --include-in-header=$HeaderPath `
    --resource-path=$resourcePath `
    --lua-filter=$divFilter `
    -V geometry:a4paper `
    -V "geometry:margin=$Margin" `
    -V "fontsize=$FontSize" `
    -V documentclass=article `
    --toc=false

if ($LASTEXITCODE -ne 0) {
    throw "pandoc 退出码 $LASTEXITCODE，PDF 没生成成功。"
}

$info = Get-Item $OutputPath
Write-Host "生成成功：$($info.FullName)（$([math]::Round($info.Length / 1KB, 1)) KB）"

if ($SkipCheck) { return }

Write-Host ""
& python (Join-Path $PSScriptRoot "check_layout.py") $OutputPath --margin ($Margin -replace "mm$", "")
exit $LASTEXITCODE
