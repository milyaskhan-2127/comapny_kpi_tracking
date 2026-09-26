# Productix ERP - module selection and .env reader (Windows hosts)
# ============================================================================
# PowerShell cannot source the POSIX implementation in
# docker/productix-selection.sh, so this file mirrors it. The two MUST stay
# in step: setup_site.ps1 / deploy.ps1 have to resolve PRODUCTIX_APPS to
# exactly the list docker/backend-entrypoint.sh resolves it to for the same
# .env, or a Windows host would install a different set from a Linux one.
#
# Dot-source it from a script in the repo root:
#
#     . "$PSScriptRoot\docker\productix-selection.ps1"
#
# Nothing here names a module. Apps are discovered by globbing
#     <root>/productix_*/productix_*/productix_module.json
# and the only inputs are that glob plus the operator's PRODUCTIX_APPS.
# ============================================================================

function Import-ProductixDotEnv {
    <#
        Read KEY=VALUE lines out of .env without overriding anything already
        in the environment. Precedence: an explicitly exported variable first,
        the file second - so .env is the deployment's configuration while an
        operator can still override a single value for one run.

        This is what makes the manual path agree with `docker compose up`,
        which has always read .env itself: without it, PRODUCTIX_APPS in .env
        was honoured by the container bootstrap and silently ignored here.
    #>
    [CmdletBinding()]
    param([string]$Path = ".env")

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }

    foreach ($raw in Get-Content -LiteralPath $Path) {
        $line = "$raw"
        if ($line -match '^\s*(#|$)') { continue }
        if ($line -notmatch '^([^=]+)=(.*)$') { continue }

        $key = $Matches[1].Trim()
        $val = $Matches[2]

        # Only a name the shell could actually export.
        if ($key -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { continue }

        # Already in the environment - even as an empty string - wins.
        if ([Environment]::GetEnvironmentVariable($key) -ne $null) { continue }

        if ($val.Length -ge 2) {
            $first = $val[0]
            $last = $val[$val.Length - 1]
            if (($first -eq [char]34 -and $last -eq [char]34) -or
                ($first -eq [char]39 -and $last -eq [char]39)) {
                $val = $val.Substring(1, $val.Length - 2)
            }
        }

        # Windows PowerShell will not hold an empty process variable: writing
        # '' here leaves the name unset. That is indistinguishable from `FOO=`
        # for every consumer - both the shell loader and compose's ${FOO:-}
        # expansion treat an empty and an absent value the same - so no
        # workaround is attempted.
        Set-Item -Path "Env:$key" -Value $val
    }
}

function Get-ProductixModuleManifest {
    # <apps-root> <app> -> the module's manifest path, or $null. Having its
    # own productix_module.json is what makes an app a MODULE; frappe and
    # erpnext have none, which is how the bench base stays out of a
    # module selection without naming it here.
    [CmdletBinding()]
    param([string]$AppsRoot, [string]$App)

    if (-not $App) { return $null }
    $hit = @(Get-ChildItem -Path (Join-Path $AppsRoot "$App/*/productix_module.json") -ErrorAction SilentlyContinue |
        Select-Object -First 1)
    if ($hit.Count -gt 0) { return $hit[0].FullName }
    return $null
}

function Get-ProductixManifestList {
    # A JSON array of strings, returned as an array. Matches across lines, so
    # the array in the manifest may be wrapped. Unreadable file or no such
    # key -> empty, never an error: a malformed manifest must not abort an
    # install.
    [CmdletBinding()]
    param([string]$Manifest, [string]$Key)

    if (-not $Manifest -or -not (Test-Path -LiteralPath $Manifest)) { return @() }
    $raw = Get-Content -LiteralPath $Manifest -Raw
    $rx = '"' + [regex]::Escape($Key) + '"\s*:\s*\[([^\]]*)\]'
    $m = [regex]::Match($raw, $rx)
    if (-not $m.Success) { return @() }

    $items = @()
    foreach ($piece in ($m.Groups[1].Value -split ',')) {
        $one = $piece.Trim().Trim([char]34).Trim([char]39)
        if ($one) { $items += $one }
    }
    return $items
}

