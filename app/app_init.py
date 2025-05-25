import json
import os
import requests
import configparser
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from jira import JIRA
from decimal import Decimal, ROUND_HALF_UP
import dateutil.parser


# 讀取設定檔
config = configparser.ConfigParser()
config.read('./ManPowerTool.ini')
project_key = config['JIRA']['project_key']

def round1(x):
    return float(Decimal(str(x)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))

INI_PATH = './ManPowerTool.ini'
YEAR = datetime.now().year

# ---------- Step 1: Ensure and Modify Annual Data ----------
def ensure_annual_json(year):
    file_path = f"{year}.json"
    if not os.path.exists(file_path):
        url = f"https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json"
        current_month = datetime.now().month
        current_year = datetime.now().year
        if current_month == 12 or year < current_year:
            print(f"從網路下載: {url}")
            response = requests.get(url)
            if response.status_code == 200:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(response.text)
                return response.json()
            else:
                print(f"下載失敗: {year}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def modify_annual_json(year):
    data = ensure_annual_json(year)
    # 勞動節 (5/1) 強制為假日
    for entry in data:
        if entry['date'][4:] == '0501':
            entry['isHoliday'] = True
    # 六、日為假日
    for entry in data:
        if entry['week'] in ['六', '日']:
            entry['isHoliday'] = True
    out_file = f"{year}_modify.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

# ---------- Step 2: Fetch JIRA Tasks and Save JSON ----------
def fetch_jira_issues(progress_callback=None):
    config = configparser.ConfigParser()
    config.read('./ManPowerTool.ini')
    server = config['JIRA']['server']
    api_token = config['JIRA']['api_token']

    try:
        jira = JIRA(server=server, token_auth=api_token, max_retries=0)
        print("✅ JIRA 連線成功！")
    except Exception as e:
        print(f"❌ JIRA 連線失敗：{e}")
        return []

    jql_query = f"project = {project_key}"
    fields_to_fetch = [
        "key", "summary", "issuetype", "status", "assignee",
        "customfield_10109", "customfield_10110", "customfield_12046", "parent"
    ]
    fields_arg = ",".join(fields_to_fetch)
    total_count = jira.search_issues(jql_query, maxResults=1, fields=fields_arg).total
    print(f"📊 JIRA 共找到 {total_count} 筆 Issue")

    batch_size = int(config['JIRA'].get('batch_size', '100'))
    issues = []
    for start in range(0, total_count, batch_size):
        batch = jira.search_issues(
            jql_query,
            startAt=start,
            maxResults=batch_size,
            fields=fields_arg
        )
        issues.extend(batch)
        # 新增進度回報
        if progress_callback is not None:
            progress_callback(min(start + batch_size, total_count), total_count)
        print(f"➡️ 已抓取 {min(start+batch_size, total_count)}/{total_count}")



    def fetch_issues(start_at):
        return jira.search_issues(jql_query, startAt=start_at, maxResults=200, fields=fields_to_fetch)

    issues = []
    with ThreadPoolExecutor(5) as executor:
        futures = [executor.submit(fetch_issues, start) for start in range(0, total_count, 200)]
        for future in as_completed(futures):
            issues.extend(future.result())

    task_data = []
    for issue in issues:
        def get_value(f, sub=None):
            val = getattr(issue.fields, f, None)
            if not val: return 'NA'
            return getattr(val, sub, 'NA') if sub else val

        ts = get_value("customfield_10109")
        te = get_value("customfield_10110")
        if ts != 'NA': ts = ts.replace('-', '')
        if te != 'NA': te = te.replace('-', '')
        resdate = get_value("resolutiondate")
        # 格式正規化
        if resdate and resdate != 'NA' and isinstance(resdate, str) and 'T' not in resdate:
            resdate = None

        task_data.append({
            "Issue": issue.key,
            "IssueType": get_value("issuetype", "name"),
            "Summary": get_value("summary"),
            "Status": get_value("status", "name"),
            "Assignee": get_value("assignee", "displayName"),
            "Target Start": ts,
            "Target End": te,
            "Man-hour": get_value("customfield_12046"),
            "Parent": get_value("parent", "key"),
            "resolutiondate": resdate
        })

    with open("Jira_Tasks.json", "w", encoding="utf-8") as f:
        json.dump(task_data, f, ensure_ascii=False, indent=2)
    print("📂 Jira_Tasks.json 產生完成")
    return task_data

# ---------- Step 3: Calculate Workhour Data ----------
def calculate_workhour():
    year = datetime.now().year
    annual_data = modify_annual_json(year)
    with open('Jira_Tasks.json', 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    # 產生週次資訊
    week_map = {'日': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6}
    date_to_week = {}
    for entry in annual_data:
        d = entry['date']; y, m, day = int(d[:4]), int(d[4:6]), int(d[6:])
        code = y % 10
        wd = week_map[entry['week']]
        wn = 1 if (m == 1 and day <= 6) else ((m - 1) * 31 + day - 1) // 7 + 1
        if m == 12 and day == 31 and wd != 5:
            code = (y + 1) % 10; wn = 1
        date_to_week[d] = f"{code}{wn:02d}"

    today = datetime.now().strftime('%Y%m%d')
    cur_week = date_to_week.get(today)
    weeks = []
    if cur_week:
        num = int(cur_week[1:]); yc = cur_week[0]
        for i in range(3):
            wid = f"{yc}{num+i:02d}"
            dates = sorted([d for d, w in date_to_week.items() if w == wid])
            workdays = [d for d in dates if not next(x for x in annual_data if x['date'] == d)['isHoliday']]
            weeks.append({
                'wh_name': f"week_{i+1}",
                'wh_week_id': wid,
                'wh_week_start_date': dates[0],
                'wh_week_end_date': dates[-1],
                'wh_week_workdates': len(workdays),
                'wh_week_uplimit_hours': round(len(workdays) * 8, 1),
                'wh_week_downlimit_hours': round(len(workdays) * 8 * 0.6, 1)
            })

    w1s, w3e = weeks[0]['wh_week_start_date'], weeks[-1]['wh_week_end_date']
    members = []
    mains = {t['Issue']: t['Summary'] for t in tasks if t['IssueType'] == 'Manpower'}
    subs = [t for t in tasks if t['IssueType'] == 'Sub-Manpower' and not (t['Target Start'] > w3e or t['Target End'] < w1s)]
    by_person = defaultdict(lambda: defaultdict(list))
    for t in subs:
        by_person[t['Assignee']][t['Parent']].append(t)

    for name, issues in by_person.items():
        member = {'name': name, 'issue': []}
        totals = {'week_1_hours': 0, 'week_2_hours': 0, 'week_3_hours': 0}
        for mid, lst in issues.items():
            block = {'main_issue': mid, 'main_issue_name': mains.get(mid, ''), 'sub_issue': []}
            for si in lst:
                mh = float(si['Man-hour']) if si['Man-hour'] != 'NA' else 0
                if mh == 0.1 or mh == 0:
                    continue

                sd, ed = si['Target Start'], si['Target End']
                valid = [e['date'] for e in annual_data if sd <= e['date'] <= ed and not e['isHoliday']]
                wd = len(valid)
                pd = round(mh / wd, 1) if wd else 0.0

                # 三週交集天數
                week_inter = []
                for wk in weeks:
                    week_dates = [d for d in valid if wk['wh_week_start_date'] <= d <= wk['wh_week_end_date']]
                    week_inter.append(len(week_dates))

                # 三週工時計算（預設值）
                w1 = round1(mh / wd * week_inter[0]) if (wd and len(week_inter) > 0) else 0
                w2 = round1(mh / wd * week_inter[1]) if (wd and len(week_inter) > 1) else 0
                w3 = round1(mh / wd * week_inter[2]) if (wd and len(week_inter) > 2) else 0

                # resolutiondate 判斷，若已結案+14天早於今天則三週工時歸零
                resdate = si.get('resolutiondate', None)
                if resdate and resdate != 'NA':
                    try:
                        resolved_date = dateutil.parser.parse(resdate) + timedelta(days=14)
                        now_date = datetime.now()
                        if resolved_date.date() < now_date.date():
                            w1 = w2 = w3 = 0
                    except Exception as ex:
                        print(f"解析 resolutiondate 錯誤: {resdate}, {ex}")

                block['sub_issue'].append({
                    'sub_issue_id': si['Issue'],
                    'sub_issue_name': si['Summary'],
                    'sub_issue_manpower': mh,
                    'sub_issue_work_day': wd,
                    'sub_issue_preday_hours': pd,
                    'sub_issue_work_day_week1': week_inter[0] if len(week_inter) > 0 else 0,
                    'sub_issue_work_day_week2': week_inter[1] if len(week_inter) > 1 else 0,
                    'sub_issue_work_day_week3': week_inter[2] if len(week_inter) > 2 else 0,
                    'week_1_hours': w1,
                    'week_2_hours': w2,
                    'week_3_hours': w3,
                    'resolutiondate': resdate if resdate else None
                })

                # 只有有週工時才加總
                if w1 or w2 or w3:
                    totals['week_1_hours'] += w1
                    totals['week_2_hours'] += w2
                    totals['week_3_hours'] += w3

            member['issue'].append(block)
        member['week_1_hours'] = round(totals['week_1_hours'], 1)
        member['week_2_hours'] = round(totals['week_2_hours'], 1)
        member['week_3_hours'] = round(totals['week_3_hours'], 1)
        members.append(member)

    with open('workhour.json', 'w', encoding='utf-8') as f:
        json.dump({'week': weeks, 'members': members}, f, ensure_ascii=False, indent=2)
    print('✅ workhour.json 產生完成')

# ---------- Entry Point ----------
def main(progress_callback=None):
    fetch_jira_issues(progress_callback)
    calculate_workhour()

if __name__ == '__main__':
    main()
