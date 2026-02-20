# 🎯 YouTube 채널 자동 수집기

YouTube Data API v3를 사용하여 키워드 기반으로 채널을 자동 수집하는 Python 스크립트입니다.

**완전 자동화 + 스마트 필터링**: 키워드 파일만 만들면 활발하고 연락 가능한 한국 채널만 자동으로 수집합니다!

## ✨ 주요 기능

### 🤖 완전 자동화
- ✅ **키워드 파일 기반 자동 수집** - keywords.txt에 키워드만 입력하면 자동 실행
- ✅ **키워드당 50개씩 자동 수집** - 설정 변경 가능
- ✅ **중복 자동 제거** - 같은 채널은 한 번만 저장
- ✅ **부족분 자동 보충** - 목표 개수 달성까지 자동 추가 검색 (최대 5회)

### 🎯 스마트 필터링
- ✅ **한국 채널 필터링** - 국가 설정 또는 한글 포함 여부로 판단
- ✅ **연락처 필수 필터** - 연락 수단이 없는 채널 자동 제외
- ✅ **채널 활동 필터링** - 최근 6개월 이내 활동 채널만 (기본값)
- ✅ **신규 채널 필터링** - 채널 개설 기간 제한 가능 (선택)
- ✅ **관련성순 정렬** - 검색어와 가장 관련성 높은 채널 우선

### 📧 연락처 자동 추출
채널 설명에서 다음 연락처를 자동으로 추출:
- 이메일 주소
- 전화번호 (한국 형식)
- 카카오톡 ID
- 기타 링크 (블로그, 개인 웹사이트 등)

### 💾 효율적인 데이터 관리
- ✅ **날짜별 파일 자동 생성** - YYMMDD_youtube_channels_키워드.json
- ✅ **검색어별 자동 분류** - 각 키워드마다 별도 JSON 파일
- ✅ **업데이트 모드** - 같은 날짜/키워드로 재실행 시 새 채널만 추가
- ✅ **완전한 채널 정보** - 구독자, 동영상 수, 조회수, 최근 활동일 등

## 🚀 빠른 시작

### 1. 설치

```bash
# 필수 라이브러리 설치
pip install google-api-python-client python-dotenv
```

또는

```bash
pip install -r requirements.txt
```

### 2. API 키 설정

#### 2-1. YouTube Data API 키 발급

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성
3. "API 및 서비스" > "라이브러리" > "YouTube Data API v3" 활성화
4. "사용자 인증 정보" > "API 키" 생성
5. API 키 복사

#### 2-2. .env 파일 생성

프로젝트 폴더에 `.env` 파일 생성:

```
YOUTUBE_API_KEY=여기에_발급받은_API_키_입력
```

**예시:**
```
YOUTUBE_API_KEY=이곳에 복사한 API 키 붙여넣기
```


### 3. 실행

```bash
python youtube_channel_crawler.py
```

**끝!** 자동으로 모든 키워드를 순서대로 처리합니다.

## 📊 실행 예시

```
============================================================
🎯 YouTube 채널 자동 수집 시작
============================================================
📋 키워드 파일: keywords.txt
📊 총 키워드 수: 5개
🎯 키워드당 목표: 50개
🇰🇷 한국 채널만: 예
📧 연락처 필수: 예
🎬 최근 활동: 6개월 이내
📊 정렬: 관련성순
============================================================

키워드 목록:
  1. 파이썬
  2. 요리
  3. 게임
  4. 영어공부
  5. 운동

계속하려면 Enter를 누르세요... (Ctrl+C로 취소)
```

Enter를 누르면 자동으로 시작:

```
############################################################
# 진행: 1/5 - '파이썬'
############################################################

============================================================
YouTube 채널 크롤링 시작: '파이썬'
💾 저장 파일: 250220_youtube_channels_파이썬.json
🎯 목표: 새 채널 50개 수집
============================================================

[검색 1회-1/100] 채널A 정보 수집 중...
  ✓ 구독자: 1200, 동영상: 15
  ✓ 진행: 1/50개 수집 완료
  📧 연락처: 이메일: contact@example.com

[검색 1회-2/100] 채널B 정보 수집 중...
  ⊝ 연락처 없음 - 제외

[검색 1회-3/100] 채널C 정보 수집 중...
  ⊝ 최근 6개월간 활동 없음 - 제외

============================================================
ℹ️  중복 채널 제외: 3개
ℹ️  한국 채널 아님으로 제외: 5개
ℹ️  최근 활동 없음으로 제외: 15개
ℹ️  연락처 없음으로 제외: 12개
✓ 새로 추가된 채널: 50개
✓ 전체 채널: 50개
📧 연락 가능 채널: 50/50개 (100%)
============================================================

✅ '파이썬' 완료!
```

## 📁 결과 파일

각 키워드별로 날짜와 함께 자동 생성:

```
프로젝트 폴더/
  ├── .env                                      ← API 키
  ├── keywords.txt                              ← 입력 키워드
  ├── youtube_channel_crawler.py                ← 메인 스크립트
  │
  ├── 250220_youtube_channels_파이썬.json      ← 2월 20일
  ├── 250220_youtube_channels_요리.json        ← 2월 20일
  ├── 250221_youtube_channels_파이썬.json      ← 2월 21일 (추가 수집)
  └── 250221_youtube_channels_영어공부.json    ← 2월 21일
```

## 📋 JSON 데이터 형식

