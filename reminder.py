import os
import sys
import datetime
import smtplib  # 导入 smtplib 库
from email.mime.text import MIMEText
from email.header import Header

# --- 配置信息 (使用 GitHub Secrets 存储敏感信息) ---
# 使用环境变量获取敏感信息，确保安全
SMTP_SERVER = os.environ.get("SMTP_SERVER")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")

# **【重要修改】** 接收通知的邮箱列表 (从环境变量中获取)
RECEIVER_EMAILS_STR = os.environ.get("RECEIVER_EMAILS")
RECEIVER_EMAILS = [email.strip() for email in RECEIVER_EMAILS_STR.split(',') if email.strip()]

# 脚本运行配置
HOLIDAYS_FILE_PATH = "holidays.txt"
REMINDER_SUBJECT_MIDDAY = "中午打卡提醒：勿忘提交GitHub代码"
REMINDER_SUBJECT_EVENING = "晚上打卡提醒：勿忘提交GitHub代码"

def load_holidays(file_path):
    """从文件中加载节假日日期集合。"""
    holidays = set()
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        datetime.datetime.strptime(line, '%Y-%m-%d')
                        holidays.add(line)
                    except ValueError:
                        print(f"⚠️ 跳过无效的日期格式: {line}")
    except FileNotFoundError:
        print(f"⚠️ 节假日文件未找到: {file_path}")
    return holidays

HOLIDAYS = load_holidays(HOLIDAYS_FILE_PATH)


def send_email_notification(subject, receivers):
    """发送提醒邮件给多个接收者。"""
    if not all([SMTP_SERVER, SENDER_EMAIL, SENDER_PASSWORD]):
        print("❌ 错误: SMTP 环境变量未设置。跳过邮件发送。")
        return False

    body = f"""
    这是一封自动发送的学习打卡提醒邮件。
    
    请确认您已完成或即将完成：
    1. 学习任务。
    2. 将代码/笔记提交到 GitHub 仓库。
    
    本次提醒主题：【{subject}】
    
    [请注意：这是提醒邮件，不是打卡结果邮件。请及时完成任务！]
    """
    
    message = MIMEText(body, 'plain', 'utf-8') 
    message['From'] = SENDER_EMAIL
    message['To'] = ", ".join(receivers) 
    message['Subject'] = Header(subject, 'utf-8')

    print(f"正在尝试发送邮件到 {message['To']}...")
    try:
        server = smtplib.SMTP(SMTP_SERVER, 587) 
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        server.sendmail(SENDER_EMAIL, receivers, message.as_string())
        server.quit()
        print("✅ 邮件发送成功！")
        return True
    except Exception as e:
        print(f"❌ 邮件发送失败。请检查SMTP配置和授权码是否正确: {e}")
        return False


def main():
    if len(sys.argv) != 2:
        print("用法: python reminder.py <task_name>")
        print("例如: python reminder.py midday")
        sys.exit(1)

    task_name = sys.argv[1] # 'midday' 或 'evening'

    # --- 时区配置 (假设北京时间 UTC+8) ---
    LOCAL_TZ_OFFSET = datetime.timedelta(hours=8)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_local = now_utc + LOCAL_TZ_OFFSET

    today_date_str = now_local.strftime('%Y-%m-%d')
    day_of_week = now_local.weekday() # 0=周一, 6=周日

    print(f"执行任务时间 (本地): {now_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"任务类型: {task_name}")
    print(f"已加载节假日: {HOLIDAYS}")
    
    # --- 豁免判断：节假日/周日优先 ---
    is_holiday = today_date_str in HOLIDAYS
    is_sunday = day_of_week == 6

    if is_holiday:
        print("ℹ️ 豁免: 今天是节假日，跳过提醒。")
        return
        
    if is_sunday:
        print("ℹ️ 豁免: 今天是周日，跳过提醒。")
        return

    # --- 细化判断 ---
    
    # 1. 周六晚上豁免
    if day_of_week == 5 and task_name == 'evening':
        print("ℹ️ 豁免: 今天是周六晚上，跳过提醒。")
        return

    # 2. 周一到周五，所有任务都提醒 (midday, evening)
    if day_of_week in range(0, 5): 
        if task_name == 'midday':
            subject = REMINDER_SUBJECT_MIDDAY
        elif task_name == 'evening':
            subject = REMINDER_SUBJECT_EVENING
        else:
            print(f"❌ 未知任务名称: {task_name}")
            return
        
        send_email_notification(subject, RECEIVER_EMAILS)
        return

    # 3. 周六只有中午提醒
    if day_of_week == 5 and task_name == 'midday':
        subject = REMINDER_SUBJECT_MIDDAY
        send_email_notification(subject, RECEIVER_EMAILS)
        return

    print("ℹ️ 流程结束，未发送邮件（可能今天是周日或节假日）。")

if __name__ == "__main__":
    main()