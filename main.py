import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1544879632577470587/fbc0TdvyVlERYLiwkwwuhJfBT5YwWM2ZyniwjWAgTNgfR7keBUY6Vo-AEoZnuHrRDOu9",
)

def clean_menu_content(raw_text):
    lines = raw_text.split("\n")
    cleaned_lines = []

    day_pattern = re.compile(r"^[\s]*[월화수목금토일][\s]*$")
    date_pattern = re.compile(r"^\(\d{1,2}/\d{1,2}\)$")

    for line in lines:
        line_str = line.strip()

        if not line_str:
            continue

        if day_pattern.match(line_str) or date_pattern.match(line_str):
            continue

        if "원" in line_str or "구성원" in line_str or re.search(r"\d+원", line_str):
            continue

        if line_str not in ["\"'", "''", '""', '-', '─', '운영없음', '쉬어갑니다']:
            line_str = line_str.replace('"', "").replace("'", "")

            if "kcal" in line_str.lower():
                kcal_num = re.sub(r"[^\d]", "", line_str)
                if kcal_num:
                    line_str = f"⚡ {int(kcal_num):,} kcal"

            cleaned_lines.append(line_str)

    return "\n".join(cleaned_lines)

def get_today_menu():
    url = "https://www.inucoop.com/main.php?mkey=2&w=2"
    days = ["월", "화", "수", "목", "금", "토", "일"]

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)

    weekday_idx = now.weekday()
    today_weekday = days[weekday_idx]
    today_str = f"{now.month}월 {now.day}일 ({today_weekday}요일)"

    if weekday_idx >= 5:
        return f"📅 **{today_str}**\n주말은 식당을 운영하지 않습니다."

    try:
        # Playwright를 이용해 셀레니움처럼 실제 웹 브라우저를 띄워서 페이지 로딩
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            content = page.content()
            browser.close()

        soup = BeautifulSoup(content, "html.parser")
        tables = soup.find_all("table")

        result_text = f"📅 **{today_str} 인천대 학생식당(11호관)**\n"
        result_text += "─────────────────────────\n\n"

        menu_added = False

        for tbl in tables:
            rows = tbl.find_all("tr")
            if len(rows) <= 1:
                continue

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

            if col_index == -1:
                col_index = weekday_idx + 1

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])

                if len(cells) <= col_index:
                    continue

                raw_category = cells[0].get_text(strip=True)
                raw_menu = cells[col_index].get_text(separator="\n", strip=True)

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
