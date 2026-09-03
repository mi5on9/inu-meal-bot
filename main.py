import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import zoneinfo # Python 3.9+ 기본 라이브러리

# 디스코드 웹훅 URL 설정
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1544879632577470587/fbc0TdvyVlERYLiwkwwuhJfBT5YwWM2ZyniwjWAgTNgfR7keBUY6Vo-AEoZnuHrRDOu9",
)

def clean_category_name(raw_category):
    """카테고리명을 정돈합니다."""
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
    """가격 및 요일/날짜 텍스트를 제거하고 메뉴와 칼로리만 남깁니다."""
    lines = text.split("\n")
    cleaned_lines = []

    day_pattern = re.compile(r"^[\s]*[월화수목금토일][\s]*$")
    date_pattern = re.compile(r"^\(\d{1,2}/\d{1,2}\)$")

    for line in lines:
        line_str = line.strip()

        # 1. 헤더 날짜 텍스트 제거
        if day_pattern.match(line_str) or date_pattern.match(line_str):
            continue

        # 2. 가격("6,500원", "구성원 5,500원") 제거
        if "원" in line_str or "구성원" in line_str or re.search(r"\d+원", line_str):
            continue

        # 3. 따옴표 정돈 및 칼로리 포맷팅
        if line_str and line_str not in ["\"'", "''", '""']:
            line_str = line_str.replace('"', "").replace("'", "")

            if "kcal" in line_str.lower():
                kcal_num = re.sub(r"[^\d]", "", line_str)
                if kcal_num:
                    line_str = f"⚡ {int(kcal_num):,} kcal"

            cleaned_lines.append(line_str)

    return "\n".join(cleaned_lines)


def get_today_menu():
    url = "https://www.inucoop.com/main.php"
    params = {"mkey": "2", "w": "2", "l": "1"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    days = ["월", "화", "수", "목", "금", "토", "일"]
    
    # 한국 표준시(KST) 명확히 설정
    kst = zoneinfo.ZoneInfo("Asia/Seoul")
    now = datetime.now(kst)
    
    today_weekday = days[now.weekday()]
    today_str = f"{now.month}월 {now.day}일 ({today_weekday}요일)"

    try:
        res = requests.get(url, params=params, headers=headers)
        res.encoding = res.apparent_encoding or "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")

        tables = soup.find_all("table")
        
        # 오늘 요일에 해당하는 열(index) 찾기 및 해당 테이블 감지
        target_table = None
        col_index = -1

        for tbl in tables:
            rows = tbl.find_all("tr")
            if not rows:
                continue
            
            header_cells = [cell.get_text(strip=True) for cell in rows[0].find_all(["th", "td"])]
            
            for idx, text in enumerate(header_cells):
                # 헤더 셀 안에 오늘 요일(예: '목')이 포함되어 있는지 확인
                if today_weekday in text:
                    col_index = idx
                    target_table = tbl
                    break
            
            if target_table:
                break

        if not target_table or col_index == -1:
            return f"📅 **{today_str}**\n오늘 등록된 학식 메뉴가 없습니다."

        rows = target_table.find_all("tr")
        result_text = f"📅 **{today_str} 인천대 학식**\n"
        result_text += "─────────────────────────\n\n"

        menu_added = False
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            raw_category = cells[0].get_text(strip=True)
            category = clean_category_name(raw_category)

            if len(cells) > col_index:
                raw_menu = cells[col_index].get_text(separator="\n", strip=True)

                if (
                    "오늘 등록된" in raw_menu
                    or "등록된 메뉴가 없습니다" in raw_menu
                    or not raw_menu
                ):
                    continue

                menu_content = clean_menu_content(raw_menu)

                if category and menu_content:
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
            "url": "https://www.inucoop.com/main.php?mkey=2&w=2&l=1",
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
