import os
import sys
import requests
import datetime

# --- Beeminder API 配置 (使用 GitHub Secrets 存储更安全) ---
# 在 Actions 中，我们会将这些值作为环境变量传入
USERNAME = os.environ.get("BEEMINDER_USERNAME")
AUTH_TOKEN = os.environ.get("BEEMINDER_AUTH_TOKEN")
GOAL_NAME = os.environ.get("BEEMINDER_GOAL_NAME")

# --- GitHub 仓库配置 ---
# 监测哪个仓库的提交时间，使用环境变量传入
GITHUB_REPO_OWNER = os.environ.get("REPO_OWNER")
GITHUB_REPO_NAME = os.environ.get("REPO_NAME")

# --- 脚本运行配置 ---
HOLIDAYS_FILE_PATH = "holidays.txt"
FAKE_SUBMISSION_VALUE = 0 
NORMAL_SUBMISSION_VALUE = 1 
NORMAL_COMMENT = "正常打卡提交 - Commit OK"
FAKE_COMMENT = "伪提交 - 豁免日或周六晚上"

def load_holidays(file_path):
    """从文件中加载节假日日期集合。"""
    holidays = set()
    try:
        # 在 Actions 环境中，文件路径可能需要调整，但通常在根目录
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        # 确保日期格式正确
                        datetime.datetime.strptime(line, '%Y-%m-%d')
                        holidays.add(line)
                    except ValueError:
                        print(f"⚠️ 跳过无效的日期格式: {line}")
    except FileNotFoundError:
        print(f"⚠️ 节假日文件未找到: {file_path}")
    return holidays

HOLIDAYS = load_holidays(HOLIDAYS_FILE_PATH)


def get_latest_commit_time():
    """使用 GitHub API 获取仓库的最近一次提交时间 (UTC)。"""
    url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/commits"
    
    try:
        # 使用 token 进行认证，避免 API 限制，并获取更精确的提交数据
        headers = {'Authorization': f'token {os.environ.get("GITHUB_TOKEN")}'}
        response = requests.get(url, headers=headers, params={'per_page': 1})
        response.raise_for_status() # 对非 200 状态码抛出异常
        
        data = response.json()
        if not data:
            print("❌ 错误: 仓库中没有提交记录。")
            return None
        
        # 提取提交时间 (格式：2025-11-12T07:20:47Z)
        commit_time_str = data[0]['commit']['committer']['date']
        
        # 将 UTC 时间字符串转换为 datetime 对象
        latest_commit_time = datetime.datetime.strptime(commit_time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
        return latest_commit_time
        
    except requests.exceptions.RequestException as e:
        print(f"❌ GitHub API 请求错误: {e}")
        return None

def submit_to_beeminder(value, comment):
    """向 Beeminder API 提交数据点。"""
    if not all([USERNAME, AUTH_TOKEN, GOAL_NAME]):
        print("❌ 错误: Beeminder 环境变量未设置。跳过提交。")
        return False
        
    url = f"https://www.beeminder.com/api/v1/users/{USERNAME}/goals/{GOAL_NAME}/datapoints.json"
    
    payload = {
        "auth_token": AUTH_TOKEN,
        "value": value,
        "comment": comment,
    }

    try:
        print(f"🚀 尝试提交数据: value={value}, comment='{comment}'")
        response = requests.post(url, data=payload)
        
        if response.status_code == 200:
            print(f"✅ Beeminder 提交成功!")
            return True
        else:
            print(f"❌ Beeminder 提交失败! 状态码: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求错误: {e}")
        return False

def main():
    if len(sys.argv) != 4:
        print("用法: python beeminder.py <local_hour> <check_start_hour> <check_end_minute>")
        sys.exit(1)

    # 命令行参数 (由 Actions 传入)
    local_hour = int(sys.argv[1])            # 当前执行任务的本地小时 (14 或 23)
    check_start_hour = int(sys.argv[2])      # 要求提交的开始时间 (12 或 23)
    check_end_minute = int(sys.argv[3])      # 要求提交的结束分钟 (14:00 对应 00, 23:50 对应 50)

    # 获取当前 UTC 时间，并将其转换为东八区 (EST) 时间，用于判断日期和星期
    # 注意：您的时区是 EST (美国东部时间)，而不是中国时区的 UTC+8。
    # 我假设您的要求中的 14:00 和 23:50 指的是您所在时区的时间。
    # 这里我们使用 Action 的运行时间作为“当前时间”
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    # 将时间转换为您要求的时区 (假设为 UTC-5 或 EST)
    # ⚠️ 请根据您实际需要的时区（例如北京时间 UTC+8 或 EST UTC-5）调整这个偏移量
    # 鉴于您的环境是 EST (UTC-5)，我们使用这个偏移量
    LOCAL_TZ_OFFSET = datetime.timedelta(hours=-5)
    now_local = now_utc + LOCAL_TZ_OFFSET

    today_date_str = now_local.strftime('%Y-%m-%d')
    day_of_week = now_local.weekday() # 0=周一, 6=周日

    print(f"执行任务时间 (本地): {now_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"任务参数: 检查窗口开始于 {check_start_hour}:00, 结束于 {local_hour}:{check_end_minute}")
    print(f"已加载节假日: {HOLIDAYS}")
    
    # --- 逻辑判断：伪提交 (豁免) 优先 ---
    is_holiday = today_date_str in HOLIDAYS
    is_sunday = day_of_week == 6
    is_saturday_night_fake_submit = (day_of_week == 5 and local_hour == 23 and check_end_minute == 50)
    
    if is_holiday or is_sunday or is_saturday_night_fake_submit:
        # --- 伪提交逻辑 (节假日/周日/周六晚上) ---
        print(f"ℹ️ 当前是豁免日 (节假日/周日/周六晚上)，执行伪提交。")
        submit_to_beeminder(FAKE_SUBMISSION_VALUE, FAKE_COMMENT)
        return

    # --- 正常打卡逻辑 (周一到周六中午, 周一到周五晚上) ---
    
    # 确定要求提交的时间窗口 (本地时间)
    check_window_start = now_local.replace(hour=check_start_hour, minute=0, second=0, microsecond=0)
    check_window_end = now_local.replace(hour=local_hour, minute=check_end_minute, second=0, microsecond=0)
    
    # 获取最新的提交时间 (UTC)
    latest_commit_time_utc = get_latest_commit_time()
    
    if latest_commit_time_utc is None:
        # 无法获取提交时间，提交失败 (0) 以警示
        submit_to_beeminder(0, "失败: 无法获取 GitHub 提交时间")
        return
        
    # 将获取的提交时间 (UTC) 转换为本地时区进行比较
    latest_commit_time_local = latest_commit_time_utc + LOCAL_TZ_OFFSET

    # 检查提交时间是否在要求的时间窗口内
    if check_window_start <= latest_commit_time_local <= check_window_end:
        print(f"✅ 提交时间 {latest_commit_time_local.strftime('%Y-%m-%d %H:%M:%S')} 符合要求 ({check_window_start.strftime('%H:%M')} - {check_window_end.strftime('%H:%M')})。")
        submit_to_beeminder(NORMAL_SUBMISSION_VALUE, NORMAL_COMMENT)
    else:
        print(f"❌ 提交时间 {latest_commit_time_local.strftime('%Y-%m-%d %H:%M:%S')} 不在要求的时间窗口内 ({check_window_start.strftime('%H:%M')} - {check_window_end.strftime('%H:%M')})。")
        # 失败提交 (0)
        submit_to_beeminder(0, "失败: 未在要求时间段内监测到 GitHub 提交")

if __name__ == "__main__":
    main()