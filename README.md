# YouTube 채널 수집기

키워드를 입력하면 그 주제를 다루는 **한국어 교육·강의 채널**을 찾아, AI로 한 번 더 걸러내고 공개된 연락처까지 정리해 주는 수집 도구입니다.

브라우저 UI와 CLI 두 가지 방식으로 실행할 수 있고, 모든 처리는 실행한 PC 안에서만 이뤄집니다.

```
키워드 → YouTube 검색 → 1차 규칙 필터 → AI 심층 검수 → 연락처 추출 → JSON
```

---

## 왜 만들었나

YouTube Data API는 키워드로 **영상**을 찾아 줄 뿐, "이 채널이 실제로 강의를 하는 채널인가"는 알려주지 않습니다. 검색 결과를 그대로 쓰면 게임 실황, 브이로그, AI TTS 양산형 채널, 기업 홍보 채널이 잔뜩 섞여 들어옵니다.

그래서 세 겹으로 거릅니다.

1. **규칙 필터** — 한국어 비율, 최근 업로드 여부, 연락처 유무, 교육 키워드
2. **AI 심층 검수** — 자막을 읽고, 자막이 없으면 썸네일을 봅니다
3. **중복 차단** — 한 번 확인한 채널은 다시 API를 쓰지 않습니다

---

## 주요 기능

### 멀티모달 AI 검수 (OpenAI)

- **자막 분석** — `youtube-transcript-api`로 영상 자막 앞 1,500자를 뽑아, 실제로 지식을 전달하는 콘텐츠인지 판별합니다.
- **썸네일 비전 분석** — 자막이 없거나 막혀 있으면 썸네일 이미지를 대신 넘겨 판단합니다. 강의 슬라이드·코딩 화면·설명형 레이아웃을 단서로 씁니다.
- **해시태그 보조 판단** — 영상 제목·설명의 `#태그`를 추출해 판단 근거에 함께 넣습니다.
- **금융·기업 채널 차단** — 주식/코인/부동산 투기 채널과 기업·기관 공식 채널은 명시적으로 거부합니다.
- **Rate limit 대응** — 429(TPM/RPM) 발생 시 지연 후 재시도하고, 연속 3회 실패하면 수집분을 저장하고 안전하게 종료합니다.
- `USE_OPENAI_FILTER = False` 로 끄면 OpenAI를 전혀 호출하지 않습니다. (비용 0, 대신 정확도 하락)

### 연락처 추출

채널 설명에서 **이메일·전화번호·카카오톡 ID·외부 링크**를 정규식으로 뽑습니다.

채널 소개의 "이메일 주소 보기" 값은 API로 내려오지 않기 때문에(웹에서 CAPTCHA를 거쳐야 함), 채널 설명이 비어 있으면 **최근 영상 몇 개의 설명란까지 합쳐서** 한 번 더 찾습니다. 실제로 문의처를 영상 설명에만 적어두는 채널이 많습니다.

### API 할당량 최적화

- 채널 상세 조회는 **50개씩 batch**로 묶습니다. 채널마다 개별 호출하는 구조 대비 90% 이상 절약됩니다.
- 제외 대상은 **상세 조회 전에** 걸러내므로 할당량도 AI 비용도 발생하지 않습니다.
- `quotaExceeded` 를 감지하면 그때까지의 결과를 파일로 저장한 뒤 다음 API 키로 넘어갑니다.

### 중복 방지 (Global Checked Engine)

`data/processed_ids.json` 과 기존 결과 파일을 함께 스캔해, **수집됐든 탈락했든 한 번이라도 본 채널 ID**를 전부 추적합니다. 재실행 시 같은 채널에 API를 다시 쓰지 않습니다.

결과는 `data/youtube_channels_{키워드}.json` 으로 키워드별 분리 저장되며, 기존 파일이 있으면 누적 병합(upsert)됩니다.

### 제외 명단 (선택)

이미 접촉이 끝난 채널을 다시 수집하지 않도록 막는 기능입니다. 손으로 관리해 온 리스트에는 `channel_id`가 거의 없고 채널명이나 이메일만 있는 경우가 많아, **4가지 식별자를 모두 대조**합니다.

| 식별자 | 대조 시점 | 정확도 |
|---|---|---|
| 채널 ID | 검색 직후 (상세 조회 전) | 확실 |
| 채널명 (완전일치) | 검색 직후 (상세 조회 전) | 동명이인 주의 |
| 채널 주소 (`@핸들` / `/channel/UC...`) | 상세 조회 후 | 확실 |
| 이메일 | 상세 조회 후 | 확실 |

채널 주소는 형태가 제각각이라 파서를 거칩니다. 아래는 전부 같은 채널로 인식합니다.

```
@example_channel
example_channel
https://www.youtube.com/@example_channel
https://www.youtube.com/@example_channel?si=xxxx
https://www.youtube.com/@%EC%98%88%EC%8B%9C      ← 퍼센트 인코딩된 한글 핸들
https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx
```

