# support-guard v1.0 — shared support-state guard for 1c-metadata-manage tools
# Adapted from https://github.com/Nikolay-Shirokov/cc-1c-skills (cf-edit.ps1 write-guard,
# meta-info.ps1 read-only status reporting). Dot-source this file, then call
# Assert-EditAllowed (write path) or Get-SupportStatusForPath (read-only status line).
#
# Deviation from upstream: upstream resolves the guard policy from .v8-project.json's
# editingAllowedCheck. Here the policy comes from .dev.env's SUPPORT_EDIT_POLICY
# instead — .dev.env is this project's single source of truth for operational
# parameters (see AGENTS.md / dev-standards-core.md §1), and .v8-project.json in this
# project is documentation-only (no script reads it — see docs/db-manage.md). Same
# directory walk-up algorithm as upstream (up to 20 levels), same default ('deny')
# when the file or field is absent. Everything else (Ext/ParentConfigurations.bin
# parsing, block/flag semantics) is unchanged from upstream — see
# docs/support-manage.md for the full format spec.
#
# Centralized here (unlike upstream, which duplicates this block in every script)
# so all 1c-metadata-manage write/info tools share one implementation.

function Get-RootUuid([string]$xmlPath) {
	if (-not (Test-Path $xmlPath)) { return $null }
	try {
		[xml]$mx = Get-Content -Path $xmlPath -Encoding UTF8
		$el = $mx.DocumentElement.FirstChild
		while ($el -and $el.NodeType -ne 'Element') { $el = $el.NextSibling }
		if ($el) { $u = $el.GetAttribute("uuid"); if ($u) { return $u } }
	} catch {}
	return $null
}

function Find-DevEnv([string]$startDir) {
	$d = $startDir
	for ($i = 0; $i -lt 20 -and $d; $i++) {
		$f = Join-Path $d ".dev.env"
		if (Test-Path $f) { return $f }
		$parent = [System.IO.Path]::GetDirectoryName($d)
		if ($parent -eq $d) { break }
		$d = $parent
	}
	return $null
}

function Get-EditMode([string]$cfgDir) {
	try {
		$envFile = Find-DevEnv (Get-Location).Path
		if (-not $envFile) { $envFile = Find-DevEnv $cfgDir }
		if (-not $envFile) { return 'deny' }
		$m = Select-String -Path $envFile -Pattern '^\s*SUPPORT_EDIT_POLICY\s*=\s*(\S+)' -Encoding UTF8 | Select-Object -First 1
		if (-not $m) { return 'deny' }
		$val = $m.Matches[0].Groups[1].Value.Trim().ToLower()
		if ($val -in @('deny', 'warn', 'off')) { return $val }
		return 'deny'
	} catch { return 'deny' }
}

