import configparser
from datetime import datetime
import os
import requests
import json

# 讀取ini資料
config = configparser.ConfigParser()
config.read('./ManPowerTool.ini')
server = config['JIRA']['server']
api_token = config['JIRA']['api_token']
# print(f"server = {server}")
# print(f"api_token = {api_token}")

# 獲取時間


now = datetime.now()

current_data = now.date()
current_month = now.date().month
current_year = now.date().year
next_year = current_year + 1
# print(f"日期:{current_data}")
# print(f"月份:{current_month}")
# print(f"年度:{current_year}")
# print(f'type:{type(current_year)}')
# str_current_year = str(current_year)
# print(f'type:{type(str_current_year)}')


# 獲取假日資料，並檢查目錄下有無存在資料


current_year_file = '%s.json' % str(current_year)
# print(current_year_file)
current_year_url = 'https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/%s.json' % str(current_year)  # 國定假日資料網址
# print(current_year_url)

next_year_file = '%s.json' % str(next_year)
next_year_url = 'https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/%s.json' % str(next_year)

# 定義產生json資料
def create_year_json(url, file_name):
    url_response = requests.get(url)
    # 確認請求成功
    if url_response.status_code == 200:  # 請求資料成功
        # 解析JSON資料
        data = url_response.json()
        # 將JSON資料寫入文件
        with open(file_name, 'w', encoding='utf-8') as encoding_file:
            json.dump(data, encoding_file, ensure_ascii=False, indent=4)
        print(f"資料已成功寫入 {file_name}")
    else:
        print(f"Error: {url_response.status_code}")  # 請求資料失敗並印出錯誤碼


if os.path.exists(current_year_file):  # 檢查目錄下有無存在 year.json
    with open(current_year_file, 'r', encoding='utf-8') as r_current_year_data:  # 將 ASCII 改成 utf-8
        # print(r_current_year_data)
        r_current_year_jdata = json.load(r_current_year_data)
    print(f"讀取文件 {current_year_file} 的資料:")
    print(json.dumps(r_current_year_jdata, ensure_ascii=False, indent=4))  # ensure設定確保在輸出時不會將非ASCII字符轉換為ASCII編碼

else:
    create_year_json(current_year_file, current_year_url)

# 如果當前月份是12月，則檢查並下載下一年的資料
if current_month == 12:
    if os.path.exists(next_year_file):
        with open(next_year_file, 'r', encoding='utf-8') as r_next_year_data:
            r_next_year_jdata = json.load(r_next_year_data)
        print(f"讀取文件 {next_year_file} 的資料:")
        print(json.dumps(r_next_year_jdata, ensure_ascii=False, indent=4))
    else:
        create_year_json(next_year_url, next_year_file)