#!/bin/bash

# ==========================================================
# Beeminder Commit Tracker - 本地 Cron 执行脚本
# ==========================================================

# 1. 切换到脚本所在目录，确保 Python 脚本能找到依赖
# 使用 dirname "$0" 获取脚本自身的路径，然后 cd
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

# 2. 设置/加载环境变量
# 在 Cron 环境中，环境变量不会自动加载。请替换为您的真实值。
# 注意：敏感信息最好通过配置文件或服务器环境变量管理，但为了演示，这里直接赋值。

# 🚨 替换为您真实的 Beeminder 和 GitHub Token/信息
export BEEMINDER_USERNAME="paxton"
export BEEMINDER_AUTH_TOKEN="YOURBEEMINDER_AUTH_TOKEN"
export BEEMINDER_GOAL_NAME="bytedance"
export GITHUB_TOKEN="YOURGITHUBTOKEN"
export REPO_OWNER="Paxton-Miller"
export REPO_NAME="beeminder"


# 3. 检查并安装 Python 依赖
# 确保安装的是 Python 3 的 requests 库
if ! python3 -c "import requests" 2>/dev/null; then
    echo "requests 库未安装，正在安装..."
    # 使用 -q 保持安静，-U 确保升级到最新版
    python3 -m pip install requests -q
    if [ $? -ne 0 ]; then
        echo "Error: 依赖安装失败，请手动检查 pip 和 requests。"
        exit 1
    fi
fi


# 4. 确定执行参数 (模拟 GitHub Actions 的定时逻辑)
# 获取当前 UTC 时间
UTC_HOUR=$(date -u +%H)
UTC_MINUTE=$(date -u +%M)

LOCAL_HOUR=""
CHECK_START_HOUR=""
CHECK_END_MINUTE=""
SUCCESS=1 # 默认失败

if [ "$UTC_HOUR" -eq 6 ]; then
  # 匹配 UTC+8 14:00 任务 (检查 12:00-14:00)
  LOCAL_HOUR=14
  CHECK_START_HOUR=12
  CHECK_END_MINUTE=00
  SUCCESS=0

elif [ "$UTC_HOUR" -eq 15 ]; then
  # 匹配 UTC+8 23:35 任务 (检查 23:00-23:30)
  # 允许 15:35 启动，但检查窗口结束是 30 分
  LOCAL_HOUR=23
  CHECK_START_HOUR=23
  CHECK_END_MINUTE=30
  SUCCESS=0
fi

if [ "$SUCCESS" -eq 0 ]; then
    echo "$(date): Cron 任务匹配成功。检查窗口 ${CHECK_START_HOUR}:00 - ${LOCAL_HOUR}:${CHECK_END_MINUTE}"
    
    # 5. 运行 Python 脚本
    # 使用 python3 确保版本正确
    python3 beeminder.py "$LOCAL_HOUR" "$CHECK_START_HOUR" "$CHECK_END_MINUTE"
    
    if [ $? -eq 0 ]; then
        echo "$(date): Python 脚本执行成功。"
    else
        echo "$(date): 🚨 Python 脚本执行失败，请检查 beeminder.py 的日志。"
    fi
else
    # 任务在非预定小时启动 (例如 07:00 UTC)，通常是由于系统延迟
    echo "$(date): 警告：任务在预期小时 ($UTC_HOUR UTC) 之外启动。跳过执行。"
fi

exit 0