import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import zoneinfo

# 디스코드 웹훅 URL 설정
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1544879632577470587/fbc0TdvyVlERYLiwkwwuhJfBT5YwWM2ZyniwjWAgTNgfR7keBUY6Vo-AEoZnuHrRDOu9",
)

def clean_category_name(raw_category):
    """카테고리명 정돈"""
    if "백반" in raw_category:
        return "백반"
    elif "일품" in raw_category:
        return "일품"
    elif "4코너" in raw_category:
        return "4코너"
    elif "5코너" in raw_category:
        return "5코너"
    elif "석식" in raw_category:
        return "석식"
    elif "국밥" in raw_category:
        return "국밥"

    clean_name = re.sub(r"\(.*?\)", "", raw_category).strip()
    return clean_name if clean_name else raw_category


def clean_menu_content(text):
    """메뉴 텍스트 정제"""
    lines = text.split("\n")
    cleaned_lines = []

    day_pattern = re.compile(r"^[\s]*[월화수목금토일][\s]*$")
    date_pattern = re.compile(r"^\(\d{1,2}/\d{1,2}\)$")

    for line in lines:
        line_str = line.strip()

        if day_pattern.match(line_str) or date_pattern.match(line_str):
            continue

        if "원" in line_str or "구성원" in line_str or re.search(r"\d+원", line_str):
            continue

        if line_str and line_str not in ["\"'", "''", '""']:
            line_str = line_str.replace('"', "").replace("'", "")

            if "kcal" in line_str.lower():
                kcal_num = re.sub(r"[^\d]", "", line_str)
                if kcal_num:
                    line_str = f"⚡ {int(kcal_num):,} kcal"

            cleaned_lines.append(line_str)

    return "\n".join(cleaned_lines)


def get_today_menu():
    # 인천대 생협 식단 메인 페이지 (파라미터 단순화)
    url = "https://www.inucoop.com/main.php?mkey=2"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    days = ["월", "화", "수", "목", "금", "토", "일"]
    
    # KST 기준 오늘 날짜 구하기
    kst = zoneinfo.ZoneInfo("Asia/Seoul")
    now = datetime.now(kst)
    
    today_weekday = days[now.weekday()]
    today_str = f"{now.month}월 {now.day}일 ({today_weekday}요일)"

    try:
        res = requests.get(url, headers=headers)
        res.encoding = res.apparent_encoding or "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")

        tables = soup.find_all("table")
        
        result_text = f"📅 **{today_str} 인천대 학식**\n"
        result_text += "─────────────────────────\n\n"

        menu_added = False

        for tbl in tables:
            rows = tbl.find_all("tr")
            if not rows:
                continue

            # 요일 헤더 탐색
            col_index = -1
            for row in rows[:3]: # 상단 3개 행 내에서 헤더 검색
                cells = row.find_all(["th", "td"])
                for idx, cell in enumerate(cells):
                    cell_text = cell.get_text(strip=True)
                    if today_weekday in cell_text and len(cell_text) <= 10:
                        col_index = idx
                        break
                if col_index != -1:
                    break

            if col_index == -1:
                continue

            # 메뉴 데이터 파싱
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) <= col_index:
                    continue

                raw_category = cells[0].get_text(strip=True)
                category = clean_category_name(raw_category)

                raw_menu = cells[col_index].get_text(separator="\n", strip=True)

                if (
                    "오늘 등록된" in raw_menu
                    or "등록된 메뉴가 없습니다" in raw_menu
                    or "쉬어갑니다" in raw_menu
                    or not raw_menu
                ):
                    continue

                menu_content = clean_menu_content(raw_menu)

                if category and menu_content and len(menu_content) > 2:
                    result_text += f"📌 **{category}**\n{menu_content}\n\n"
                    menu_added = True

        if not menu_added:
            return f"📅 **{today_str}**\n오늘 등록된 학식 메뉴가 없습니다."

        return result_text

    except Exception as e:
        return f"크롤링 중 에러가 발생했습니다: {e}"


def send_discord_meal_notice(menu_text):
    payload = {
        "username": "인천대 학식 알리미",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3405/3405255.png",
        "embeds": [{
            "title": "🍱 오늘의 학식 메뉴",
            "url": "https://www.inucoop.com/main.php?mkey=2",
            "description": menu_text,
            "color": 3447003,
        }],
    }

    res = requests.post(DISCORD_WEBHOOK_URL, json=payload)

    if res.status_code in [200, 204]:
        print("✅ 디스코드 메시지 전송 성공!")
    else:
        print(f"❌ 전송 실패 (상태 코드: {res.status_code}): {res.text}")


if __name__ == "__main__":
    today_menu = get_today_menu()
    send_discord_meal_notice(today_menu)
