<#
.SYNOPSIS
    Script thu PCAP dùng chung cho mọi kịch bản S01–S12 (Wireshark CLI: dumpcap, capinfos, tshark).

.DESCRIPTION
    1. Kiểm tra trước khi thu: công cụ Wireshark, SSH tới router, flow offloading, Mosquitto,
       lệch đồng hồ, dung lượng ổ, khung giờ 07:00–18:00.
    2. Thu: ssh vào router chạy tcpdump trên br-lan (loại SSH của CAPTURE-SERVER), dữ liệu đẩy
       về dumpcap trên máy này, tự tách file theo thời gian, tự dừng khi hết thời lượng.
    3. Sau khi thu: đổi tên file theo quy ước, đọc số liệu bằng capinfos, ghi metadata.csv,
       chạy các bộ lọc nghiệm thu bằng tshark và xuất báo cáo PASS/FAIL.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S04 -NUserDevices 4
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S11 -NUserDevices 10 -Config Lon -Notes "cuoi tuan"
.EXAMPLE
    # Chỉ chấm lại nghiệm thu cho một phiên đã thu
    powershell -ExecutionPolicy Bypass -File tools\capture_session.ps1 -Scenarios S07 -CheckOnly -SessionId SES005
#>
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Scenarios,                   # ví dụ: S04  hoặc  S05,S07  (S08 luôn được thêm)
    [int]$NUserDevices = 0,                  # số thiết bị người dùng đang kết nối
    [ValidateSet("Nho", "Lon")]
    [string]$Config = "Lon",
    [int]$DurationMin = 0,                   # 0 = dùng thời lượng mặc định của kịch bản
    [string]$Notes = "",
    [string]$RouterIp = "192.168.10.1",
    [string]$RouterUser = "root",
    [string]$CaptureServerIp = "192.168.10.60",
    [string]$Interface = "br-lan",
    [string]$OutDir = (Join-Path (Split-Path $PSScriptRoot -Parent) "data"),
    [string]$WiresharkDir = "C:\Program Files\Wireshark",
    [switch]$CheckOnly,                      # bỏ qua thu, chỉ chấm nghiệm thu
    [string]$SessionId = "",                 # dùng với -CheckOnly
    [switch]$Force                           # bỏ qua cảnh báo khung giờ / kiểm tra trước
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Cấu hình theo kịch bản
# ---------------------------------------------------------------------------
# Min: thời lượng mặc định (phút); SplitMin: tách file; DiskGB: dung lượng trống tối thiểu
$ScenarioInfo = @{
    S01 = @{ Name = "Idle network";            Min = 30; SplitMin = 60; DiskGB = 1 }
    S02 = @{ Name = "Device onboarding";       Min = 15; SplitMin = 60; DiskGB = 1 }
    S03 = @{ Name = "Web browsing";            Min = 30; SplitMin = 60; DiskGB = 2 }
    S04 = @{ Name = "Video streaming";         Min = 30; SplitMin = 60; DiskGB = 12 }
    S05 = @{ Name = "File transfer";           Min = 25; SplitMin = 60; DiskGB = 3 }
    S06 = @{ Name = "Voice/video call";        Min = 30; SplitMin = 60; DiskGB = 3 }
    S07 = @{ Name = "IP camera";               Min = 30; SplitMin = 60; DiskGB = 4 }
    S08 = @{ Name = "MQTT background";         Min = 60; SplitMin = 60; DiskGB = 1 }
    S09 = @{ Name = "Smart home control";      Min = 20; SplitMin = 60; DiskGB = 1 }
    S10 = @{ Name = "Normal reconnect";        Min = 15; SplitMin = 60; DiskGB = 1 }
    S11 = @{ Name = "Mixed household";         Min = 60; SplitMin = 30; DiskGB = 25 }
    S12 = @{ Name = "Peak hour";               Min = 30; SplitMin = 10; DiskGB = 30 }
}