function Get-ProductixManifestValue {
    # One JSON string value, or $null.
    [CmdletBinding()]
    param([string]$Manifest, [string]$Key)

    if (-not $Manifest -or -not (Test-Path -LiteralPath $Manifest)) { return $null }
    $raw = Get-Content -LiteralPath $Manifest -Raw
    $rx = '"' + [regex]::Escape($Key) + '"\s*:\s*"([^"]*)"'
    $m = [regex]::Match($raw, $rx)
    if ($m.Success) { return $m.Groups[1].Value }
    return $null
}

function Get-ProductixSelection {
    <#
        Resolves the module selection.

        AppsRoot   directory holding the app checkouts (the repo's apps/)
        Requested  the operator's PRODUCTIX_APPS: commas and/or spaces, or
                   "" to mean "every module discovered"
        BenchBase  apps a Frappe site has whether or not any module is
                   selected; a `requires` naming one is satisfied by
                   definition rather than by a folder under AppsRoot.
                   Mirrors PX_BENCH_BASE in docker/productix-selection.sh.

        Returns an object with:
          Platform     the always_enabled manifest ('' when there is none)
          Discovered   every other module found
          Selected     the final, ordered list: platform first, then
                       dependencies, then the rest - ready to install
          Requested    what was asked for, normalised ('' = discovery mode)
          Unavailable  requested modules with no folder under AppsRoot
          DepGaps      modules a `requires` refers to that are not on disk
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$AppsRoot,
        [string]$Requested = '',
        [string[]]$BenchBase = @('frappe', 'erpnext')
    )

    $platform = ''
    $discovered = @()
    foreach ($m in @(Get-ChildItem -Path (Join-Path $AppsRoot 'productix_*/productix_*/productix_module.json') -ErrorAction SilentlyContinue)) {
        $app = $m.Directory.Parent.Name
        if ((Get-Content -LiteralPath $m.FullName -Raw) -match '"always_enabled"\s*:\s*true') {
            $platform = $app
        }
        else {
            $discovered += $app
        }
    }

    # NOTE the name: PowerShell variable names are case-insensitive, so a
    # local called $requested would BE the [string]$Requested parameter - and
    # `$wanted = @()` would then be coerced back to '' by the parameter's
    # type. That silently turned every selection into one empty item.
    $wanted = @()
    if ($Requested) {
        $wanted = @($Requested -split '[,\s]+' | Where-Object { $_ })
    }

    # What was asked for, or everything when nothing was.
    $choice = if ($wanted.Count -gt 0) { $wanted } else { $discovered }

    # --- transitive `requires`, depth first so a dependency is always
    # --- emitted before the module that needs it ---
    $ordered = New-Object System.Collections.Generic.List[string]
    $gaps = New-Object System.Collections.Generic.List[string]

    $visit = $null
    $visit = {
        param([string]$App, [string[]]$Path)

        if ($Path -contains $App) { return }      # circular `requires`
        $next = @($Path) + @($App)

        $manifest = Get-ProductixModuleManifest -AppsRoot $AppsRoot -App $App
        foreach ($dep in (Get-ProductixManifestList -Manifest $manifest -Key 'requires')) {
            if (-not (Test-Path -LiteralPath (Join-Path $AppsRoot $dep) -PathType Container)) {
                # A bench-base app is not missing just because a host checkout
                # does not carry it - only a real module gap is worth a warning.
                if (($BenchBase -notcontains $dep) -and (-not $gaps.Contains($dep))) {
                    [void]$gaps.Add($dep)
                }
                continue
            }
            if (-not (Get-ProductixModuleManifest -AppsRoot $AppsRoot -App $dep)) { continue }
            & $visit $dep $next
        }

        if (-not $ordered.Contains($App)) { [void]$ordered.Add($App) }
    }

    foreach ($app in $choice) { & $visit $app @() }

    # The platform app always leads, whatever the resolution produced.
    $selected = @()
    if ($platform) { $selected += $platform }
    foreach ($app in $ordered) {
        if ($selected -notcontains $app) { $selected += $app }
    }

    # Modules that were named but do not exist on this host.
    $unavailable = @()
    foreach ($app in $wanted) {
        if (-not (Test-Path -LiteralPath (Join-Path $AppsRoot $app) -PathType Container)) {
            $unavailable += $app
        }
    }

    [pscustomobject]@{
        Platform    = $platform
        Discovered  = @($discovered)
        Selected    = @($selected)
        Requested   = @($wanted)
        Unavailable = @($unavailable)
        DepGaps     = @($gaps)
    }
}
