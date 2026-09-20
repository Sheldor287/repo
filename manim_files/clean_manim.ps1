# ============================================================
# Clean-Manim.ps1
#
# Cleans obsolete Manim-generated artifacts while preserving
# source files and final rendered media.
# ============================================================

$Root = "C:\Users\Drew\Documents\MyFiles\work\manim_files"

# SAFETY SWITCH
# $true  = show what would be deleted
# $false = actually delete
$DryRun = $false


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

$DeletedFiles = 0
$DeletedDirectories = 0
$KeptFiles = 0


function Remove-Safely {
    param ([System.IO.FileSystemInfo]$Item)

    if ($DryRun) {Write-Host "DELETE: $($Item.FullName)"}
    else {Remove-Item -LiteralPath $Item.FullName -Force -Recurse}

    if ($Item.PSIsContainer) {$script:DeletedDirectories++}
    else {$script:DeletedFiles++}
}


function Get-DirectoryLastWriteTime {
    param ([string]$Path)
    $items = Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if (-not $items) {return [datetime]::MinValue}
    return ($items | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
}



# Validate root
if (-not (Test-Path -LiteralPath $Root)) {
    Write-Host ""
    Write-Host "ERROR: Manim directory was not found:" -ForegroundColor Red
    Write-Host $Root -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit
}


Write-Host ""
Write-Host "============================================"
Write-Host "             MANIM CLEANUP"
Write-Host "============================================"
Write-Host ""
Write-Host "Root:"
Write-Host "  $Root"
Write-Host ""

if ($DryRun) {Write-Host "MODE: DRY RUN - nothing will be deleted" -ForegroundColor Yellow}
else {Write-Host "MODE: DELETE" -ForegroundColor Red}
Write-Host ""


# ============================================================
# 1. Clean partial_movie_files
#
# For every partial_movie_files directory:
#     Keep the newest partial render set for each scene.
#     Delete older sets.
# ============================================================

Write-Host "--------------------------------------------"
Write-Host "Partial movie files"
Write-Host "--------------------------------------------"

$PartialDirectories = Get-ChildItem `
    -Path $Root `
    -Directory `
    -Filter "partial_movie_files" `
    -Recurse `
    -ErrorAction SilentlyContinue


foreach ($PartialDir in $PartialDirectories) {

    # Each child directory represents a partial render set.
    $RenderSets = Get-ChildItem `
        -LiteralPath $PartialDir.FullName `
        -Directory `
        -ErrorAction SilentlyContinue

    if ($RenderSets.Count -le 1) {foreach ($item in $RenderSets) {$script:KeptFiles++} continue}

    # Newest render set based on its contents.
    $RenderSets = $RenderSets | Sort-Object `
        @{Expression = {Get-DirectoryLastWriteTime $_.FullName}; Descending = $true}

    $Newest = $RenderSets | Select-Object -First 1
    $OldSets = $RenderSets | Select-Object -Skip 1

    Write-Host ""
    Write-Host "Scene: $($PartialDir.FullName)"
    Write-Host "KEEP:   $($Newest.Name)"

    $script:KeptFiles++
    foreach ($OldSet in $OldSets) {Remove-Safely $OldSet}
}

# ============================================================
# 2. Clean Manim-generated LaTeX artifacts
#
# Only operates inside directories named "Tex".
#
# KEEP:
#   .log
#
# REMOVE:
#   obsolete generated/intermediate LaTeX artifacts
#
# For now, retain the newest file of each generated artifact
# type within each Tex directory.
# ============================================================

Write-Host ""
Write-Host "--------------------------------------------"
Write-Host "LaTeX artifacts"
Write-Host "--------------------------------------------"

$TexDirectories = Get-ChildItem `
    -Path $Root `
    -Directory `
    -Filter "Tex" `
    -Recurse `
    -ErrorAction SilentlyContinue

$LatexExtensions = @(
    ".tex",
    ".dvi",
    ".aux",
    ".fls",
    ".fdb_latexmk",
    ".xdv",
    ".synctex",
    ".synctex.gz"
)

foreach ($TexDir in $TexDirectories) {

    Write-Host ""
    Write-Host "Directory: $($TexDir.FullName)"

    $Files = Get-ChildItem `
        -LiteralPath $TexDir.FullName `
        -File `
        -Force `
        -ErrorAction SilentlyContinue

    if (-not $Files) {
        continue
    }

    # --------------------------------------------------------
    # Always keep logs.
    # --------------------------------------------------------

    foreach ($File in $Files) {

        if ($File.Extension -ieq ".log") {
            Write-Host "KEEP:   $($File.Name)"
            $script:KeptFiles++
        }
    }

    # --------------------------------------------------------
    # For each artifact type, keep only the newest file.
    # --------------------------------------------------------

    foreach ($Extension in $LatexExtensions) {

        $MatchingFiles = @(
            $Files |
                Where-Object {
                    $_.Extension -ieq $Extension
                } |
                Sort-Object LastWriteTime -Descending
        )

        if ($MatchingFiles.Count -eq 0) {
            continue
        }

        # Keep newest file.
        $Newest = $MatchingFiles[0]

        Write-Host "KEEP:   $($Newest.Name)"
        $script:KeptFiles++

        # Delete older files.
        if ($MatchingFiles.Count -gt 1) {

            $OldFiles = $MatchingFiles | Select-Object -Skip 1

            foreach ($OldFile in $OldFiles) {
                Remove-Safely $OldFile
            }
        }
    }
}


# ============================================================
# 3. Clean Manim-generated SVG files
#
# IMPORTANT:
# We only inspect SVGs underneath the Manim media directory.
#
# SVGs outside media are untouched.
#
# Within each directory, keep the newest SVG and remove
# older generated SVGs.
# ============================================================

Write-Host ""
Write-Host "--------------------------------------------"
Write-Host "Manim SVG files"
Write-Host "--------------------------------------------"


$MediaDirectories = Get-ChildItem `
    -Path $Root `
    -Directory `
    -Filter "media" `
    -Recurse `
    -ErrorAction SilentlyContinue


foreach ($MediaDir in $MediaDirectories) {

    $SvgFiles = Get-ChildItem `
        -LiteralPath $MediaDir.FullName `
        -File `
        -Filter "*.svg" `
        -Recurse `
        -ErrorAction SilentlyContinue

    if (-not $SvgFiles) {continue}


    # Group by directory so unrelated SVG generations in
    # different Manim output directories remain independent.
    $Groups = $SvgFiles | Group-Object DirectoryName


    foreach ($Group in $Groups) {
        $Sorted = $Group.Group |
            Sort-Object LastWriteTime -Descending
        $Newest = $Sorted | Select-Object -First 1
        Write-Host ""
        Write-Host "SVG directory: $($Group.Name)"
        Write-Host "KEEP:   $($Newest.Name)"
        $script:KeptFiles++
        $OldFiles = $Sorted | Select-Object -Skip 1
        foreach ($OldFile in $OldFiles) {Remove-Safely $OldFile}
    }
}