$Cams  = "192.168.10.30 192.168.10.31 192.168.10.32"
$Iots  = "192.168.10.40 192.168.10.41 192.168.10.42"
$Users = (10..19 | ForEach-Object { "192.168.10.$_" }) -join " "

# Bộ lọc nghiệm thu: Expect = "zero" (phải bằng 0) hoặc "nonzero" (phải > 0)
$CommonChecks = @(
    @{ Name = "Khong co SSH cua CAPTURE-SERVER"; Filter = "tcp.port == 22";        Expect = "zero" }
    @{ Name = "Co DNS";                          Filter = "dns";                   Expect = "nonzero" }
    @{ Name = "MQTT publish (S08)";              Filter = "mqtt.msgtype == 3";     Expect = "nonzero" }
    @{ Name = "IOT01 xuat hien";                 Filter = "ip.addr == 192.168.10.40"; Expect = "nonzero" }
    @{ Name = "IOT02 xuat hien";                 Filter = "ip.addr == 192.168.10.41"; Expect = "nonzero" }
    @{ Name = "IOT03 xuat hien";                 Filter = "ip.addr == 192.168.10.42"; Expect = "nonzero" }
)
$ScenarioChecks = @{
    S01 = @( @{ Name = "Co NTP"; Filter = "ntp"; Expect = "nonzero" } )
    S02 = @( @{ Name = "DHCP Request/ACK";   Filter = "dhcp";                     Expect = "nonzero" }
             @{ Name = "DHCP Discover";      Filter = "dhcp.option.dhcp == 1";    Expect = "nonzero" }
             @{ Name = "ARP";                Filter = "arp";                      Expect = "nonzero" }
             @{ Name = "MQTT CONNECT";       Filter = "mqtt.msgtype == 1";        Expect = "nonzero" } )
    S03 = @( @{ Name = "TLS ClientHello";    Filter = "tls.handshake.type == 1";  Expect = "nonzero" }
             @{ Name = "QUIC";               Filter = "quic";                     Expect = "nonzero" } )
    S04 = @( @{ Name = "QUIC/TLS";           Filter = "quic || tls";              Expect = "nonzero" } )
    S05 = @( @{ Name = "TLS";                Filter = "tls";                      Expect = "nonzero" } )
    S06 = @( @{ Name = "STUN/TURN";          Filter = "stun || udp.port == 3478 || udp.port == 19302"; Expect = "nonzero" } )
    S07 = @( @{ Name = "Camera <-> viewer LAN"; Filter = "ip.addr in {$Cams} && ip.addr in {$Users}"; Expect = "nonzero" }
             @{ Name = "CAM01 xuat hien";    Filter = "ip.addr == 192.168.10.30"; Expect = "nonzero" }
             @{ Name = "CAM02 xuat hien";    Filter = "ip.addr == 192.168.10.31"; Expect = "nonzero" }
             @{ Name = "CAM03 xuat hien";    Filter = "ip.addr == 192.168.10.32"; Expect = "nonzero" } )
    S08 = @( @{ Name = "PUBACK (QoS 1)";     Filter = "mqtt.msgtype == 4";        Expect = "nonzero" } )
    S09 = @( @{ Name = "Lenh /cmd";          Filter = 'mqtt.topic contains "/cmd"'; Expect = "nonzero" }
             @{ Name = "Phan hoi IOT03";     Filter = 'mqtt.topic contains "iot03"'; Expect = "nonzero" } )
    S10 = @( @{ Name = "DHCP khi ket noi lai"; Filter = "dhcp";                   Expect = "nonzero" }
             @{ Name = "LWT IOT03";          Filter = 'mqtt.topic == "smarthome/iot03/status"'; Expect = "nonzero" } )
    S11 = @( @{ Name = "QUIC";               Filter = "quic";                     Expect = "nonzero" }
             @{ Name = "HTTP camera noi bo"; Filter = "http && ip.addr in {$Cams}"; Expect = "nonzero" }
             @{ Name = "Lenh IOT03";         Filter = 'mqtt.topic contains "iot03"'; Expect = "nonzero" } )
    S12 = @( @{ Name = "Khong co iperf (5201)"; Filter = "tcp.port == 5201";      Expect = "zero" }
             @{ Name = "QUIC";               Filter = "quic";                     Expect = "nonzero" } )
}

