# SNU Mail Sorter

서울대학교 학생 Gmail을 자동으로 분류하는 해커톤 프로젝트입니다.

## 분류 규칙

| 메일 유형 | 조건 | 라벨 |
|---|---|---|
| 카테고리 메일 | 제목에 `[학술]`, `[공지]` 등 대괄호 존재 | `메일분류/학술`, `메일분류/공지` 등 |
| 개인 중요 메일 | 대괄호 없음 + (처음 받는 발신자 or 1:1 수신) | `메일분류/개인` |
| 기타 | 대괄호 없음 + 자주 오는 발신자 | `메일분류/기타` |

## 설치

```bash
cd snu-mail-sorter
pip install -r requirements.txt
```

## Google Cloud 설정

1. [Google Cloud Console](https://console.cloud.google.com) 접속
2. 새 프로젝트 생성
3. **Gmail API** 활성화
4. OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱 유형)
5. `credentials.json` 다운로드 후 이 폴더에 저장

## 실행

```bash
# 미리보기 (변경 없음)
python main.py --dry-run

# 실제 실행 (받은편지함 최근 200개)
python main.py

# 더 많은 메일 처리
python main.py --max 500
```

첫 실행 시 브라우저에서 구글 계정 로그인 및 권한 허용을 요청합니다.  
이후에는 `token.pickle`에 인증 정보가 저장되어 자동 로그인됩니다.