핸들·이메일로 차단된 채널은 그 채널 ID를 `processed_ids.json`에 등록해, 다음 실행부터는 검색 단계에서 바로 걸립니다. 다만 **채널명 매칭은 영구 등록하지 않습니다** — 동명이인 오탐이 굳어지는 것을 막기 위해서입니다.

명단 갱신:

```bash
python tools/build_exclusion.py
```

`data/exclusion_sources/` 안의 파일을 전부 읽어 `data/excluded_channels.json` 을 만듭니다. `.json`과 `.xlsx`를 지원하고, 여러 번 돌려도 결과는 같습니다(중복 추가 없음). 형식은 [`data/exclusion_sources/example_mail_list.json`](data/exclusion_sources/example_mail_list.json)을 참고하세요.

---

## 설치

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

`.env`를 열어 API 키를 채웁니다.

```env
YOUTUBE_API_KEY_1=AIza...
YOUTUBE_API_KEY_2=AIza...
OPENAI_API_KEY=sk-proj-...
```

- **YouTube Data API 키** (필수) — [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성 → `YouTube Data API v3` 사용 설정 → API 키 발급
- **OpenAI API 키** (선택) — [platform.openai.com](https://platform.openai.com/api-keys). 비워두면 AI 검수 없이 동작합니다.

> [!IMPORTANT]
> `.env`에는 키가 평문으로 들어갑니다. `.gitignore`로 막혀 있지만, 폴더를 통째로 남에게 전달할 때는 `.env`를 지우고 전달하세요.

---

## 실행

### 방법 1. 브라우저 UI

```bash
python app.py
```

브라우저가 자동으로 열립니다 (`http://127.0.0.1:5000`). 화면에서 API 키 등록 → 키워드 입력 → 수집 조건 조절 → 실행 → 결과 내려받기까지 전부 할 수 있습니다. 윈도우에서는 `run_web_ui.bat` 더블클릭으로도 실행됩니다.

서버는 `127.0.0.1`에만 바인딩되어 외부에서 접근할 수 없고, 입력한 키는 이 폴더의 `.env`에만 저장됩니다. 브라우저로 되돌려주는 키 값은 항상 마스킹됩니다.

자세한 사용법은 [docs/사용설명서.md](docs/사용설명서.md)에 있습니다.

### 방법 2. CLI

```bash
python youtube_channel_crawler.py
```

```bash
python youtube_channel_crawler.py --auto
```

앞은 대화형(요약 확인 후 Enter), 뒤는 프롬프트 없는 무인 실행입니다.

키워드는 `keywords/keywords_N.txt`에 한 줄에 하나씩 적습니다. **파일 번호와 API 키 번호가 1:1로 짝**을 이룹니다.

```
YOUTUBE_API_KEY_1  ↔  keywords/keywords_1.txt
YOUTUBE_API_KEY_2  ↔  keywords/keywords_2.txt
```

짝이 되는 키가 없는 키워드 파일은 실행되지 않습니다. 특정 키의 할당량이 소진되면 그 키의 남은 키워드는 건너뛰고 다음 키로 자동 전환합니다.

### 방법 3. 매일 자동 실행 (Windows)

`run_auto.ps1`을 윈도우 작업 스케줄러에 등록하면 창 없이 매일 자동 실행됩니다. 중복 실행 방지(lock), 실행 결과 한 줄 요약(`logs/last_run.txt`), 전체 로그 누적(`logs/crawler_run.log`)이 포함되어 있습니다.

```text
2026-09-03 11:12  성공  신규 23건  (8분 소요)

  youtube_channels_MCP.json (+7)
  youtube_channels_AI_에이전트.json (+6)
```

---

## 설정 (`src/config.py`)

```python
MAX_RESULTS_PER_KEYWORD = 100   # 키워드당 최대 수집 채널 수
KOREAN_ONLY = True              # 한국 채널만
CONTACTABLE_ONLY = True         # 연락처가 있는 채널만
EDUCATION_ONLY = True           # 강의/교육 채널만
LAST_UPLOAD_MONTHS = 6          # 최근 N개월 내 업로드한 활성 채널만 (None = 제한 없음)
CHANNEL_AGE_MONTHS = None       # 채널 개설 기간 제한

CONTACT_FROM_VIDEOS = True      # 채널 설명에 연락처가 없으면 영상 설명란까지 검사
CONTACT_VIDEO_SCAN_COUNT = 5    # 검사할 최근 영상 수 (채널당 API 2유닛 추가)

USE_EXCLUSION_LIST = True       # 제외 명단 사용
EXCLUSION_MATCH_TITLE = True    # 채널명 완전일치로도 차단 (동명이인 오탐 시 False)

USE_OPENAI_FILTER = True        # AI 심층 검수 사용
OPENAI_MODEL = 'gpt-4o'         # 사용할 OpenAI 모델
```

브라우저 UI에서 조절하는 값은 이 파일의 해당 줄을 직접 고쳐 씁니다(주석은 그대로 보존).

---

## 출력 형식

```json
{
  "channel_id": "UC1234567890",
  "title": "개발자 파이썬 튜브",
  "description": "파이썬 자동화를 알려드립니다. 문의: python_dev@example.com",
  "custom_url": "@python_dev",
  "published_at": "2023-01-15T00:00:00Z",
  "last_upload_date": "2026-05-18T10:30:00Z",
  "country": "KR",
  "is_korean": true,
  "subscriber_count": "4520",
  "video_count": "72",
  "view_count": "153402",
  "channel_url": "https://www.youtube.com/channel/UC1234567890",
  "custom_channel_url": "https://www.youtube.com/@python_dev",
  "email": "python_dev@example.com",
  "phone": "N/A",
  "kakao": "N/A",
  "other_links": "https://blog.example.com/python_dev",
  "contactable": true,
  "thumbnail": "https://yt3.ggpht.com/.../photo.jpg",
  "latest_video_id": "ab_12cdeFGh",
  "latest_video_title": "[파이썬] 10분 만에 웹 자동화 만들기",
  "latest_video_thumb": "https://i.ytimg.com/vi/ab_12cdeFGh/hqdefault.jpg",
  "collected_date": "2026-05-20 15:40:00",
  "search_keyword": "파이썬 자동화",
  "priority_review": false
}
```

채널 소개에 `문의` `강연` `강의` `협업` `제안` 같은 단어가 있으면 `priority_review: true`가 붙고 제목 앞에 `⭐ [우선검수]` 표시가 붙습니다.

---

## 프로젝트 구조

```text
.
├── app.py                        브라우저 UI 서버 (Flask, 127.0.0.1 전용)
├── index.html                    UI 화면
├── youtube_channel_crawler.py    CLI 진입점
├── run_auto.ps1                  작업 스케줄러용 무인 실행 스크립트
├── run_web_ui.bat                Windows 실행 도우미
│
├── src/
│   ├── config.py                 수집 조건 설정
│   ├── crawler.py                수집 파이프라인 · batch API 요청 관리
│   ├── ai_filter.py              OpenAI 자막/비전 판별 엔진
│   ├── filters.py                한글 판별 · 해시태그 추출 · 1차 규칙 필터
│   ├── contact.py                이메일/전화/카카오톡 정규식 추출기
│   └── exclusion.py              제외 명단 대조 (ID/채널명/핸들/이메일)
│
├── tools/
│   └── build_exclusion.py        원본 리스트 → 제외 명단 생성
│
├── keywords/                     키워드 파일 (keywords_N.txt)
├── data/                         수집 결과 · 중복 방지 DB (git 제외)
└── logs/                         실행 기록 (git 제외)
```

---

## 할당량과 비용

- YouTube Data API는 **키(프로젝트)당 하루 10,000 units** 무료입니다. 태평양 표준시 자정(한국 시간 오후 4~5시경)에 초기화됩니다.
- 기본 설정(키워드당 100개) 기준 **API 키 1개당 하루 키워드 3~5개** 정도가 적당합니다. 더 넣으면 뒷부분 키워드는 한도에 걸려 수집되지 않습니다.
- 하루에 여러 번 돌려도 그날 총량은 늘지 않습니다.
- OpenAI 검수를 켜면 사용량만큼 요금이 발생합니다.

## 외부로 나가는 데이터

수집 결과 파일은 외부로 전송되지 않습니다.

| 대상 | 전송 내용 |
|---|---|
| Google (YouTube Data API) | 검색 키워드 |
| YouTube | 영상 자막 요청 |
| OpenAI | 채널명·설명·최신 영상 제목·해시태그·자막 일부(1,500자), 자막이 없으면 썸네일 이미지 URL |

---

## 주의사항

> [!WARNING]
> **수집 결과에는 채널 운영자의 이메일·전화번호 등 개인정보가 포함됩니다.** 보관·이용·파기에 대해 거주 지역의 개인정보 보호법(한국은 개인정보 보호법, EU는 GDPR 등)을 반드시 확인하고, 수집한 연락처를 동의 없는 광고성 메일 발송에 사용하지 마세요.

- AI가 걸러내더라도 100% 강의 채널이라고 볼 수 없습니다. **사람의 검수가 반드시 필요합니다.**
- 연락처는 공개된 소개글에서 자동 추출한 것이라, 담당자가 아닌 주소가 섞여 있을 수 있습니다.
- 이 도구는 YouTube의 **공식 Data API**만 사용하며 페이지를 스크래핑하지 않습니다. 사용 시 [YouTube API 서비스 약관](https://developers.google.com/youtube/terms/api-services-terms-of-service)을 준수하세요.