function Assert-EditAllowed([string]$targetPath, [string]$require) {
	try {
		$rp = $targetPath
		try { $rp = (Resolve-Path $targetPath -ErrorAction Stop).Path } catch {}
		$elemUuid = Get-RootUuid $rp
		$cfgDir = $null; $binPath = $null
		$d = if (Test-Path $rp -PathType Container) { $rp } else { [System.IO.Path]::GetDirectoryName($rp) }
		for ($i = 0; $i -lt 12 -and $d; $i++) {
			if (-not $elemUuid) { $elemUuid = Get-RootUuid "$d.xml" }
			if (-not $cfgDir) {
				$cand = Join-Path (Join-Path $d "Ext") "ParentConfigurations.bin"
				if ((Test-Path $cand) -or (Test-Path (Join-Path $d "Configuration.xml"))) { $cfgDir = $d; $binPath = $cand }
			}
			if ($elemUuid -and $cfgDir) { break }
			$parent = [System.IO.Path]::GetDirectoryName($d)
			if ($parent -eq $d) { break }
			$d = $parent
		}
		# New object (no element file): fall back to config root uuid.
		if (-not $elemUuid -and $cfgDir) { $elemUuid = Get-RootUuid (Join-Path $cfgDir "Configuration.xml") }
		if (-not $binPath -or -not (Test-Path $binPath)) { return }
		$bytes = [System.IO.File]::ReadAllBytes($binPath)
		if ($bytes.Length -le 32) { return }
		$start = 0
		if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { $start = 3 }
		$text = [System.Text.Encoding]::UTF8.GetString($bytes, $start, $bytes.Length - $start)
		$hm = [regex]::Match($text, '^\{6,(\d+),(\d+),')
		if (-not $hm.Success) { return }
		$G = [int]$hm.Groups[1].Value
		$K = [int]$hm.Groups[2].Value
		if ($K -eq 0) { return }
		$best = $null
		if ($elemUuid) {
			$u = [regex]::Escape($elemUuid.ToLower())
			foreach ($m in [regex]::Matches($text, "([0-2]),0,$u")) {
				$f1 = [int]$m.Groups[1].Value
				if ($null -eq $best -or $f1 -lt $best) { $best = $f1 }
			}
		}
		$blocked = $false; $code = ""; $reason = ""
		if ($G -eq 1) { $blocked = $true; $code = "capability-off"; $reason = "возможность изменения конфигурации выключена (вся конфигурация read-only)" }
		elseif ($require -eq 'removed') {
			if ($null -ne $best -and $best -ne 2) { $blocked = $true; $code = "not-removed"; $reason = "объект не снят с поддержки — удаление сломает обновления" }
		}
		else {
			if ($null -ne $best -and $best -eq 0) { $blocked = $true; $code = "locked"; $reason = "объект на замке — редактирование сломает обновления" }
		}
		if (-not $blocked) { return }
		$mode = Get-EditMode $cfgDir
		if ($mode -eq 'off') { return }
		# Use Console.Error (not Write-Error) — under ErrorActionPreference=Stop the
		# latter throws and would be swallowed by this function's own catch.
		if ($mode -eq 'warn') { [Console]::Error.WriteLine("[support-guard] ПРЕДУПРЕЖДЕНИЕ: $reason. Цель: $rp"); return }
		$head = "[support-guard] Редактирование отклонено: это объект типовой конфигурации на поддержке поставщика, прямое редактирование молча сломает будущие обновления."
		$cfe = "Рекомендуемый путь: внести доработку в расширение (навыки cfe-borrow / cfe-patch-method) — состояние поддержки менять не нужно, обновления вендора сохраняются."
		$offNote = "Снять проверку для этой базы: SUPPORT_EDIT_POLICY=warn|off в .dev.env."
		if ($code -eq "capability-off") {
			$state = "Состояние: у всей конфигурации выключена возможность изменения (режим read-only «из коробки») — поэтому объект «$rp» редактировать нельзя."
			$fix = "Либо снять защиту явно (навык support-edit, два шага):`n  1. support-edit -Path ""$cfgDir"" -Capability on — включить возможность изменения (объекты пока остаются на замке);`n  2. support-edit -Path ""$rp"" -Set editable — открыть этот объект для редактирования.`n  Изменение применяется в базу полной загрузкой выгрузки и обходит механизм обновлений вендора."
		} elseif ($code -eq "not-removed") {
			$state = "Состояние: объект «$rp» на поддержке (не снят с поддержки) — его удаление разорвёт обновления вендора."
			$fix = "Либо сначала снять объект с поддержки, затем удалять:`n  support-edit -Path ""$rp"" -Set off-support — объект уходит из-под обновлений, после этого удаление безопасно."
		} else {
			$state = "Состояние: объект «$rp» на замке (возможность изменения конфигурации включена, но сам объект не редактируется)."
			$fix = "Либо разрешить редактирование этого объекта (навык support-edit, выбрать одно):`n  support-edit -Path ""$rp"" -Set editable — редактировать и дальше получать обновления вендора (возможны конфликты слияния);`n  support-edit -Path ""$rp"" -Set off-support — снять с поддержки: обновления по объекту больше не приходят."
		}
		[Console]::Error.WriteLine("$head`n$state`n$cfe`n$fix`n$offNote")
		exit 1
	} catch { return }
}

function Get-SupportStatusForPath([string]$objPath) {
	try {
		$rp = $objPath
		try { $rp = (Resolve-Path $objPath -ErrorAction Stop).Path } catch {}
		$elemUuid = Get-RootUuid $rp
		$binPath = $null
		$d = if (Test-Path $rp -PathType Container) { $rp } else { [System.IO.Path]::GetDirectoryName($rp) }
		for ($i = 0; $i -lt 8 -and $d; $i++) {
			if (-not $elemUuid) { $elemUuid = Get-RootUuid "$d.xml" }
			$cand = Join-Path (Join-Path $d "Ext") "ParentConfigurations.bin"
			if ((Test-Path $cand) -or (Test-Path (Join-Path $d "Configuration.xml"))) { $binPath = $cand; break }
			$parent = [System.IO.Path]::GetDirectoryName($d)
			if ($parent -eq $d) { break }
			$d = $parent
		}
		if (-not $binPath -or -not (Test-Path $binPath)) { return "не на поддержке" }
		$bytes = [System.IO.File]::ReadAllBytes($binPath)
		if ($bytes.Length -le 32) { return "снято с поддержки (правки свободны)" }
		$start = 0
		if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { $start = 3 }
		$text = [System.Text.Encoding]::UTF8.GetString($bytes, $start, $bytes.Length - $start)
		$h = [regex]::Match($text, '^\{6,(\d+),(\d+),')
		if (-not $h.Success) { return "не на поддержке" }
		$G = [int]$h.Groups[1].Value
		$K = [int]$h.Groups[2].Value
		if ($K -eq 0) { return "снято с поддержки (правки свободны)" }
		if ($G -eq 1) { return "конфигурация read-only (возможность изменения выключена) — правки невозможны без включения" }
		if (-not $elemUuid) { return "не на поддержке" }
		$u = [regex]::Escape($elemUuid.ToLower())
		$best = $null
		foreach ($m in [regex]::Matches($text, "([0-2]),0,$u")) {
			$f1 = [int]$m.Groups[1].Value
			if ($null -eq $best -or $f1 -lt $best) { $best = $f1 }
		}
		if ($null -eq $best) { return "не на поддержке" }
		switch ($best) {
			0 { return "на замке — прямая правка сломает обновления; дорабатывай через cfe-* либо включи редактирование объекта" }
			1 { return "редактируется с сохранением поддержки" }
			2 { return "снято с поддержки (правки свободны)" }
		}
		return "не на поддержке"
	} catch { return "не на поддержке" }
}