```json
[
  {
    "channel_id": "UC1234567890",
    "title": "파이썬Master",
    "description": "파이썬 강의를 제공합니다.\n문의: contact@example.com",
    "published_at": "2023-01-15T00:00:00Z",
    "last_upload_date": "2024-02-15T10:30:00Z",
    "country": "KR",
    "is_korean": true,
    
    "subscriber_count": "4780",
    "video_count": "120",
    "view_count": "263482",
    
    "channel_url": "https://www.youtube.com/channel/UC1234567890",
    
    "email": "contact@example.com",
    "phone": "010-1234-5678",
    "kakao": "pythonking",
    "other_links": "blog.naver.com/pythonmaster",
    
    "contactable": true
  }
]
```

## ⚙️ 설정 변경

`youtube_channel_crawler.py` 파일을 열어서 다음 부분을 수정하세요:

```python
# main() 함수 내 설정 부분

MAX_RESULTS_PER_KEYWORD = 50    # 키워드당 수집 개수
KOREAN_ONLY = True               # 한국 채널만
ORDER = 'relevance'              # 정렬: relevance(관련성), date(최신순), viewCount(조회수)
CONTACTABLE_ONLY = True          # 연락처 필수

# 기간 필터
CHANNEL_AGE_MONTHS = None        # 채널 개설 기간 제한 (None=제한없음, 12=1년이내)
LAST_UPLOAD_MONTHS = 6           # 최근 업로드 기간 제한 (6=6개월이내)
```

### 설정 예시

#### 신규 활발 채널만
```python
CHANNEL_AGE_MONTHS = 12     # 1년 이내 개설
LAST_UPLOAD_MONTHS = 3      # 3개월 이내 활동
```

#### 활발한 채널만 (개설일 무관)
```python
CHANNEL_AGE_MONTHS = None   # 제한 없음
LAST_UPLOAD_MONTHS = 1      # 1개월 이내 활동
```

#### 더 많은 채널 수집
```python
MAX_RESULTS_PER_KEYWORD = 100   # 키워드당 100개
```

## ⚠️ 주의사항

### API 할당량

- **무료 할당량**: 하루 10,000 units
- **예상 소비**: 키워드 1개당 약 400 units
- **하루 약 25개 키워드 처리 가능**

**권장 사항**:
- 한 번에 10-15개 키워드 처리
- 여러 날에 걸쳐 나눠서 실행

### 할당량 초과 시

에러: `quotaExceeded`

**해결 방법**:
1. 다음 날까지 대기 (자정 PST 기준 리셋)
2. 키워드 개수 줄이기
3. `MAX_RESULTS_PER_KEYWORD` 값 줄이기

### 실행 시간

- 키워드당 약 3-7분 소요
- 10개 키워드 = 약 30-70분

## 🎯 필터링 기준

### 한국 채널
- 채널 국가 = "KR" OR
- 제목에 한글 포함 OR
- 설명에 한글 포함

### 연락 가능
- 이메일 OR
- 전화번호 OR
- 카카오톡 ID OR
- 기타 링크

### 활동 중
- 최근 6개월 이내 영상 업로드 (기본값)

## 🔍 트러블슈팅

### "API key not valid" 오류
- `.env` 파일이 올바른 위치에 있는지 확인
- API 키가 정확히 입력되었는지 확인

### "quotaExceeded" 오류
- API 할당량 초과
- 다음 날까지 대기 또는 키워드 개수 줄이기

### "keywords.txt 파일이 없습니다"
- 프로젝트 폴더에 `keywords.txt` 파일 생성
- 자동으로 예시 파일 생성됨

### 목표 개수를 채우지 못함
- 정상입니다 (중복, 필터링으로 제외됨)
- 자동으로 추가 검색 (최대 5회)
- 조건 완화를 원하면 설정 변경

## 💡 유용한 팁

### 1. 키워드 선정

**좋은 키워드**:
- 파이썬, 요리, 게임 (넓은 주제)
- 엑셀 강의 (구체적 + 수요 높음)

**피할 키워드**:
- 너무 구체적: "파이썬 3.11 비동기 프로그래밍"
- 너무 일반적: "영상"

### 2. 매일 조금씩 실행

```
Day 1: 10개 키워드 → 500개 채널
Day 2: 10개 키워드 → 500개 채널
Week 1: 3,500개 채널
```

### 3. 데이터 분석

```python
import json

with open('250220_youtube_channels_파이썬.json', 'r', encoding='utf-8') as f:
    channels = json.load(f)

# 이메일 있는 채널
email_channels = [ch for ch in channels if ch['email'] != 'N/A']
print(f"이메일: {len(email_channels)}개")

# 구독자 1만 이상
popular = [ch for ch in channels 
           if ch['subscriber_count'] != 'N/A' 
           and int(ch['subscriber_count']) >= 10000]
print(f"구독자 1만+: {len(popular)}개")
```

## 🔒 보안

### API 키 보호
- ✅ `.env` 파일에 저장
- ✅ `.gitignore`에 `.env` 추가
- ❌ 코드에 직접 입력 금지
- ❌ GitHub에 업로드 금지

### .gitignore 예시
```
.env
*.json
__pycache__/
*.pyc
```

## 📦 필요한 파일

```
프로젝트 폴더/
├── .env                              (필수) API 키
├── keywords.txt                      (필수) 키워드 목록
├── youtube_channel_crawler.py        (필수) 메인 스크립트
└── requirements.txt                  (선택) 라이브러리 목록
```

## 🎓 라이선스

교육 및 개인 사용 목적으로 자유롭게 사용 가능합니다.

YouTube API 사용 시 [YouTube API 서비스 약관](https://developers.google.com/youtube/terms/api-services-terms-of-service)을 준수해야 합니다.

---

**Happy Crawling! 🎉**

*v2.0 - 완전 자동화 + 스마트 필터링*