# ============================================================
# 4. Remove Python cache directories underneath manim_files
#
# Manim does not need these to preserve rendered output.
# ============================================================

Write-Host ""
Write-Host "--------------------------------------------"
Write-Host "Python cache directories"
Write-Host "--------------------------------------------"
$CacheDirectories = Get-ChildItem `
    -Path $Root `
    -Directory `
    -Filter "__pycache__" `
    -Recurse `
    -ErrorAction SilentlyContinue
foreach ($CacheDir in $CacheDirectories) {Remove-Safely $CacheDir}
# ============================================================
# 5. Summary
# ============================================================
Write-Host ""
Write-Host "============================================"
Write-Host "                 SUMMARY"
Write-Host "============================================"
Write-Host ""

Write-Host "Files kept:       $KeptFiles"
Write-Host "Files deleted:    $DeletedFiles"
Write-Host "Directories deleted: $DeletedDirectories"

Write-Host ""

if ($DryRun) {

    Write-Host "DRY RUN COMPLETE" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "No files were deleted."
    Write-Host "Review the DELETE entries above."
    Write-Host ""
    Write-Host "When you're satisfied, change:"
    Write-Host ""
    Write-Host '    $DryRun = $true'
    Write-Host ""
    Write-Host "to:"
    Write-Host ""
    Write-Host '    $DryRun = $false'
}
else {Write-Host "CLEANUP COMPLETE" -ForegroundColor Green}
Write-Host ""
Read-Host "Press Enter to exit"