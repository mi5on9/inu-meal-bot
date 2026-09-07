import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# 디스코드 웹훅 URL (GitHub Secrets 우선 적용)
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1544879632577470587/fbc0TdvyVlERYLiwkwwuhJfBT5YwWM2ZyniwjWAgTNgfR7keBUY6Vo-AEoZnuHrRDOu9",
)


def clean_menu_content(raw_text):
    """가격, 날짜 및 불필요한 기호를 제거하고 순수 메뉴만 깔끔하게 남깁니다."""
    lines = raw_text.split("\n")
    cleaned_lines = []

    day_pattern = re.compile(r"^[\s]*[월화수목금토일][\s]*$")
    date_pattern = re.compile(r"^\(\d{1,2}/\d{1,2}\)$")

    for line in lines:
        line_str = line.strip()

        if not line_str:
            continue

        # 1. 요일/날짜 표기 제거
        if day_pattern.match(line_str) or date_pattern.match(line_str):
            continue

        # 2. 가격 및 구성원 안내 제거
        if "원" in line_str or "구성원" in line_str or re.search(r"\d+원", line_str):
            continue

        # 3. 칼로리 및 특수문자 정돈
        if line_str not in ["\"'", "''", '""', '-', '─', '운영없음', '쉬어갑니다']:
            line_str = line_str.replace('"', "").replace("'", "")

            if "kcal" in line_str.lower():
                kcal_num = re.sub(r"[^\d]", "", line_str)
                if kcal_num:
                    line_str = f"⚡ {int(kcal_num):,} kcal"

            cleaned_lines.append(line_str)

    return "\n".join(cleaned_lines)


def get_today_menu():
    # 인천대 학생식당(11호관) URL
    url = "https://www.inucoop.com/main.php?mkey=2&w=2"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    days = ["월", "화", "수", "목", "금", "토", "일"]

    # KST (UTC+9) 날짜 구하기
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)

    weekday_idx = now.weekday()  # 0:월, 1:화, 2:수, 3:목, 4:금, 5:토, 6:일
    today_weekday = days[weekday_idx]
    today_str = f"{now.month}월 {now.day}일 ({today_weekday}요일)"

    # 주말 예외 처리
    if weekday_idx >= 5:
        return f"📅 **{today_str}**\n주말은 식당을 운영하지 않습니다."

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = res.apparent_encoding or "euc-kr"
        
        # HTML 파싱 전 br 태그를 실제 줄바꿈 문자로 변환 (핵심!)
        html_content = res.text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        soup = BeautifulSoup(html_content, "html.parser")

        tables = soup.find_all("table")

        result_text = f"📅 **{today_str} 인천대 학생식당(11호관)**\n"
        result_text += "─────────────────────────\n\n"

        menu_added = False

        for tbl in tables:
            rows = tbl.find_all("tr")
            if len(rows) <= 1:
                continue

            # 오늘 요일(예: '월')이 있는 열(Column) 위치 찾기
            col_index = -1
            for row in rows[:3]:
                cells = row.find_all(["th", "td"])
                for idx, cell in enumerate(cells):
                    cell_text = cell.get_text(strip=True)
                    if today_weekday in cell_text and len(cell_text) <= 12:
                        col_index = idx
                        break
                if col_index != -1:
                    break

            # 요일 위치를 못 찾았다면 기본 인덱스(월=1, 화=2, 수=3, 목=4, 금=5) 지정
            if col_index == -1:
                col_index = weekday_idx + 1

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])

                if len(cells) <= col_index:
                    continue

                raw_category = cells[0].get_text(strip=True)
                raw_menu = cells[col_index].get_text()

                if (
                    "오늘 등록된" in raw_menu
                    or "등록된 메뉴가 없습니다" in raw_menu
                    or "운영없음" in raw_menu
                    or "쉬어갑니다" in raw_menu
                    or not raw_menu.strip()
                ):
                    continue

                menu_content = clean_menu_content(raw_menu)

                if menu_content and len(menu_content) > 1:
                    category_title = (
                        f"📌 **{raw_category}**\n"
                        if raw_category and len(raw_category) < 15
                        else "📌 **오늘의 메뉴**\n"
                    )
                    result_text += f"{category_title}{menu_content}\n\n"
                    menu_added = True

            if menu_added:
                break

        if not menu_added:
            return f"📅 **{today_str}**\n오늘 등록된 학식 메뉴가 없습니다."

        return result_text

    except Exception as e:
        return f"크롤링 중 에러가 발생했습니다: {e}"


def send_discord_meal_notice(menu_text):
    payload = {
        "username": "인천대 학식 알리미",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3405/3405255.png",
        "embeds": [
            {
                "title": "🍱 오늘의 학식 메뉴",
                "url": "https://www.inucoop.com/main.php?mkey=2&w=2",
                "description": menu_text,
                "color": 3447003,
            }
        ],
    }

    res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

    if res.status_code in [200, 204]:
        print("✅ 디스코드 메시지 전송 성공!")
    else:
        print(f"❌ 전송 실패 (상태 코드: {res.status_code}): {res.text}")


if __name__ == "__main__":
    today_menu = get_today_menu()
    send_discord_meal_notice(today_menu)
