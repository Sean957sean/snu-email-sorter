#!/usr/bin/env python3
"""
SNU Mail Sorter
서울대학교 학생 Gmail을 자동으로 분류합니다.
Gmail API 없이 IMAP 표준 프로토콜로 동작합니다.
"""

import sys
import argparse
from src.auth import prompt_credentials, connect_imap
from src.sorter import sort_inbox


def prompt_mail_count() -> int:
    """분류할 메일 수를 입력받습니다."""
    print()
    while True:
        raw = input("  최근 몇 개의 메일을 분류할까요? (숫자 입력, 기본 100): ").strip()
        if raw == "":
            return 100
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("  [!] 1 이상의 숫자를 입력해 주세요.")


def main():
    parser = argparse.ArgumentParser(description="SNU Gmail 자동 분류기 (IMAP)")
    parser.add_argument("--dry-run", action="store_true", help="실제 변경 없이 미리보기")
    args = parser.parse_args()

    print("=" * 60)
    print("        SNU Mail Sorter")
    print("  서울대학교 Gmail 자동 분류기 (IMAP)")
    print("=" * 60)

    if args.dry_run:
        print("\n[ DRY RUN 모드 — 실제 이동은 일어나지 않습니다 ]")

    # 이메일 + 앱 비밀번호 입력
    email, password = prompt_credentials()

    # 분류할 메일 수 입력
    max_emails = prompt_mail_count()
    print(f"\n  최근 {max_emails}개 메일을 분류합니다.")

    # IMAP 연결
    print("\nIMAP 서버에 연결 중...")
    try:
        mail = connect_imap(email, password)
    except (ConnectionError, PermissionError) as e:
        print(e)
        sys.exit(1)

    # 메일 분류
    print()
    try:
        sort_inbox(mail, max_emails=max_emails, dry_run=args.dry_run)
    finally:
        mail.logout()
        print("\n  연결 종료")


if __name__ == "__main__":
    main()
