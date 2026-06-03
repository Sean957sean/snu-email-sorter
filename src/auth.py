import imaplib
import getpass
import re
from typing import Tuple

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SNU_EMAIL_PATTERN = re.compile(r"^[\w.+-]+@snu\.ac\.kr$", re.IGNORECASE)


def prompt_credentials() -> Tuple[str, str]:
    """서울대 이메일과 앱 비밀번호를 입력받습니다."""
    print()
    # ── 이메일 입력 ───────────────────────────────────────────────
    while True:
        email = input("  서울대학교 이메일을 입력하세요 (예: gildong@snu.ac.kr): ").strip()
        if not email:
            print("  [!] 이메일을 입력해 주세요.")
            continue
        if not SNU_EMAIL_PATTERN.match(email):
            print("  [!] @snu.ac.kr 이메일만 사용 가능합니다.")
            continue
        break

    # ── 앱 비밀번호 입력 ─────────────────────────────────────────
    print()
    print("  ※ 앱 비밀번호가 필요합니다.")
    print("    발급 방법: https://myaccount.google.com/apppasswords")
    print("    (Google 계정 → 보안 → 2단계 인증 → 앱 비밀번호)")
    print()
    password = getpass.getpass("  앱 비밀번호를 입력하세요 (입력 내용은 화면에 표시되지 않음): ")
    # Google 앱 비밀번호는 'abcd efgh ijkl mnop' 형태로 복사되는 경우가 있어 공백 제거
    password = password.replace(" ", "").strip()

    return email.lower(), password


def connect_imap(email: str, password: str) -> imaplib.IMAP4_SSL:
    """IMAP 서버에 연결하고 인증된 IMAP 객체를 반환합니다."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    except Exception:
        raise ConnectionError(
            f"\n[오류] IMAP 서버({IMAP_HOST})에 연결할 수 없습니다.\n"
            "  인터넷 연결을 확인해 주세요."
        )

    # imaplib 기본 인코딩이 ASCII라 한글 등 non-ASCII 문자를 처리 못함 → UTF-8로 변경
    mail._encoding = "utf-8"

    try:
        mail.login(email, password)
    except imaplib.IMAP4.error:
        raise PermissionError(
            "\n[오류] 로그인에 실패했습니다.\n"
            "  1. 이메일 주소가 올바른지 확인\n"
            "  2. 앱 비밀번호(일반 비밀번호 X)를 입력했는지 확인\n"
            "     발급: https://myaccount.google.com/apppasswords\n"
            "  3. Gmail 설정 → 전달 및 POP/IMAP → IMAP 사용이 켜져 있는지 확인\n"
        )

    print(f"  ✓ 로그인 성공 — {email}")
    return mail
