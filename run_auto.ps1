# ============================================================
# run_auto.ps1  -  윈도우 작업 스케줄러 자동 실행용
# ============================================================

Set-Location $PSScriptRoot

# ── 경로 ─────────────────────────────────────────────────
$LOG_DIR   = Join-Path $PSScriptRoot 'logs'
$LOG_FILE  = Join-Path $LOG_DIR 'crawler_run.log'
$LAST_RUN  = Join-Path $LOG_DIR 'last_run.txt'
$LOCK_FILE = Join-Path $PSScriptRoot '.crawler.lock'

if (!(Test-Path $LOG_DIR)) { New-Item -Path $LOG_DIR -ItemType Directory | Out-Null }

# ── 한글 출력 인코딩 ─────────────────────────────────────
# 파이썬(UTF-8) 출력을 PowerShell이 제대로 읽어오게 맞춰줍니다.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$startTime = Get-Date

# ── last_run.txt 기록 함수 ───────────────────────────────
function Write-LastRun {
    param(
        [string]$Status,        # 성공 / 실패 / 건너뜀
        [string]$Detail,        # "신규 23건" 또는 실패 사유
        [string[]]$FileLines = @(),
        [bool]$WithDuration = $true
    )
    $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm')
    $line  = "$stamp  $Status  $Detail"
    if ($WithDuration) {
        $mins = [int][Math]::Round(((Get-Date) - $startTime).TotalMinutes)
        $line += "  (${mins}분 소요)"
    }

    $body = @($line)
    if ($FileLines.Count -gt 0) {
        $body += ''
        $body += $FileLines
    }
    # 메모장에서 한글이 깨지지 않도록 BOM 포함 UTF-8로 저장
    $body | Out-File -FilePath $LAST_RUN -Encoding utf8 -Force
}

# ── 중복 실행 방지 ───────────────────────────────────────
if (Test-Path $LOCK_FILE) {
    $oldPid = Get-Content $LOCK_FILE -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Host "이미 다른 크롤러 인스턴스(PID: $oldPid)가 실행 중이라 이번 실행은 건너뜁니다."
        Write-LastRun -Status '건너뜀' -Detail "이미 실행 중 (PID: $oldPid)" -WithDuration $false
        exit 0
    }
}
$PID | Out-File -FilePath $LOCK_FILE -Encoding UTF8 -Force

# ── 실행 ─────────────────────────────────────────────────
try { Start-Transcript -Path $LOG_FILE -Append -Force | Out-Null } catch { }

$failReason  = $null
$newTotal    = 0
$newFiles    = @()
$completed   = $false

try {
    # 파이썬 존재 확인 (작업 스케줄러는 PATH가 다를 수 있습니다)
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "python 을 찾을 수 없습니다 (작업 스케줄러의 PATH 확인 필요)"
    }

    # 필수 라이브러리 확인 (없을 때만 자동 설치)
    # 평소에는 설치를 시도하지 않으므로 불필요한 외부 통신이 발생하지 않습니다.
    # requirements.txt 의 버전을 올린 경우에는 pip install -r requirements.txt 를 직접 실행하세요.
    & python -c "import googleapiclient, dotenv, youtube_transcript_api, openai" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "필수 라이브러리가 없어 설치를 시작합니다..."
        & python -m pip install -r requirements.txt -q

        # 설치 명령의 종료 코드로 바로 판단하지 않습니다.
        # 네트워크가 잠시 불안정해도 이미 설치되어 있으면 실행할 수 있어야 하므로,
        # 최종 판정은 아래 import 재확인으로 합니다.
        & python -c "import googleapiclient, dotenv, youtube_transcript_api, openai" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "라이브러리 자동 설치 실패 (pip install -r requirements.txt 를 직접 실행해 주세요)"
        }
        Write-Host "설치 완료."
    }

    Write-Host "크롤러를 시작합니다..."
    & python youtube_channel_crawler.py --auto | Tee-Object -Variable crawlerOut
    $pyExit = $LASTEXITCODE

    if ($null -eq $crawlerOut) { $crawlerOut = @() }

    # ── 크롤러 출력에서 신규 건수 집계 ───────────────────
    # 크롤러가 마지막에 찍는 요약 줄을 읽습니다.
    #   " 1. [API#1] MCP    - ✅  40개 채널 (신규: 7개)"
    #   "    └─ 파일: data\youtube_channels_MCP.json"
    for ($i = 0; $i -lt $crawlerOut.Count; $i++) {
        $line = [string]$crawlerOut[$i]

        if ($line -match '최종 통계') { $completed = $true }

        if ($line -match '\(신규:\s*(\d+)개\)') {
            $n = [int]$Matches[1]
            $newTotal += $n
            if ($n -gt 0 -and ($i + 1) -lt $crawlerOut.Count) {
                $nextLine = [string]$crawlerOut[$i + 1]
                if ($nextLine -match '파일:\s*(.+?)\s*$') {
                    $name = Split-Path $Matches[1] -Leaf
                    $newFiles += ("  {0} (+{1})" -f $name, $n)
                }
            }
        }
    }

    # ── 성공/실패 판정 ───────────────────────────────────
    $all = ($crawlerOut -join "`n")

    if ($pyExit -ne 0) {
        if ($all -match 'OpenAI API가 연속 3회 실패') { $failReason = 'OpenAI API 연속 오류' }
        else { $failReason = "크롤러가 오류로 종료 (종료 코드 $pyExit)" }
    }
    elseif (-not $completed) {
        # 종료 코드는 0이지만 최종 요약이 없는 경우.
        # .env 나 키워드 파일 문제로 크롤러가 아무것도 하지 않고 끝난 상황입니다.
        # 이걸 잡지 않으면 매일 "신규 0건"으로 보여서 문제를 눈치채지 못합니다.
        if     ($all -match 'API 키가 설정되지 않았습니다')      { $failReason = 'YouTube API 키 미설정 (.env 확인)' }
        elseif ($all -match 'OpenAI API 키가 설정되지 않았습니다') { $failReason = 'OpenAI API 키 미설정 (.env 확인)' }
        elseif ($all -match '조합이 없습니다')                   { $failReason = '키워드 파일 없음 (keywords 폴더 확인)' }
        else                                                     { $failReason = '크롤러가 끝까지 실행되지 않음' }
    }
}
catch {
    $failReason = $_.Exception.Message
}
finally {
    # ── 결과 기록 ────────────────────────────────────────
    if ($failReason) {
        Write-Host ""
        Write-Host "실패: $failReason" -ForegroundColor Red
        Write-LastRun -Status '실패' -Detail $failReason
    }
    else {
        Write-Host ""
        Write-Host "완료: 신규 $newTotal 건" -ForegroundColor Green
        Write-LastRun -Status '성공' -Detail "신규 ${newTotal}건" -FileLines $newFiles
    }

    # 잠금 해제
    if (Test-Path $LOCK_FILE) {
        $storedPid = Get-Content $LOCK_FILE -ErrorAction SilentlyContinue
        if ($storedPid -eq $PID) { Remove-Item $LOCK_FILE -Force -ErrorAction SilentlyContinue }
    }

    try { Stop-Transcript | Out-Null } catch { }
}

if ($failReason) { exit 1 } else { exit 0 }
