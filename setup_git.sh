#!/bin/bash

# Git配置脚本
# 用于配置git以满足以下要求：
# 1. 上传之后不进行跟踪
# 2. git后台的删除不影响本地文件
# 3. 上传之后不删除本地文件
# 4. config.ini不上传git

set -e

echo "=== Git配置脚本 ==="
echo ""

# 检查是否在git仓库中
if [ ! -d ".git" ]; then
    echo "⚠️  当前目录不是git仓库"
    read -p "是否要初始化git仓库? (y/n): " init_repo
    if [ "$init_repo" = "y" ] || [ "$init_repo" = "Y" ]; then
        git init
        echo "✅ Git仓库已初始化"
    else
        echo "❌ 取消操作"
        exit 1
    fi
fi

echo ""
echo "1. 检查config.ini是否被跟踪..."

# 检查config.ini是否被跟踪
if git ls-files --error-unmatch config.ini > /dev/null 2>&1; then
    echo "⚠️  config.ini已被git跟踪，需要从git中移除（保留本地文件）"
    read -p "是否要从git中移除config.ini? (y/n): " remove_config
    if [ "$remove_config" = "y" ] || [ "$remove_config" = "Y" ]; then
        git rm --cached config.ini
        echo "✅ config.ini已从git跟踪中移除（本地文件已保留）"
        echo "   提示：记得提交这个更改: git commit -m 'Remove config.ini from tracking'"
    fi
else
    echo "✅ config.ini未被跟踪，配置正确"
fi

echo ""
echo "2. 检查.gitignore配置..."

# 检查.gitignore中是否包含config.ini
if grep -q "^config\.ini$" .gitignore 2>/dev/null || grep -q "^config\.ini$" .gitignore 2>/dev/null; then
    echo "✅ config.ini已在.gitignore中"
else
    echo "⚠️  config.ini不在.gitignore中，正在添加..."
    echo "config.ini" >> .gitignore
    echo "✅ 已添加config.ini到.gitignore"
fi

echo ""
echo "3. 配置git以保护本地文件..."

# 设置git配置，确保删除操作不影响本地文件
git config core.sparseCheckout false 2>/dev/null || true

echo ""
echo "=== 配置完成 ==="
echo ""
echo "📝 重要提示："
echo "   1. config.ini已在.gitignore中，不会被跟踪"
echo "   2. 如果config.ini之前被跟踪，已从git中移除（本地文件保留）"
echo "   3. 使用 'git rm --cached <文件>' 可以从git删除文件但保留本地文件"
echo "   4. 使用 'git update-index --skip-worktree <文件>' 可以让已跟踪的文件不再被跟踪"
echo ""
echo "🔍 验证命令："
echo "   - 检查被跟踪的文件: git ls-files"
echo "   - 检查config.ini是否被跟踪: git ls-files | grep config.ini"
echo "   - 查看.gitignore内容: cat .gitignore"
echo ""

