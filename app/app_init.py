import json
import os
import requests
import configparser
import time
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from jira import JIRA

# ---------- Step 1: Ensure and Modify Annual Data ----------

def ensure_annual_json(year):
    file_path = f"{year}.json"
    if not os.path.exists(file_path):
        url = f"https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json"
        print(f"Downloading annual data: {url}")
        resp = requests.get(url)
        if resp.status_code == 200:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(resp.json(), f, ensure_ascii=False, indent=2)
        else:
            raise Exception(f"Failed to download data for {year}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def modify_annual_json(year):
    data = ensure_annual_json(year)
    # 將 5 月 1 號標記為假日
    for entry in data:
        if entry['date'][4:] == '0501':
            entry['isHoliday'] = True

    # 原有邏輯，週六與週日標記為假日
    for entry in data:
        if entry['week'] in ['六', '日']:
            entry['isHoliday'] = True
    out_path = f"{year}_modify.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

# ---------- Step 2: Fetch JIRA Tasks and Save JSON ----------

def fetch_jira_issues():
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

    jql_query = 'project = F0TASK'
    fields_to_fetch = "key,summary,issuetype,status,assignee,customfield_10109,customfield_10110,customfield_12046,parent"
    total_count = jira.search_issues(jql_query, maxResults=1).total
    print(f"📊 JIRA 共找到 {total_count} 筆 Issue")

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

        task_data.append({
            "Issue": issue.key,
            "IssueType": get_value("issuetype", "name"),
            "Summary": get_value("summary"),
            "Status": get_value("status", "name"),
            "Assignee": get_value("assignee", "displayName"),
            "Target Start": ts,
            "Target End": te,
            "Man-hour": get_value("customfield_12046"),
            "Parent": get_value("parent", "key")
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
                'wh_week_uplimit_hours': len(workdays) * 8,
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
        totals = {f'week_{i}_hours': 0 for i in range(1, 4)}
        for mid, lst in issues.items():
            block = {'main_issue': mid, 'main_issue_name': mains.get(mid, ''), 'sub_issue': []}
            for si in lst:
                mh = float(si['Man-hour']) if si['Man-hour'] != 'NA' else 0
                sd, ed = si['Target Start'], si['Target End']
                valid = [e['date'] for e in annual_data if sd <= e['date'] <= ed and not e['isHoliday']]
                wd = len(valid); pd = mh / wd if wd else 0
                block['sub_issue'].append({
                    'sub_issue_id': si['Issue'],
                    'sub_issue_name': si['Summary'],
                    'sub_issue_manpower': mh,
                    'sub_issue_work_day': wd,
                    'sub_issue_preday_hours': round(pd, 2)
                })
                for i, wk in enumerate(weeks):
                    totals[f'week_{i+1}_hours'] += round(pd * wk['wh_week_workdates'], 2)
            member['issue'].append(block)
        member.update(totals)
        members.append(member)

    with open('workhour.json', 'w', encoding='utf-8') as f:
        json.dump({'week': weeks, 'members': members}, f, ensure_ascii=False, indent=2)
    print('✅ workhour.json 產生完成')

# ---------- Entry Point ----------

def main():
    fetch_jira_issues()
    calculate_workhour()

if __name__ == '__main__':
    main()