# ---------------------------------------------------------------------------
# Hàm tiện ích
# ---------------------------------------------------------------------------
function Write-Step($msg)  { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "  [FAIL] $msg" -ForegroundColor Red }

function Invoke-Router([string]$cmd) {
    & ssh -o BatchMode=yes -o ConnectTimeout=5 "$RouterUser@$RouterIp" $cmd 2>$null
}

function Get-NextSessionId([string]$metaPath) {
    $max = 0
    if (Test-Path $metaPath) {
        Import-Csv $metaPath | ForEach-Object {
            if ($_.session_id -match '^SES(\d+)$') { $max = [Math]::Max($max, [int]$Matches[1]) }
        }
    }
    return "SES{0:D3}" -f ($max + 1)
}

# Đếm số gói khớp với nhiều bộ lọc trong MỘT lần đọc file (tshark -z io,stat,0,...)
function Get-FilterCounts([string]$pcap, [string[]]$filters) {
    # Tự dựng chuỗi tham số: PowerShell 5.1 truyền sai tham số có dấu " cho chương trình ngoài
    $z = "io,stat,0," + (($filters | ForEach-Object { $_.Replace('"', '\"') }) -join ",")
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Tshark
    $psi.Arguments = "-n -q -r `"$pcap`" -z `"$z`""
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) { Write-Warn2 "tshark loi voi $($pcap): $stderr" }

    $row = ($stdout -split "`r?`n") | Where-Object { $_ -match '<>' } | Select-Object -Last 1
    if (-not $row) { return @($filters | ForEach-Object { 0 }) }
    $cells = @(($row -split '\|') | Select-Object -Skip 2 | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
    # Mỗi bộ lọc có 2 cột: Frames, Bytes
    $counts = @()
    for ($i = 0; $i -lt $filters.Count; $i++) { $counts += [long]$cells[2 * $i] }
    return $counts
}

# ---------------------------------------------------------------------------
# Chuẩn bị tham số phiên
# ---------------------------------------------------------------------------
$Scenarios = @($Scenarios | ForEach-Object { $_ -split "[,; ]" } | Where-Object { $_ } |
    ForEach-Object { $_.ToUpper() } | Select-Object -Unique)
foreach ($s in $Scenarios) { if (-not $ScenarioInfo.ContainsKey($s)) { throw "Kich ban khong hop le: $s" } }
if ($Scenarios -notcontains "S08") { $Scenarios += "S08" }
$Main = ($Scenarios | Where-Object { $_ -ne "S08" } | Select-Object -First 1)
if (-not $Main) { $Main = "S08" }
if ($Scenarios -contains "S12" -and $Config -ne "Lon") { throw "S12 chi chay voi cau hinh Lon." }

if ($DurationMin -le 0) { $DurationMin = $ScenarioInfo[$Main].Min }
$SplitMin = ($Scenarios | ForEach-Object { $ScenarioInfo[$_].SplitMin } | Measure-Object -Minimum).Minimum
$DiskGB   = ($Scenarios | ForEach-Object { $ScenarioInfo[$_].DiskGB }   | Measure-Object -Maximum).Maximum
$ActiveScenarios = (@($Main) + ($Scenarios | Where-Object { $_ -ne $Main } | Sort-Object)) -join ";"

$Dumpcap  = Join-Path $WiresharkDir "dumpcap.exe"
$Tshark   = Join-Path $WiresharkDir "tshark.exe"
$Capinfos = Join-Path $WiresharkDir "capinfos.exe"
$PcapDir  = Join-Path $OutDir "pcap"
$LogDir   = Join-Path $OutDir "logs"
$MetaPath = Join-Path $OutDir "metadata.csv"
New-Item -ItemType Directory -Force -Path $PcapDir, $LogDir | Out-Null

