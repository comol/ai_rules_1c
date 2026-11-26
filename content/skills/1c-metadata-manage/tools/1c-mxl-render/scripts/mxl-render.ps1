# mxl-render v1.1 - draw a 1C spreadsheet layout (Template.xml) as a PNG sketch
# and estimate how its width prints on A4.
# Local tool of this ruleset, not vendored from cc-1c-skills.
#
# The picture is a preview, not the platform's rendering: column widths, row heights,
# merges, borders, fills, fonts, cell texts, parameters (<Name>), templates ([Name]) and
# named areas are drawn from the XML; pictures, charts, rotated text, header / footer
# and conditional appearance are not.
#
# Scale. The unit of a column width in the XML is not documented (ColumnWidth in the
# language is in "average characters"). It is drawn as one pixel at 96 dpi (0.75 pt,
# 0.26 mm) - the scale at which the static texts of ZUP's vendor layouts fit the table
# cells they sit in (95% of 2148 measured cells). Row height in the XML is points x 4
# (RowHeight is in points; single-line rows of a 9-10 pt font are 60-75 in the XML).
# Fonts are drawn in points.
#
# Width. The report gives the width in units and an estimate in millimetres from that
# scale - not checked against the 1C print preview. It compares the units with the
# targets mxl-compile writes new layouts to (A4-portrait 540, A4-landscape 780) and,
# separately, estimates the print on A4 from the print settings the layout stores
# (orientation, fitToPage, scale, margins); with fitToPage it gives the reduction.
#
# Windows only: drawing uses System.Drawing (GDI+). pwsh on Linux / macOS has no GDI+,
# and the run is refused before anything is written.
#
# NOTE: this file is deliberately pure ASCII (Windows PowerShell 5.1 reads a BOM-less
# .ps1 as ANSI).
[CmdletBinding(PositionalBinding=$false)]
param(
	[Parameter(Position=0)]
	[Alias('Path')]
	[string]$TemplatePath,
	[string]$ProcessorName,
	[string]$TemplateName,
	[string]$SrcDir = "src",
	[string]$OutputPath,
	[string]$Area,
	[double]$Zoom = 1.0,
	[int]$MaxHeight = 16000
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Stop-MxrRun([string]$message) {
	[Console]::Error.WriteLine($message)
	exit 1
}

# --- Platform ---

if ($PSVersionTable.PSEdition -eq 'Core' -and -not $IsWindows) {
	Stop-MxrRun "mxl-render needs Windows: it draws with System.Drawing (GDI+), which .NET does not provide on this OS. Nothing was written. mxl-info gives the structure as text."
}
if ($Zoom -le 0 -or $Zoom -gt 4) { Stop-MxrRun "-Zoom must be greater than 0 and at most 4" }
if ($MaxHeight -lt 200) { Stop-MxrRun "-MaxHeight must be at least 200 pixels" }

# The rest is one script block, dot-sourced so that it runs in this scope. PowerShell compiles
# a script before it runs any of it, and on Linux / macOS compiling a System.Drawing enum
# constant already throws (PlatformNotSupportedException): written inline, the check above
# would never be reached. A script block literal is compiled only when it is invoked.
. {
	# --- Resolve template path (same rules as mxl-validate) ---

	if (-not $TemplatePath) {
		if (-not $ProcessorName -or -not $TemplateName) {
			Stop-MxrRun "Specify -TemplatePath or both -ProcessorName and -TemplateName"
		}
		$TemplatePath = Join-Path (Join-Path (Join-Path (Join-Path (Join-Path $SrcDir $ProcessorName) "Templates") $TemplateName) "Ext") "Template.xml"
	}
	if (Test-Path $TemplatePath -PathType Container) {
		$TemplatePath = Join-Path (Join-Path $TemplatePath "Ext") "Template.xml"
	}
	if (-not (Test-Path $TemplatePath)) {
		$fn = [System.IO.Path]::GetFileName($TemplatePath)
		if ($fn -eq "Template.xml") {
			$c = Join-Path (Join-Path (Split-Path $TemplatePath) "Ext") $fn
			if (Test-Path $c) { $TemplatePath = $c }
		}
	}
	# The descriptor Templates/<Name>.xml exists as a file of its own, so it is redirected whether
	# or not the given path exists.
	if ($TemplatePath.EndsWith(".xml") -and [System.IO.Path]::GetFileName($TemplatePath) -ne "Template.xml") {
		$stem = [System.IO.Path]::GetFileNameWithoutExtension($TemplatePath)
		$dir = Split-Path $TemplatePath
		$c = Join-Path (Join-Path (Join-Path $dir $stem) "Ext") "Template.xml"
		if (Test-Path $c) { $TemplatePath = $c }
	}
	if (-not (Test-Path $TemplatePath)) { Stop-MxrRun "File not found: $TemplatePath" }
	$resolvedPath = (Resolve-Path -LiteralPath $TemplatePath).ProviderPath

	# Owner and template names for the default file name: .../<Owner>/Templates/<Name>/Ext/Template.xml
	$templateDir = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetDirectoryName($resolvedPath))
	$templateLabel = [System.IO.Path]::GetFileName($templateDir)
	$ownerDir = [System.IO.Path]::GetDirectoryName($templateDir)
	if ($ownerDir -and [System.IO.Path]::GetFileName($ownerDir) -eq 'Templates') {
		$templateLabel = [System.IO.Path]::GetFileName([System.IO.Path]::GetDirectoryName($ownerDir)) + "." + $templateLabel
	}
	if (-not $templateLabel) { $templateLabel = "Template" }

	# --- Load XML ---

	$xmlDoc = New-Object System.Xml.XmlDocument
	$xmlDoc.PreserveWhitespace = $false
	try {
		$xmlDoc.Load($resolvedPath)
	} catch {
		$ex = $_.Exception
		while ($ex.InnerException) { $ex = $ex.InnerException }
		Stop-MxrRun "[ERROR] Cannot read XML: $($ex.Message)"
	}
	$root = $xmlDoc.DocumentElement
	if ($root.get_LocalName() -ne 'document' -or $root.get_NamespaceURI() -ne 'http://v8.1c.ru/8.2/data/spreadsheet') {
		Stop-MxrRun "Not a spreadsheet document layout (root <$($root.get_Name())>): $resolvedPath"
	}
	$ns = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
	$ns.AddNamespace("d", "http://v8.1c.ru/8.2/data/spreadsheet")
	$ns.AddNamespace("v8", "http://v8.1c.ru/8.1/data/core")
	$ns.AddNamespace("v8ui", "http://v8.1c.ru/8.1/data/ui")
	$xsiNs = "http://www.w3.org/2001/XMLSchema-instance"

	$inv = [System.Globalization.CultureInfo]::InvariantCulture

	function Get-MxrText($node, [string]$xpath) {
		$n = $node.SelectSingleNode($xpath, $ns)
		if ($n) { return $n.InnerText }
		return $null
	}

	function ConvertTo-MxrNumber([string]$s, [double]$default) {
		$d = 0.0
		if ($s -and [double]::TryParse($s, [System.Globalization.NumberStyles]::Float, $inv, [ref]$d)) { return $d }
		return $default
	}

	$lang = Get-MxrText $root "d:languageSettings/d:currentLanguage"
	if (-not $lang) { $lang = 'ru' }

	# --- Palettes: fonts and lines are 0-based, formats 1-based ---

	$fontDefs = New-Object System.Collections.Generic.List[object]
	foreach ($fn in $root.SelectNodes("d:font", $ns)) {
		$face = $fn.GetAttribute("faceName")
		$size = ConvertTo-MxrNumber $fn.GetAttribute("height") 0
		$fontDefs.Add(@{
			Face      = $(if ($face) { $face } else { 'Arial' })
			Size      = $(if ($size -gt 0) { $size } else { 10.0 })
			Bold      = ($fn.GetAttribute("bold") -eq 'true')
			Italic    = ($fn.GetAttribute("italic") -eq 'true')
			Underline = ($fn.GetAttribute("underline") -eq 'true')
			Strikeout = ($fn.GetAttribute("strikeout") -eq 'true')
			IsRef     = [bool]$fn.GetAttribute("ref")
		})
	}

	$lineDefs = New-Object System.Collections.Generic.List[object]
	foreach ($ln in $root.SelectNodes("d:line", $ns)) {
		$st = $ln.SelectSingleNode("v8ui:style", $ns)
		$w = 1
		[void][int]::TryParse($ln.GetAttribute("width"), [ref]$w)
		if ($w -lt 1) { $w = 1 }
		$lineDefs.Add(@{ Width = $w; Style = $(if ($st) { $st.InnerText } else { 'Solid' }) })
	}

	$colorTags = @{ backColor = 1; textColor = 1; borderColor = 1 }
	$formats = New-Object System.Collections.Generic.List[object]
	foreach ($fm in $root.SelectNodes("d:format", $ns)) {
		$p = @{}
		foreach ($ch in $fm.ChildNodes) {
			if ($ch.NodeType -ne [System.Xml.XmlNodeType]::Element) { continue }
			if ($ch.SelectNodes('*').Count -gt 0) { continue }
			$tag = $ch.get_LocalName()
			$val = $ch.InnerText
			if ($colorTags.ContainsKey($tag) -and $val -like '*:*' -and $val -notlike 'style:*') {
				$prefix = $val.Substring(0, $val.IndexOf(':'))
				$uri = $ch.GetNamespaceOfPrefix($prefix)
				if ($uri -like '*ui/colors/web' -or $uri -like '*ui/colors/windows') {
					$val = 'named:' + $val.Substring($val.IndexOf(':') + 1)
				}
			}
			$p[$tag] = $val
		}
		$formats.Add($p)
	}

	function Get-MxrFormat([int]$index) {
		if ($index -ge 1 -and $index -le $formats.Count) { return $formats[$index - 1] }
		return $null
	}

	# A format shows on paper when it fills the cell or draws a line that is not None.
	function Test-MxrVisibleFormat($fmt) {
		if (-not $fmt) { return $false }
		if ($fmt.ContainsKey('backColor')) { return $true }
		foreach ($k in 'border', 'leftBorder', 'topBorder', 'rightBorder', 'bottomBorder') {
			if (-not $fmt.ContainsKey($k)) { continue }
			$li = [int]$fmt[$k]
			if ($li -ge 0 -and $li -lt $lineDefs.Count -and $lineDefs[$li].Style -ne 'None') { return $true }
		}
		return $false
	}

	$defFmtIdx = [int](ConvertTo-MxrNumber (Get-MxrText $root "d:defaultFormatIndex") 0)
	$defFmt = Get-MxrFormat $defFmtIdx
	# 72 is the platform's default column width: the default format of 1455 of 1461 ZUP layouts.
	$defaultWidth = 72.0
	if ($defFmt -and $defFmt.ContainsKey('width')) {
		$w = ConvertTo-MxrNumber $defFmt['width'] 0
		if ($w -gt 0) { $defaultWidth = $w }
	}

	# --- Column sets: the one without <id> is the default ---

	$sets = @{}
	foreach ($cn in $root.SelectNodes("d:columns", $ns)) {
		$id = Get-MxrText $cn "d:id"
		if (-not $id) { $id = '' }
		$fmtIdx = @{}
		foreach ($ci in $cn.SelectNodes("d:columnsItem", $ns)) {
			$fmtIdx[[int](Get-MxrText $ci "d:index")] = [int](ConvertTo-MxrNumber (Get-MxrText $ci "d:column/d:formatIndex") 0)
		}
		$sets[$id] = @{ Id = $id; Size = [int](ConvertTo-MxrNumber (Get-MxrText $cn "d:size") 0); FmtIdx = $fmtIdx; Used = 0; Rows = 0 }
	}
	if (-not $sets.ContainsKey('')) { $sets[''] = @{ Id = ''; Size = 0; FmtIdx = @{}; Used = 0; Rows = 0 } }

	function Get-MxrSet([string]$id) {
		if ($id -and $sets.ContainsKey($id)) { return $sets[$id] }
		return $sets['']
	}

	# --- Rows and cells ---

	$rows = @{}
	$maxRow = -1
	$cellPictures = 0
	foreach ($ri in $root.SelectNodes("d:rowsItem", $ns)) {
		$idx = [int](ConvertTo-MxrNumber (Get-MxrText $ri "d:index") 0)
		$to = [int](ConvertTo-MxrNumber (Get-MxrText $ri "d:indexTo") $idx)
		$rn = $ri.SelectSingleNode("d:row", $ns)
		if (-not $rn) { continue }
		$rowFmt = [int](ConvertTo-MxrNumber (Get-MxrText $rn "d:formatIndex") 0)
		$cid = Get-MxrText $rn "d:columnsID"
		if (-not $cid) { $cid = '' }
		$set = Get-MxrSet $cid
		$cells = @{}
		$col = -1
		foreach ($cg in $rn.SelectNodes("d:c", $ns)) {
			$iT = Get-MxrText $cg "d:i"
			if ($iT) { $col = [int]$iT } else { $col++ }
			$cc = $cg.SelectSingleNode("d:c", $ns)
			if (-not $cc) { continue }
			$text = $null
			$items = $cc.SelectNodes("d:tl/v8:item", $ns)
			if ($items.Count -gt 0) {
				foreach ($it in $items) {
					if ((Get-MxrText $it "v8:lang") -eq $lang) { $text = Get-MxrText $it "v8:content"; break }
				}
				if ($null -eq $text) { $text = Get-MxrText $items[0] "v8:content" }
			}
			$f = [int](ConvertTo-MxrNumber (Get-MxrText $cc "d:f") 0)
			$cells[$col] = @{
				F     = $f
				Param = Get-MxrText $cc "d:parameter"
				Text  = $text
				Note  = ($null -ne $cc.SelectSingleNode("d:note", $ns))
			}
			$cf = Get-MxrFormat $f
			if ($cf -and $cf.ContainsKey('picIndex')) { $cellPictures++ }
			# Only what shows extends the layout: vendor layouts keep format-only cells far past
			# the column count (SZV-KORR: 13 columns, cells up to the 78th).
			if (($text -or $cells[$col].Param -or (Test-MxrVisibleFormat $cf)) -and $col + 1 -gt $set.Used) { $set.Used = $col + 1 }
		}
		for ($r = $idx; $r -le $to; $r++) { $rows[$r] = @{ Fmt = $rowFmt; Set = $set.Id; Cells = $cells } }
		$set.Rows += ($to - $idx + 1)
		if ($to -gt $maxRow) { $maxRow = $to }
	}

	$docHeight = [int](ConvertTo-MxrNumber (Get-MxrText $root "d:height") 0)
	$rowCount = [math]::Max($docHeight, $maxRow + 1)

	# --- Merges: <w>/<h> count the columns / rows beyond the first ---

	$mergeAt = @{}
	$covered = @{}
	foreach ($mn in $root.SelectNodes("d:merge", $ns)) {
		$r = [int](ConvertTo-MxrNumber (Get-MxrText $mn "d:r") 0)
		$c = [int](ConvertTo-MxrNumber (Get-MxrText $mn "d:c") 0)
		$w = [int](ConvertTo-MxrNumber (Get-MxrText $mn "d:w") 0)
		$h = [int](ConvertTo-MxrNumber (Get-MxrText $mn "d:h") 0)
		# A merge without <columnsID> lies in whatever column set its row uses (SZV-KORR merges
		# rows of an extra set that way); one with it, only in that set.
		$cid = Get-MxrText $mn "d:columnsID"
		if (-not $cid) { $cid = '' }
		# A merge not bound to a cell (whole height / width) has no extent here; it is not drawn.
		if ($r -lt 0 -or $c -lt 0 -or $w -lt 0 -or $h -lt 0) { continue }
		$mergeAt["$r|$c"] = @{ W = $w; H = $h; Set = $cid }
		for ($rr = $r; $rr -le $r + $h; $rr++) {
			for ($cc = $c; $cc -le $c + $w; $cc++) {
				if ($rr -eq $r -and $cc -eq $c) { continue }
				$covered["$rr|$cc"] = $cid
			}
		}
		if ($cid) { $set = Get-MxrSet $cid }
		elseif ($rows.ContainsKey($r)) { $set = Get-MxrSet $rows[$r].Set }
		else { $set = $sets[''] }
		if ($c + $w + 1 -gt $set.Used) { $set.Used = $c + $w + 1 }
	}

	function Get-MxrMerge([int]$r, [int]$c, [string]$setId) {
		$m = $mergeAt["$r|$c"]
		if ($m -and ($m.Set -eq '' -or $m.Set -eq $setId)) { return $m }
		return $null
	}
	function Test-MxrCovered([int]$r, [int]$c, [string]$setId) {
		$k = "$r|$c"
		if (-not $covered.ContainsKey($k)) { return $false }
		$cv = $covered[$k]
		return ($cv -eq '' -or $cv -eq $setId)
	}

	# --- Named items ---

	$areas = New-Object System.Collections.Generic.List[object]
	$drawingNames = @{}
	foreach ($ni in $root.SelectNodes("d:namedItem", $ns)) {
		$xt = $ni.GetAttribute("type", $xsiNs)
		$name = Get-MxrText $ni "d:name"
		if ($xt -eq 'NamedItemCells') {
			$an = $ni.SelectSingleNode("d:area", $ns)
			if (-not $an) { continue }
			$cid = Get-MxrText $an "d:columnsID"
			$a = @{
				Name = $name
				Type = Get-MxrText $an "d:type"
				R1   = [int](ConvertTo-MxrNumber (Get-MxrText $an "d:beginRow") -1)
				R2   = [int](ConvertTo-MxrNumber (Get-MxrText $an "d:endRow") -1)
				C1   = [int](ConvertTo-MxrNumber (Get-MxrText $an "d:beginColumn") -1)
				C2   = [int](ConvertTo-MxrNumber (Get-MxrText $an "d:endColumn") -1)
				Set  = $(if ($cid) { $cid } else { '' })
			}
			$areas.Add($a)
			if ($a.Type -ne 'Rows' -and $a.C2 -ge 0) {
				$set = Get-MxrSet $a.Set
				if ($a.C2 + 1 -gt $set.Used) { $set.Used = $a.C2 + 1 }
			}
		} elseif ($xt -eq 'NamedItemDrawing') {
			$drawingNames[(Get-MxrText $ni "d:drawingID")] = $name
		}
	}

	$drawings = New-Object System.Collections.Generic.List[object]
	foreach ($dr in $root.SelectNodes("d:drawing", $ns)) {
		$id = Get-MxrText $dr "d:id"
		$drawings.Add(@{
			Type = $(if (Get-MxrText $dr "d:drawingType") { Get-MxrText $dr "d:drawingType" } else { 'Picture' })
			Name = $drawingNames[$id]
			R1 = [int](ConvertTo-MxrNumber (Get-MxrText $dr "d:beginRow") 0)
			R2 = [int](ConvertTo-MxrNumber (Get-MxrText $dr "d:endRow") 0)
			C1 = [int](ConvertTo-MxrNumber (Get-MxrText $dr "d:beginColumn") 0)
			C2 = [int](ConvertTo-MxrNumber (Get-MxrText $dr "d:endColumn") 0)
			R1o = (ConvertTo-MxrNumber (Get-MxrText $dr "d:beginRowOffset") 0)
			R2o = (ConvertTo-MxrNumber (Get-MxrText $dr "d:endRowOffset") 0)
			C1o = (ConvertTo-MxrNumber (Get-MxrText $dr "d:beginColumnOffset") 0)
			C2o = (ConvertTo-MxrNumber (Get-MxrText $dr "d:endColumnOffset") 0)
		})
	}

	# --- Column widths (units) per set ---

	foreach ($set in $sets.Values) {
		$n = [math]::Max($set.Size, $set.Used)
		$widths = New-Object double[] $n
		for ($i = 0; $i -lt $n; $i++) {
			$wv = 0
			if ($set.FmtIdx.ContainsKey($i)) {
				$cf = Get-MxrFormat $set.FmtIdx[$i]
				if ($cf -and $cf.ContainsKey('width')) { $wv = ConvertTo-MxrNumber $cf['width'] 0 }
			}
			$widths[$i] = $(if ($wv -gt 0) { $wv } else { $defaultWidth })
		}
		$set.Widths = $widths
	}

	# --- Width verdict (whole layout, independent of -Area) ---

	$pageTargets = [ordered]@{ "A4-portrait" = 540; "A4-landscape" = 780 }
	$docWidth = 0.0
	$setReport = New-Object System.Collections.Generic.List[string]
	foreach ($set in ($sets.Values | Sort-Object { $_.Id })) {
		if ($set.Rows -eq 0 -and $set.Id -ne '') { continue }
		$used = [math]::Min($set.Used, $set.Widths.Length)
		$sum = 0.0
		for ($i = 0; $i -lt $used; $i++) { $sum += $set.Widths[$i] }
		if ($sum -gt $docWidth) { $docWidth = $sum }
		$label = $(if ($set.Id) { "column set $($set.Id.Substring(0, [math]::Min(8, $set.Id.Length)))..." } else { "default column set" })
		$setReport.Add(("  {0}: {1} units ({2} of {3} columns used, {4} rows)" -f $label, [math]::Round($sum), $used, $set.Widths.Length, $set.Rows))
	}

	# --- Rows to draw ---

	$r0 = 0
	$r1 = $rowCount - 1
	$focus = $null
	if ($Area) {
		$focus = $areas | Where-Object { $_.Name -eq $Area } | Select-Object -First 1
		if (-not $focus) {
			$names = ($areas | ForEach-Object { $_.Name }) -join ', '
			Stop-MxrRun "Area '$Area' not found. Named areas: $names"
		}
		if ($focus.Type -ne 'Columns' -and $focus.R1 -ge 0) {
			$r0 = $focus.R1
			$r1 = [math]::Min($focus.R2, $rowCount - 1)
		}
	}

	# Zoom so that the picture stays below 15000 pixels wide.
	$maxUnits = 0.0
	foreach ($set in $sets.Values) {
		$s = 0.0
		foreach ($wv in $set.Widths) { $s += $wv }
		if ($s -gt $maxUnits) { $maxUnits = $s }
	}
	# Scale: a width unit is drawn as one pixel at 96 dpi (0.75 pt) and a height unit as a
	# quarter of a point (see the header). A very wide layout is zoomed out to stay readable.
	$zoomEff = $Zoom
	if ($maxUnits * $zoomEff -gt 15000) { $zoomEff = 15000 / $maxUnits }
	$pxW = $zoomEff
	$pxPt = (96.0 / 72.0) * $zoomEff

	Add-Type -AssemblyName System.Drawing

	foreach ($set in $sets.Values) {
		$x = New-Object double[] ($set.Widths.Length + 1)
		for ($i = 0; $i -lt $set.Widths.Length; $i++) { $x[$i + 1] = $x[$i] + $set.Widths[$i] * $pxW }
		$set.X = $x
	}

	# --- Fonts and effective formats ---

	$fontCache = @{}
	function Get-MxrFont($fmt) {
		$idx = -1
		if ($fmt -and $fmt.ContainsKey('font')) { $idx = [int]$fmt['font'] }
		elseif ($defFmt -and $defFmt.ContainsKey('font')) { $idx = [int]$defFmt['font'] }
		$key = "$idx"
		if ($fontCache.ContainsKey($key)) { return $fontCache[$key] }
		$face = 'Arial'; $size = 10.0
		$style = [System.Drawing.FontStyle]::Regular
		if ($idx -ge 0 -and $idx -lt $fontDefs.Count) {
			$d = $fontDefs[$idx]
			$face = $d.Face; $size = $d.Size
			if ($d.Bold) { $style = $style -bor [System.Drawing.FontStyle]::Bold }
			if ($d.Italic) { $style = $style -bor [System.Drawing.FontStyle]::Italic }
			if ($d.Underline) { $style = $style -bor [System.Drawing.FontStyle]::Underline }
			if ($d.Strikeout) { $style = $style -bor [System.Drawing.FontStyle]::Strikeout }
		}
		$emPx = [single]([math]::Max(1.0, $size * $pxPt))
		try {
			$font = New-Object System.Drawing.Font($face, $emPx, $style, [System.Drawing.GraphicsUnit]::Pixel)
		} catch {
			$font = New-Object System.Drawing.Font('Arial', $emPx, $style, [System.Drawing.GraphicsUnit]::Pixel)
		}
		$fontCache[$key] = $font
		return $font
	}

	# A cell's own format, else its row's, else its column's: the platform stores a whole
	# format per owner, so properties are not mixed across owners.
	function Get-MxrCellFormat($row, $set, [int]$col) {
		if ($row) {
			$cell = $row.Cells[$col]
			if ($cell -and $cell.F -gt 0) { return (Get-MxrFormat $cell.F) }
			if ($row.Fmt -gt 0) {
				$rf = Get-MxrFormat $row.Fmt
				if ($rf) { return $rf }
			}
		}
		if ($set.FmtIdx.ContainsKey($col)) { return (Get-MxrFormat $set.FmtIdx[$col]) }
		return $null
	}

	function Get-MxrContent($cell, $fmt) {
		if (-not $cell) { return $null }
		$fill = $null
		if ($fmt) { $fill = $fmt['fillType'] }
		if ($fill -eq 'Parameter' -and $cell.Param) { return "<" + $cell.Param + ">" }
		if ($cell.Text) { return $cell.Text }
		if ($cell.Param) { return "<" + $cell.Param + ">" }
		return $null
	}

	$styleColorCount = 0
	function Get-MxrColor([string]$value, $fallback, $styleColor) {
		if (-not $value) { return $fallback }
		if ($value -match '^#[0-9A-Fa-f]{6}$') { return [System.Drawing.ColorTranslator]::FromHtml($value) }
		if ($value -like 'named:*') {
			$cv = [System.Drawing.Color]::FromName($value.Substring(6))
			if ($cv.IsKnownColor) { return $cv }
			return $fallback
		}
		if ($value -like 'style:*') {
			$script:styleColorCount++
			return $styleColor
		}
		return $fallback
	}

	$measureBmp = New-Object System.Drawing.Bitmap(1, 1)
	$measure = [System.Drawing.Graphics]::FromImage($measureBmp)
	$measure.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
	$pad = [math]::Max(1.0, 2.0 * $zoomEff)

	function New-MxrStringFormat($fmt, [bool]$wrap) {
		$sf = New-Object System.Drawing.StringFormat
		$h = $null; $v = $null
		if ($fmt) { $h = $fmt['horizontalAlignment']; $v = $fmt['verticalAlignment'] }
		switch ($h) {
			'Center' { $sf.Alignment = [System.Drawing.StringAlignment]::Center }
			'Right'  { $sf.Alignment = [System.Drawing.StringAlignment]::Far }
			default  { $sf.Alignment = [System.Drawing.StringAlignment]::Near }
		}
		switch ($v) {
			'Top'    { $sf.LineAlignment = [System.Drawing.StringAlignment]::Near }
			'Center' { $sf.LineAlignment = [System.Drawing.StringAlignment]::Center }
			default  { $sf.LineAlignment = [System.Drawing.StringAlignment]::Far }
		}
		if (-not $wrap) { $sf.FormatFlags = [System.Drawing.StringFormatFlags]::NoWrap }
		$sf.Trimming = [System.Drawing.StringTrimming]::None
		return $sf
	}

	# --- Row heights: an explicit row height is points x 4; otherwise the row fits its text ---

	$hiddenRows = 0
	$rowHeight = @{}
	$minPx = (New-Object System.Drawing.Font('Arial', [single](10 * $pxPt), [System.Drawing.GraphicsUnit]::Pixel)).GetHeight() + 3 * $pad
	foreach ($r in $r0..$r1) {
		$row = $rows[$r]
		$set = Get-MxrSet $(if ($row) { $row.Set } else { '' })
		$rf = $null
		if ($row -and $row.Fmt -gt 0) { $rf = Get-MxrFormat $row.Fmt }
		if ($rf -and $rf['hidden'] -eq 'true') { $rowHeight[$r] = 0.0; $hiddenRows++; continue }
		$hPt = 0.0
		if ($rf -and $rf.ContainsKey('height')) { $hPt = ConvertTo-MxrNumber $rf['height'] 0 }
		if ($hPt -gt 0) { $rowHeight[$r] = $hPt / 4.0 * $pxPt; continue }
		$h = $minPx
		if ($row) {
			foreach ($col in $row.Cells.Keys) {
				if (Test-MxrCovered $r $col $set.Id) { continue }
				$m = Get-MxrMerge $r $col $set.Id
				if ($m -and $m.H -gt 0) { continue }
				$fmt = Get-MxrCellFormat $row $set $col
				$font = Get-MxrFont $fmt
				$lh = $font.GetHeight() + 3 * $pad
				$content = Get-MxrContent $row.Cells[$col] $fmt
				if ($content -and $fmt -and $fmt['textPlacement'] -eq 'Wrap' -and $col -lt $set.Widths.Length) {
					$c2 = $col
					if ($m) { $c2 = [math]::Min($set.Widths.Length - 1, $col + $m.W) }
					$wpx = $set.X[$c2 + 1] - $set.X[$col] - 2 * $pad
					if ($wpx -gt 4) {
						$size = $measure.MeasureString($content, $font, [int]$wpx)
						$lh = [math]::Max($lh, $size.Height + 2 * $pad)
					}
				} elseif ($content -and $content.Contains("`n")) {
					$size = $measure.MeasureString($content, $font)
					$lh = [math]::Max($lh, $size.Height + 2 * $pad)
				}
				if ($lh -gt $h) { $h = $lh }
			}
		}
		$rowHeight[$r] = $h
	}

	# --- Canvas geometry ---

	$labelFont = New-Object System.Drawing.Font('Arial', [single]([math]::Max(7.0, 7.5 * $pxPt)), [System.Drawing.GraphicsUnit]::Pixel)
	$rowNumW = [math]::Ceiling($measure.MeasureString([string]($r1 + 1), $labelFont).Width + 6)
	$laneW = [math]::Ceiling($labelFont.GetHeight() + 6)

	# Rows areas get lanes in the left gutter so that nested and overlapping areas stay apart.
	$rowAreas = @($areas | Where-Object { $_.Type -eq 'Rows' -and $_.R1 -ge 0 -and $_.R2 -ge $r0 -and $_.R1 -le $r1 } | Sort-Object { $_.R1 }, { -$_.R2 })
	$laneEnd = New-Object System.Collections.Generic.List[int]
	foreach ($a in $rowAreas) {
		$lane = -1
		for ($i = 0; $i -lt $laneEnd.Count; $i++) { if ($laneEnd[$i] -lt $a.R1) { $lane = $i; break } }
		if ($lane -lt 0) { $laneEnd.Add($a.R2); $lane = $laneEnd.Count - 1 } else { $laneEnd[$lane] = $a.R2 }
		$a.Lane = $lane
	}
	$colAreas = @($areas | Where-Object { $_.Type -eq 'Columns' -and $_.C1 -ge 0 } | Sort-Object { $_.C1 })
	$colLaneEnd = New-Object System.Collections.Generic.List[int]
	foreach ($a in $colAreas) {
		$lane = -1
		for ($i = 0; $i -lt $colLaneEnd.Count; $i++) { if ($colLaneEnd[$i] -lt $a.C1) { $lane = $i; break } }
		if ($lane -lt 0) { $colLaneEnd.Add($a.C2); $lane = $colLaneEnd.Count - 1 } else { $colLaneEnd[$lane] = $a.C2 }
		$a.Lane = $lane
	}

	$left = $laneEnd.Count * $laneW + $rowNumW
	$colHeaderH = [math]::Ceiling($labelFont.GetHeight() + 6)
	$top = $colLaneEnd.Count * $laneW + $colHeaderH

	$yTop = @{}
	$y = [double]$top
	$lastDrawn = $r0 - 1
	foreach ($r in $r0..$r1) {
		if ($y + $rowHeight[$r] -gt $MaxHeight - 4) { break }
		$yTop[$r] = $y
		$y += $rowHeight[$r]
		$lastDrawn = $r
	}
	$yTop[$lastDrawn + 1] = $y
	$truncated = ($lastDrawn -lt $r1)

	$contentW = 0.0
	foreach ($set in $sets.Values) {
		if ($set.Rows -eq 0 -and $set.Id -ne '') { continue }
		$wv = $set.X[$set.X.Length - 1]
		if ($wv -gt $contentW) { $contentW = $wv }
	}
	$canvasW = [int][math]::Ceiling($left + $contentW + 8)
	$canvasH = [int][math]::Ceiling($y + 8)
	if ($canvasW -lt 64) { $canvasW = 64 }
	if ($canvasH -lt 32) { $canvasH = 32 }

	$bmp = New-Object System.Drawing.Bitmap($canvasW, $canvasH)
	$g = [System.Drawing.Graphics]::FromImage($bmp)
	$g.Clear([System.Drawing.Color]::White)
	$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
	$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::None

	$gridPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(225, 225, 225), 1)
	$gutterBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(242, 242, 242))
	$gutterText = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(110, 110, 110))
	$styleFill = [System.Drawing.Color]::FromArgb(236, 240, 246)

	# --- Cells of every drawn row: one record per cell or merged block ---

	$records = New-Object System.Collections.Generic.List[object]
	$overflowable = @{}
	foreach ($r in $r0..$lastDrawn) {
		if ($rowHeight[$r] -le 0) { continue }
		$row = $rows[$r]
		$set = Get-MxrSet $(if ($row) { $row.Set } else { '' })
		$n = $set.Widths.Length
		$rowRecords = New-Object object[] $n
		for ($c = 0; $c -lt $n; $c++) {
			if (Test-MxrCovered $r $c $set.Id) { continue }
			$m = Get-MxrMerge $r $c $set.Id
			$c2 = $c; $r2 = $r
			if ($m) {
				$c2 = [math]::Min($n - 1, $c + $m.W)
				$r2 = [math]::Min($lastDrawn, $r + $m.H)
			}
			$rx = $left + $set.X[$c]
			$rw = $set.X[$c2 + 1] - $set.X[$c]
			$ry = $yTop[$r]
			$rh = $yTop[$r2 + 1] - $ry
			if ($rw -le 0 -or $rh -le 0) { continue }
			$fmt = Get-MxrCellFormat $row $set $c
			$cell = $null
			if ($row) { $cell = $row.Cells[$c] }
			$rec = @{
				R = $r; C = $c; C2 = $c2; Merged = [bool]$m; Set = $set
				X = $rx; Y = $ry; W = $rw; H = $rh
				Fmt = $fmt; Cell = $cell; Content = (Get-MxrContent $cell $fmt)
			}
			$records.Add($rec)
			$rowRecords[$c] = $rec
		}
		$overflowable[$r] = $rowRecords
	}

	# Pass 1: fills, then the light grid of the designer.
	foreach ($rec in $records) {
		if ($rec.Fmt -and $rec.Fmt['backColor']) {
			$bc = Get-MxrColor $rec.Fmt['backColor'] $null $styleFill
			if ($bc) {
				$br = New-Object System.Drawing.SolidBrush($bc)
				$g.FillRectangle($br, [single]$rec.X, [single]$rec.Y, [single]$rec.W, [single]$rec.H)
				$br.Dispose()
			}
		}
	}
	foreach ($rec in $records) {
		$g.DrawRectangle($gridPen, [single]$rec.X, [single]$rec.Y, [single]$rec.W, [single]$rec.H)
	}

	# Pass 2: text. Auto placement spills into empty neighbours, as the platform shows it.
	$rotated = 0
	foreach ($rec in $records) {
		if (-not $rec.Content) { continue }
		$fmt = $rec.Fmt
		$placement = $null
		if ($fmt) { $placement = $fmt['textPlacement'] }
		if ($fmt -and $fmt['textOrientation'] -and $fmt['textOrientation'] -ne '0') { $rotated++ }
		$wrap = ($placement -eq 'Wrap')
		$font = Get-MxrFont $fmt
		$x1 = $rec.X; $x2 = $rec.X + $rec.W
		if (-not $wrap -and $placement -ne 'Cut' -and -not $rec.Merged) {
			$need = $measure.MeasureString($rec.Content, $font).Width + 2 * $pad
			if ($need -gt $rec.W) {
				$rr = $overflowable[$rec.R]
				$h = $null
				if ($fmt) { $h = $fmt['horizontalAlignment'] }
				$goLeft = ($h -eq 'Right' -or $h -eq 'Center')
				$goRight = ($h -ne 'Right')
				$cl = $rec.C - 1; $cr = $rec.C2 + 1
				while (($x2 - $x1) -lt $need) {
					$moved = $false
					if ($goRight -and $cr -lt $rr.Length -and $rr[$cr] -and -not $rr[$cr].Content -and -not $rr[$cr].Merged) {
						$x2 = $rr[$cr].X + $rr[$cr].W; $cr++; $moved = $true
					}
					if (($x2 - $x1) -ge $need) { break }
					if ($goLeft -and $cl -ge 0 -and $rr[$cl] -and -not $rr[$cl].Content -and -not $rr[$cl].Merged) {
						$x1 = $rr[$cl].X; $cl--; $moved = $true
					}
					if (-not $moved) { break }
				}
			}
		}
		$color = [System.Drawing.Color]::Black
		if ($fmt -and $fmt['textColor']) { $color = Get-MxrColor $fmt['textColor'] ([System.Drawing.Color]::Black) ([System.Drawing.Color]::Black) }
		$brush = New-Object System.Drawing.SolidBrush($color)
		$sf = New-MxrStringFormat $fmt $wrap
		$clip = New-Object System.Drawing.RectangleF([single]$x1, [single]$rec.Y, [single]($x2 - $x1), [single]$rec.H)
		$box = New-Object System.Drawing.RectangleF([single]($x1 + $pad), [single]($rec.Y + $pad / 2), [single]([math]::Max(1, $x2 - $x1 - 2 * $pad)), [single]([math]::Max(1, $rec.H - $pad)))
		$g.SetClip($clip)
		$g.DrawString($rec.Content, $font, $brush, $box, $sf)
		$g.ResetClip()
		$brush.Dispose(); $sf.Dispose()
	}

	# Pass 3: borders from the line palette.
	$penCache = @{}
	function Get-MxrPen([int]$lineIdx, [string]$colorValue) {
		if ($lineIdx -lt 0 -or $lineIdx -ge $lineDefs.Count) { return $null }
		$ld = $lineDefs[$lineIdx]
		if ($ld.Style -eq 'None') { return $null }
		$key = "$lineIdx|$colorValue"
		if ($penCache.ContainsKey($key)) { return $penCache[$key] }
		$color = Get-MxrColor $colorValue ([System.Drawing.Color]::Black) ([System.Drawing.Color]::FromArgb(64, 64, 64))
		$pen = New-Object System.Drawing.Pen($color, [single]([math]::Max(1.0, $ld.Width * $zoomEff)))
		switch ($ld.Style) {
			'Dotted'      { $pen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dot }
			'ThinDashed'  { $pen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash }
			'ThickDashed' { $pen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash; $pen.Width = [single]($pen.Width + 1) }
			'LargeDashed' { $pen.DashPattern = [single[]](6, 3) }
			'Double'      { $pen.CompoundArray = [single[]](0, 0.3, 0.7, 1); $pen.Width = [single]([math]::Max(3, $pen.Width * 3)) }
		}
		$penCache[$key] = $pen
		return $pen
	}
	foreach ($rec in $records) {
		$fmt = $rec.Fmt
		if (-not $fmt) { continue }
		$all = $fmt['border']
		$sides = @{
			left   = $(if ($fmt['leftBorder']) { $fmt['leftBorder'] } else { $all })
			top    = $(if ($fmt['topBorder']) { $fmt['topBorder'] } else { $all })
			right  = $(if ($fmt['rightBorder']) { $fmt['rightBorder'] } else { $all })
			bottom = $(if ($fmt['bottomBorder']) { $fmt['bottomBorder'] } else { $all })
		}
		$x1 = [single]$rec.X; $y1 = [single]$rec.Y
		$x2 = [single]($rec.X + $rec.W); $y2 = [single]($rec.Y + $rec.H)
		foreach ($side in 'left', 'top', 'right', 'bottom') {
			$v = $sides[$side]
			if ($null -eq $v -or $v -eq '') { continue }
			$pen = Get-MxrPen ([int]$v) $fmt['borderColor']
			if (-not $pen) { continue }
			switch ($side) {
				'left'   { $g.DrawLine($pen, $x1, $y1, $x1, $y2) }
				'top'    { $g.DrawLine($pen, $x1, $y1, $x2, $y1) }
				'right'  { $g.DrawLine($pen, $x2, $y1, $x2, $y2) }
				'bottom' { $g.DrawLine($pen, $x1, $y2, $x2, $y2) }
			}
		}
		if ($rec.Cell -and $rec.Cell.Note) {
			$tri = [System.Drawing.PointF[]]@(
				(New-Object System.Drawing.PointF(($x2 - 6 * $zoomEff), $y1)),
				(New-Object System.Drawing.PointF($x2, $y1)),
				(New-Object System.Drawing.PointF($x2, ($y1 + 6 * $zoomEff))))
			$g.FillPolygon([System.Drawing.Brushes]::Red, $tri)
		}
	}

	# --- Drawings: outlined only ---

	$dashPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(90, 90, 160), 1)
	$dashPen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash
	$drawnDrawings = 0
	foreach ($d in $drawings) {
		if (-not $yTop.ContainsKey($d.R1) -or -not $yTop.ContainsKey($d.R2)) { continue }
		$set = $sets['']
		if ($d.C1 -ge $set.Widths.Length -or $d.C2 -ge $set.Widths.Length) { continue }
		$dx1 = $left + $set.X[$d.C1] + [math]::Min($d.C1o, $set.Widths[$d.C1]) * $pxW
		$dx2 = $left + $set.X[$d.C2] + [math]::Min($d.C2o, $set.Widths[$d.C2]) * $pxW
		$dy1 = $yTop[$d.R1] + [math]::Min($d.R1o / 4.0 * $pxPt, $rowHeight[$d.R1])
		$dy2 = $yTop[$d.R2] + [math]::Min($d.R2o / 4.0 * $pxPt, $rowHeight[$d.R2])
		if ($dx2 -le $dx1 -or $dy2 -le $dy1) { continue }
		$g.DrawRectangle($dashPen, [single]$dx1, [single]$dy1, [single]($dx2 - $dx1), [single]($dy2 - $dy1))
		$label = $d.Type
		if ($d.Name) { $label = "$($d.Type) $($d.Name)" }
		$g.DrawString($label, $labelFont, [System.Drawing.Brushes]::DarkSlateBlue, [single]($dx1 + 2), [single]($dy1 + 1))
		$drawnDrawings++
	}

	# --- Gutters: column numbers, row numbers, named areas ---

	$g.FillRectangle($gutterBrush, [single]0, [single]0, [single]$canvasW, [single]$top)
	$g.FillRectangle($gutterBrush, [single]0, [single]0, [single]$left, [single]$canvasH)
	$def = $sets['']
	$numFmt = New-Object System.Drawing.StringFormat
	$numFmt.Alignment = [System.Drawing.StringAlignment]::Center
	$numFmt.LineAlignment = [System.Drawing.StringAlignment]::Center
	$lastLabelX = -1000.0
	for ($c = 0; $c -lt $def.Widths.Length; $c++) {
		$cx = $left + $def.X[$c]
		$cw = $def.X[$c + 1] - $def.X[$c]
		$g.DrawLine($gridPen, [single]$cx, [single]($top - $colHeaderH), [single]$cx, [single]$top)
		$labelW = $measure.MeasureString([string]($c + 1), $labelFont).Width
		if ($cx + $cw / 2 - $lastLabelX -ge $labelW + 2) {
			$g.DrawString([string]($c + 1), $labelFont, $gutterText, (New-Object System.Drawing.RectangleF([single]$cx, [single]($top - $colHeaderH), [single]$cw, [single]$colHeaderH)), $numFmt)
			$lastLabelX = $cx + $cw / 2
		}
	}
	$lastLabelY = -1000.0
	foreach ($r in $r0..$lastDrawn) {
		if ($rowHeight[$r] -le 0) { continue }
		$cy = $yTop[$r] + $rowHeight[$r] / 2
		if ($cy - $lastLabelY -lt $labelFont.GetHeight()) { continue }
		$g.DrawString([string]($r + 1), $labelFont, $gutterText, (New-Object System.Drawing.RectangleF([single]($left - $rowNumW), [single]$yTop[$r], [single]$rowNumW, [single]$rowHeight[$r])), $numFmt)
		$lastLabelY = $cy
	}

	$areaColors = @(
		[System.Drawing.Color]::FromArgb(197, 217, 241), [System.Drawing.Color]::FromArgb(216, 228, 188),
		[System.Drawing.Color]::FromArgb(252, 213, 180), [System.Drawing.Color]::FromArgb(228, 223, 236),
		[System.Drawing.Color]::FromArgb(218, 238, 243), [System.Drawing.Color]::FromArgb(242, 220, 219))
	$areaPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(120, 120, 120), 1)
	$vertical = New-Object System.Drawing.StringFormat
	$vertical.FormatFlags = [System.Drawing.StringFormatFlags]::DirectionVertical -bor [System.Drawing.StringFormatFlags]::NoWrap
	$vertical.Alignment = [System.Drawing.StringAlignment]::Near
	$vertical.LineAlignment = [System.Drawing.StringAlignment]::Center
	$i = 0
	foreach ($a in $rowAreas) {
		$ra = [math]::Max($a.R1, $r0)
		$rb = [math]::Min($a.R2, $lastDrawn)
		if ($rb -lt $ra) { continue }
		$ay1 = $yTop[$ra]; $ay2 = $yTop[$rb + 1]
		$ax = $a.Lane * $laneW
		$br = New-Object System.Drawing.SolidBrush($areaColors[$i % $areaColors.Count])
		$g.FillRectangle($br, [single]($ax + 1), [single]$ay1, [single]($laneW - 2), [single]($ay2 - $ay1))
		$g.DrawRectangle($areaPen, [single]($ax + 1), [single]$ay1, [single]($laneW - 2), [single]($ay2 - $ay1))
		$g.SetClip((New-Object System.Drawing.RectangleF([single]$ax, [single]$ay1, [single]$laneW, [single]($ay2 - $ay1))))
		$g.DrawString($a.Name, $labelFont, [System.Drawing.Brushes]::Black, (New-Object System.Drawing.RectangleF([single]($ax + 1), [single]($ay1 + 2), [single]($laneW - 2), [single]([math]::Max(1, $ay2 - $ay1 - 2)))), $vertical)
		$g.ResetClip()
		$g.DrawLine($areaPen, [single]$left, [single]$ay1, [single]($left + 6), [single]$ay1)
		$br.Dispose()
		$i++
	}
	foreach ($a in $colAreas) {
		$set = Get-MxrSet $a.Set
		if ($a.C1 -ge $set.Widths.Length) { continue }
		$cb = [math]::Min($a.C2, $set.Widths.Length - 1)
		$ax1 = $left + $set.X[$a.C1]; $ax2 = $left + $set.X[$cb + 1]
		$ay = $a.Lane * $laneW
		$br = New-Object System.Drawing.SolidBrush($areaColors[$i % $areaColors.Count])
		$g.FillRectangle($br, [single]$ax1, [single]($ay + 1), [single]($ax2 - $ax1), [single]($laneW - 2))
		$g.DrawRectangle($areaPen, [single]$ax1, [single]($ay + 1), [single]($ax2 - $ax1), [single]($laneW - 2))
		$g.DrawString($a.Name, $labelFont, [System.Drawing.Brushes]::Black, [single]($ax1 + 2), [single]($ay + 2))
		$br.Dispose()
		$i++
	}
	$rectPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(200, 90, 40), [single]1)
	$rectPen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dash
	foreach ($a in ($areas | Where-Object { $_.Type -eq 'Rectangle' })) {
		if (-not $yTop.ContainsKey($a.R1) -or $a.R2 -gt $lastDrawn -or $a.C1 -lt 0) { continue }
		$set = Get-MxrSet $a.Set
		if ($a.C2 -ge $set.Widths.Length) { continue }
		$ax1 = $left + $set.X[$a.C1]; $ax2 = $left + $set.X[$a.C2 + 1]
		$ay1 = $yTop[$a.R1]; $ay2 = $yTop[$a.R2 + 1]
		$g.DrawRectangle($rectPen, [single]$ax1, [single]$ay1, [single]($ax2 - $ax1), [single]($ay2 - $ay1))
		# The name only where it fits: a row of one-cell areas (INN digits) would bury the cells.
		$tw = $measure.MeasureString($a.Name, $labelFont).Width + 4
		if ($tw -le ($ax2 - $ax1) - 4) {
			$g.FillRectangle([System.Drawing.Brushes]::White, [single]($ax1 + 2), [single]($ay1 + 2), [single]$tw, [single]$labelFont.GetHeight())
			$g.DrawString($a.Name, $labelFont, [System.Drawing.Brushes]::Sienna, [single]($ax1 + 2), [single]($ay1 + 2))
		}
	}
	if ($truncated) {
		$g.FillRectangle([System.Drawing.Brushes]::LightYellow, [single]$left, [single]($y), [single]$contentW, [single]8)
	}

	# --- Save ---

	if (-not $OutputPath) {
		$outDir = Join-Path ([System.IO.Path]::GetTempPath()) "mxl-render"
		$name = $templateLabel
		if ($Area) { $name += "." + $Area }
		foreach ($ch in [System.IO.Path]::GetInvalidFileNameChars()) { $name = $name.Replace([string]$ch, '_') }
		$OutputPath = Join-Path $outDir ($name + ".png")
	}
	$outFull = [System.IO.Path]::GetFullPath($(if ([System.IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path (Get-Location).ProviderPath $OutputPath }))
	$outParent = [System.IO.Path]::GetDirectoryName($outFull)
	if (-not (Test-Path -LiteralPath $outParent)) { [void](New-Item -ItemType Directory -Path $outParent -Force) }
	$bmp.Save($outFull, [System.Drawing.Imaging.ImageFormat]::Png)
	$g.Dispose(); $bmp.Dispose(); $measure.Dispose(); $measureBmp.Dispose()

	# --- Report ---

	Write-Host "=== MXL render: $templateLabel ==="
	Write-Host "PNG: $outFull ($canvasW x $canvasH px)"
	$rowsLine = "Rows drawn: $($r0 + 1)-$($lastDrawn + 1) of $rowCount"
	if ($focus) { $rowsLine += " (area $($focus.Name), $($focus.Type))" }
	if ($truncated) { $rowsLine += "; TRUNCATED at -MaxHeight $MaxHeight px - draw one area with -Area, or raise -MaxHeight" }
	Write-Host $rowsLine
	# Millimetres are an estimate: one unit drawn as one pixel at 96 dpi (see the header), not
	# checked against the 1C print preview. A4 is 210 x 297 mm; margins come from the layout's
	# print settings, else 10 mm a side (the value the platform writes when it saves a layout).
	$mmPerUnit = 25.4 / 96.0
	$widthMm = $docWidth * $mmPerUnit
	Write-Host "Width (whole layout):"
	foreach ($l in $setReport) { Write-Host $l }
	Write-Host ("  layout: {0} units, about {1} mm (estimate: 1 unit = 1 px at 96 dpi = 0.26 mm; not checked against the 1C print preview)" -f [math]::Round($docWidth), [math]::Round($widthMm))

	$tp = $pageTargets["A4-portrait"]; $tl = $pageTargets["A4-landscape"]
	if ($docWidth -le $tp) { $targetText = "within the portrait target" }
	elseif ($docWidth -le $tl) { $targetText = "within the landscape target only ($([math]::Round($docWidth)) > $tp)" }
	else { $targetText = "wider than both targets ($([math]::Round($docWidth)) > $tl)" }
	Write-Host "mxl-compile targets (A4-portrait $tp, A4-landscape $tl units - what the rules compile new layouts to): $targetText"

	$ps = $root.SelectSingleNode("d:printSettings", $ns)
	$orientation = $null; $fitToPage = $false; $scale = 100.0
	$leftMm = 10.0; $rightMm = 10.0
	if ($ps) {
		$orientation = Get-MxrText $ps "d:pageOrientation"
		$fitToPage = ((Get-MxrText $ps "d:fitToPage") -eq 'true')
		$scale = ConvertTo-MxrNumber (Get-MxrText $ps "d:scale") 100
		if ($scale -le 0) { $scale = 100.0 }
		$leftMm = (ConvertTo-MxrNumber (Get-MxrText $ps "d:leftMargin") 1000) / 100.0
		$rightMm = (ConvertTo-MxrNumber (Get-MxrText $ps "d:rightMargin") 1000) / 100.0
		Write-Host ("Print settings stored in the layout: orientation {0}, fitToPage {1}, scale {2}%, margins {3} + {4} mm" -f $(if ($orientation) { $orientation } else { 'not set' }), $(if ($fitToPage) { 'true' } else { 'false' }), $scale, $leftMm, $rightMm)
	} else {
		Write-Host "Print settings stored in the layout: none"
	}
	$availP = 210.0 - $leftMm - $rightMm
	$availL = 297.0 - $leftMm - $rightMm
	$pctP = [math]::Min(100, [math]::Floor(100.0 * $availP / [math]::Max(1.0, $widthMm)))
	$pctL = [math]::Min(100, [math]::Floor(100.0 * $availL / [math]::Max(1.0, $widthMm)))
	Write-Host ("A4 (estimate): portrait, {0} mm print width - {1}; landscape, {2} mm - {3}" -f [math]::Round($availP), $(if ($pctP -ge 100) { 'fits at 100%' } else { "does not fit at 100%, fitted to the page width about $pctP%" }), [math]::Round($availL), $(if ($pctL -ge 100) { 'fits at 100%' } else { "does not fit at 100%, fitted to the page width about $pctL%" }))

	if ($fitToPage) {
		$o = $(if ($orientation -eq 'Landscape') { 'landscape' } else { 'portrait' })
		$pct = $(if ($o -eq 'landscape') { $pctL } else { $pctP })
		if ($pct -ge 100) { $verdict = "the layout is set to fit the page width (fitToPage): A4 $o, no reduction needed (estimate)" }
		else { $verdict = "the layout is set to fit the page width (fitToPage): A4 $o, reduced to about $pct% (estimate)" }
	} elseif ($ps -and $orientation) {
		$o = $(if ($orientation -eq 'Landscape') { 'landscape' } else { 'portrait' })
		$avail = $(if ($o -eq 'landscape') { $availL } else { $availP })
		$printed = $widthMm * $scale / 100.0
		if ($printed -le $avail) { $verdict = "printed at $scale% on A4 $o it fits: about $([math]::Round($printed)) of $([math]::Round($avail)) mm (estimate)" }
		else { $verdict = "printed at $scale% on A4 $o it runs past the print width: about $([math]::Round($printed)) of $([math]::Round($avail)) mm (estimate), unless the printing code sets FitToPage" }
	} else {
		if ($pctP -ge 100) { $verdict = "at 100% it fits A4 portrait (estimate)" }
		elseif ($pctL -ge 100) { $verdict = "at 100% it fits A4 landscape; on portrait, fitted to the page width, about $pctP% (estimate)" }
		else { $verdict = "wider than A4 landscape at 100%; fitted to the page width it prints at about $pctL% landscape or $pctP% portrait (estimate)" }
		if ($pctP -lt 100) { $verdict += ". Whether it is fitted to the page is up to the printing code (SpreadsheetDocument.FitToPage)" }
	}
	Write-Host "Verdict: $verdict"
	$notDrawn = @()
	if ($drawings.Count -gt 0) { $notDrawn += "$($drawings.Count) drawing(s) outlined only ($drawnDrawings in view)" }
	if ($cellPictures -gt 0) { $notDrawn += "$cellPictures cell picture(s)" }
	if ($rotated -gt 0) { $notDrawn += "$rotated rotated text(s) drawn horizontally" }
	if ($styleColorCount -gt 0) { $notDrawn += "colours given by style elements drawn neutral" }
	if ($hiddenRows -gt 0) { $notDrawn += "$hiddenRows hidden row(s) left out" }
	if ($root.SelectSingleNode("d:header", $ns) -or $root.SelectSingleNode("d:footer", $ns)) { $notDrawn += "header / footer" }
	if ($notDrawn.Count -gt 0) { Write-Host "Not drawn: $($notDrawn -join '; ')" }
	exit 0
}
