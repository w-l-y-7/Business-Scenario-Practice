# SessionStart hook for the superpowers skills.
# Reads skills/using-superpowers/SKILL.md and injects it into the session
# context as hookSpecificOutput.additionalContext (the shape Claude Code reads).

$ErrorActionPreference = 'Stop'

$skillPath = Join-Path $PSScriptRoot '..\skills\using-superpowers\SKILL.md'

if (Test-Path $skillPath) {
    $content = Get-Content $skillPath -Raw -Encoding UTF8
} else {
    $content = "Error reading using-superpowers skill at $skillPath"
}

$context = @"
<EXTREMELY_IMPORTANT>
You have superpowers.

**Below is the full content of your 'superpowers:using-superpowers' skill - your introduction to using skills. For all other skills, use the 'Skill' tool:**

$content
</EXTREMELY_IMPORTANT>
"@

$payload = @{
    hookSpecificOutput = @{
        hookEventName     = 'SessionStart'
        additionalContext = $context
    }
}

$payload | ConvertTo-Json -Depth 5 -Compress