if ($CheckOnly -and -not $SessionId) { throw "-CheckOnly can kem -SessionId" }
if (-not $SessionId) { $SessionId = Get-NextSessionId $MetaPath }

Write-Host "Phien: $SessionId | Kich ban: $ActiveScenarios | Thoi luong: $DurationMin phut | Tach file: $SplitMin phut | Cau hinh: $Config"
Write-Host "Chi tiet kich ban: scenarios\$Main`_*.md"

# ---------------------------------------------------------------------------
# 1. Kiểm tra trước khi thu
# ---------------------------------------------------------------------------
if (-not $CheckOnly) {
    Write-Step "Kiem tra truoc khi thu"
    $problems = 0

    foreach ($exe in @($Dumpcap, $Tshark, $Capinfos)) {
        if (Test-Path $exe) { Write-Ok "Tim thay $(Split-Path $exe -Leaf)" } else { Write-Fail "Khong tim thay $exe"; $problems++ }
    }
    if (Get-Command ssh -ErrorAction SilentlyContinue) { Write-Ok "Tim thay ssh" } else { Write-Fail "Chua cai OpenSSH client"; $problems++ }

    $now = Get-Date
    $end = $now.AddMinutes($DurationMin)
    if ($now.Hour -lt 7 -or $end -gt $now.Date.AddHours(18)) {
        Write-Fail ("Phien {0:HH:mm}-{1:HH:mm} nam ngoai khung 07:00-18:00" -f $now, $end); $problems++
    } else { Write-Ok ("Khung gio {0:HH:mm}-{1:HH:mm}" -f $now, $end) }

    $drive = (Get-Item $OutDir).PSDrive
    $freeGB = [Math]::Round((Get-PSDrive $drive.Name).Free / 1GB, 1)
    if ($freeGB -ge $DiskGB) { Write-Ok "O dia con trong $freeGB GB (can >= $DiskGB GB)" } else { Write-Fail "O dia con $freeGB GB, can >= $DiskGB GB"; $problems++ }

    $probe = Invoke-Router "echo SSH_OK; uci -q get firewall.@defaults[0].flow_offloading; echo '|'; uci -q get firewall.@defaults[0].flow_offloading_hw; echo '|'; /etc/init.d/mosquitto running && echo MQ_OK; which tcpdump; date +%s"
    if (-not ($probe -match "SSH_OK")) {
        Write-Fail "Khong SSH duoc vao $RouterUser@$RouterIp (can SSH key, khong dung mat khau)"; $problems++
    } else {
        Write-Ok "SSH vao router"
        $text = $probe -join "`n"
        if ($text -match "(?m)^1$") { Write-Fail "Flow offloading dang bat"; $problems++ } else { Write-Ok "Flow offloading da tat" }
        if ($text -match "MQ_OK") { Write-Ok "Mosquitto dang chay" } else { Write-Fail "Mosquitto khong chay"; $problems++ }
        if ($text -match "tcpdump") { Write-Ok "Router co tcpdump" } else { Write-Fail "Router chua cai tcpdump"; $problems++ }
        $routerEpoch = [long](($probe | Where-Object { $_ -match '^\d{9,}$' } | Select-Object -Last 1))
        $localEpoch  = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $skew = [Math]::Abs($routerEpoch - $localEpoch)
        if ($skew -le 2) { Write-Ok "Lech dong ho router: $skew s" } else { Write-Fail "Lech dong ho router: $skew s (> 2 s)"; $problems++ }
    }

    if ($problems -gt 0 -and -not $Force) { throw "Co $problems loi kiem tra truoc khi thu. Sua loi hoac chay lai voi -Force." }
}

# ---------------------------------------------------------------------------
# 2. Thu PCAP
# ---------------------------------------------------------------------------
$TcpdumpLog = Join-Path $LogDir "$SessionId`_tcpdump.log"
$StartTime = $null; $EndTime = $null

