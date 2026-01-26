#!/bin/bash

# Git 快速操作脚本
# 使用方法: ./git_quick.sh [命令]

case "$1" in
    status|s)
        echo "📊 查看当前状态..."
        git status
        ;;
    add|a)
        echo "➕ 添加所有更改..."
        git add .
        git status
        ;;
    commit|c)
        if [ -z "$2" ]; then
            echo "❌ 请提供提交信息"
            echo "用法: ./git_quick.sh commit \"提交信息\""
            exit 1
        fi
        echo "💾 提交更改..."
        git commit -m "$2"
        ;;
    push|p)
        echo "🚀 推送到远程仓库..."
        git push
        ;;
    pull|pl)
        echo "📥 拉取远程更新..."
        git pull
        ;;
    log|l)
        echo "📜 查看提交历史..."
        git log --oneline -10
        ;;
    all|up)
        if [ -z "$2" ]; then
            echo "❌ 请提供提交信息"
            echo "用法: ./git_quick.sh all \"提交信息\""
            exit 1
        fi
        echo "🔄 完整流程：添加 -> 提交 -> 推送"
        git add .
        git commit -m "$2"
        git push
        echo "✅ 完成！"
        ;;
    *)
        echo "Git 快速操作脚本"
        echo ""
        echo "用法: ./git_quick.sh [命令] [参数]"
        echo ""
        echo "命令列表:"
        echo "  status, s          - 查看当前状态"
        echo "  add, a             - 添加所有更改到暂存区"
        echo "  commit, c [信息]   - 提交更改（需要提交信息）"
        echo "  push, p            - 推送到远程仓库"
        echo "  pull, pl           - 拉取远程更新"
        echo "  log, l             - 查看提交历史"
        echo "  all, up [信息]     - 一键完成：添加+提交+推送（需要提交信息）"
        echo ""
        echo "示例:"
        echo "  ./git_quick.sh status"
        echo "  ./git_quick.sh all \"修复bug\""
        echo "  ./git_quick.sh commit \"添加新功能\""
        echo "  ./git_quick.sh push"
        ;;
esac