if (-not $CheckOnly) {
    Write-Step "Thu PCAP"
    $durationSec = $DurationMin * 60
    $bpf = "not (host $CaptureServerIp and port 22)"
    $remote = "timeout $durationSec tcpdump -i $Interface -s 0 -U -B 4096 -w - '$bpf'"
    $base = Join-Path $PcapDir "$SessionId.pcap"

    # Dùng cmd.exe cho đường ống: PowerShell 5.1 làm hỏng dữ liệu nhị phân khi pipe giữa hai chương trình
    $cmdFile = Join-Path $LogDir "$SessionId`_capture.cmd"
    @"
@echo off
ssh -o BatchMode=yes -o ServerAliveInterval=15 $RouterUser@$RouterIp "$remote" 2> "$TcpdumpLog" | "$Dumpcap" -q -i - -F pcap -b duration:$($SplitMin * 60) -w "$base"
"@ | Set-Content -Path $cmdFile -Encoding ASCII

    $StartTime = Get-Date
    Write-Host ("Bat dau {0:HH:mm:ss}, tu dung luc {1:HH:mm:ss}." -f $StartTime, $StartTime.AddSeconds($durationSec))
    Write-Host "Neu dung som bang Ctrl+C: chay lai voi -CheckOnly -SessionId $SessionId de ghi metadata va nghiem thu." -ForegroundColor Yellow
    try {
        & cmd.exe /c $cmdFile
    } finally {
        $EndTime = Get-Date
        Write-Host ("Ket thuc {0:HH:mm:ss}" -f $EndTime)
    }

    # Đổi tên: SES001_00001_20261012145800.pcap -> SES001_20261012_145800.pcap
    Get-ChildItem $PcapDir -Filter "$SessionId`_*.pcap" | ForEach-Object {
        if ($_.Name -match "^($SessionId)_\d{5}_(\d{8})(\d{6})\.pcap$") {
            Rename-Item $_.FullName ("{0}_{1}_{2}.pcap" -f $Matches[1], $Matches[2], $Matches[3])
        }
    }
}

# ---------------------------------------------------------------------------
# 3. Số liệu, metadata.csv
# ---------------------------------------------------------------------------
Write-Step "So lieu phien"
$Files = @(Get-ChildItem $PcapDir -Filter "$SessionId`_*.pcap" | Sort-Object Name)
if ($Files.Count -eq 0) { throw "Khong co file PCAP nao cho $SessionId trong $PcapDir" }

$kernelDropped = ""; $tcpdumpCaptured = ""
if (Test-Path $TcpdumpLog) {
    $log = Get-Content $TcpdumpLog -Raw
    if ($log -match '(\d+) packets? captured')          { $tcpdumpCaptured = $Matches[1] }
    if ($log -match '(\d+) packets? dropped by kernel') { $kernelDropped  = $Matches[1] }
}

$fileStats = @()
foreach ($f in $Files) {
    # -T -r -M -S: bảng không tiêu đề, số chính xác, thời gian dạng epoch. Cột: file, packets, duration, first, last
    $line = (& $Capinfos -T -r -M -S -c -u -a -e $f.FullName) | Select-Object -Last 1
    $c = $line -split "`t"
    $fileStats += [pscustomobject]@{
        File     = $f
        Packets  = [long]$c[1]
        Duration = [double]$c[2]
        First    = [DateTimeOffset]::FromUnixTimeMilliseconds([long]([double]$c[3] * 1000)).ToLocalTime()
        Last     = [DateTimeOffset]::FromUnixTimeMilliseconds([long]([double]$c[4] * 1000)).ToLocalTime()
    }
    "  {0}: {1} goi, {2:N0} s" -f $f.Name, $c[1], [double]$c[2] | Write-Host
}
$totalPackets  = ($fileStats | Measure-Object Packets -Sum).Sum
$totalDuration = ($fileStats | Measure-Object Duration -Sum).Sum
$dropPct = if ($kernelDropped -ne "" -and $totalPackets -gt 0) { 100.0 * [long]$kernelDropped / ([long]$kernelDropped + $totalPackets) } else { $null }

# Ghi metadata nếu phiên chưa có trong metadata.csv (kể cả khi chạy lại bằng -CheckOnly sau khi dừng sớm bằng Ctrl+C)
$alreadyLogged = (Test-Path $MetaPath) -and @(Import-Csv $MetaPath | Where-Object { $_.session_id -eq $SessionId }).Count -gt 0
if (-not $alreadyLogged) {
    $rows = @(foreach ($s in $fileStats) {
        [pscustomobject]@{
            session_id       = $SessionId
            pcap_file        = $s.File.Name
            start_time       = $s.First.ToString("yyyy-MM-ddTHH:mm:sszzz")
            end_time         = $s.Last.ToString("yyyy-MM-ddTHH:mm:sszzz")
            config           = $Config
            n_user_devices   = $NUserDevices
            active_scenarios = $ActiveScenarios
            pkts_captured    = $s.Packets
            pkts_dropped     = $kernelDropped
            notes            = (@($Notes, "drop tinh cho ca phien") | Where-Object { $_ }) -join "; "
        }
    })
    $rows | Export-Csv -Path $MetaPath -Append -NoTypeInformation -Encoding UTF8
    Write-Ok "Da ghi $($rows.Count) dong vao $MetaPath"
}

# ---------------------------------------------------------------------------
# 4. Nghiệm thu
# ---------------------------------------------------------------------------
Write-Step "Nghiem thu"
$checks = @($CommonChecks)
foreach ($s in $Scenarios) { if ($ScenarioChecks.ContainsKey($s)) { $checks += $ScenarioChecks[$s] } }
$filters = @($checks | ForEach-Object { $_.Filter })

$totals = New-Object long[] $filters.Count
foreach ($s in $fileStats) {
    $counts = Get-FilterCounts $s.File.FullName $filters
    for ($i = 0; $i -lt $filters.Count; $i++) { $totals[$i] += $counts[$i] }
}

$report = @()
$minDuration = $DurationMin * 60 * 0.93
$report += [pscustomobject]@{ Check = "PCAP khong rong"; Filter = "capinfos"; Value = $totalPackets; Result = $(if ($totalPackets -gt 0) { "PASS" } else { "FAIL" }) }
$report += [pscustomobject]@{ Check = "Thoi luong >= 93% ke hoach"; Filter = "capinfos"; Value = ("{0:N0} s" -f $totalDuration); Result = $(if ($totalDuration -ge $minDuration) { "PASS" } else { "FAIL" }) }
$report += [pscustomobject]@{ Check = "Drop < 0.1%"; Filter = "tcpdump"; Value = $(if ($null -ne $dropPct) { "{0:N3}%" -f $dropPct } else { "khong co so lieu" });
    Result = $(if ($null -eq $dropPct) { "CHECK" } elseif ($dropPct -lt 0.1) { "PASS" } else { "FAIL" }) }
for ($i = 0; $i -lt $checks.Count; $i++) {
    $ok = if ($checks[$i].Expect -eq "zero") { $totals[$i] -eq 0 } else { $totals[$i] -gt 0 }
    $report += [pscustomobject]@{ Check = $checks[$i].Name; Filter = $checks[$i].Filter; Value = $totals[$i]; Result = $(if ($ok) { "PASS" } else { "FAIL" }) }
}

$report | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
$reportPath = Join-Path $LogDir "$SessionId`_report.csv"
$report | Export-Csv -Path $reportPath -NoTypeInformation -Encoding UTF8
$fails = @($report | Where-Object { $_.Result -eq "FAIL" }).Count
if ($fails -eq 0) { Write-Ok "Tat ca tieu chi tu dong deu dat. Bao cao: $reportPath" }
else { Write-Fail "$fails tieu chi khong dat. Bao cao: $reportPath" }
Write-Host "Cac tieu chi can nhin bang mat (I/O Graph, doi chieu nhat ky) xem trong scenarios\$Main`_*.md muc 5."
