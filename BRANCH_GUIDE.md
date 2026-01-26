# Git 版本分支创建指南

## 🌿 什么是版本分支？

版本分支用于：
- 开发新功能而不影响主分支
- 修复bug
- 准备发布新版本
- 实验性开发

## 📋 创建版本分支的方法

### 方法1：从当前分支创建新分支

```bash
# 创建并切换到新分支
git checkout -b v1.0.0

# 或者使用新语法
git switch -c v1.0.0
```

### 方法2：从指定提交创建分支

```bash
# 查看提交历史获取commit hash
git log --oneline

# 从指定提交创建分支
git checkout -b v1.0.0 <commit-hash>
```

### 方法3：从远程分支创建本地分支

```bash
# 从远程分支创建并跟踪
git checkout -b v1.0.0 origin/main
```

## 🚀 版本分支命名规范

### 推荐命名方式：

1. **版本号分支**：`v1.0.0`、`v1.1.0`、`v2.0.0`
2. **功能分支**：`feature/user-login`、`feature/payment`
3. **修复分支**：`fix/bug-123`、`hotfix/critical-issue`
4. **发布分支**：`release/v1.0.0`、`release/v1.1.0`

## 📝 完整工作流程示例

### 创建并推送版本分支

```bash
# 1. 确保在主分支且是最新的
git checkout main
git pull

# 2. 创建版本分支
git checkout -b v1.0.0

# 3. 在新分支上开发/修改
# ... 进行你的修改 ...

# 4. 提交更改
git add .
git commit -m "feat: 版本1.0.0功能更新"

# 5. 推送新分支到远程
git push -u origin v1.0.0
```

### 切换分支

```bash
# 切换到主分支
git checkout main

# 切换到版本分支
git checkout v1.0.0

# 查看所有分支
git branch

# 查看所有分支（包括远程）
git branch -a
```

### 合并分支到主分支

```bash
# 1. 切换到主分支
git checkout main

# 2. 拉取最新代码
git pull

# 3. 合并版本分支
git merge v1.0.0

# 4. 解决冲突（如果有）
# ... 手动解决冲突 ...

# 5. 推送合并后的主分支
git push
```

## 🏷️ 为版本分支创建标签

```bash
# 在版本分支上创建标签
git checkout v1.0.0
git tag -a v1.0.0 -m "版本1.0.0发布"

# 推送标签到远程
git push origin v1.0.0
git push origin --tags
```

## 🔄 常用分支操作

```bash
# 查看分支列表
git branch              # 本地分支
git branch -r           # 远程分支
git branch -a           # 所有分支

# 删除本地分支
git branch -d v1.0.0    # 安全删除（已合并）
git branch -D v1.0.0    # 强制删除（未合并）

# 删除远程分支
git push origin --delete v1.0.0

# 重命名分支
git branch -m old-name new-name
```

## 📊 分支管理最佳实践

1. **主分支保护**：`main` 分支应该保持稳定，只接受合并
2. **功能开发**：在功能分支开发，完成后合并到主分支
3. **版本发布**：使用版本分支准备发布，完成后打标签
4. **及时清理**：删除已合并的旧分支，保持仓库整洁

## 🎯 实际应用场景

### 场景1：开发新功能

```bash
git checkout -b feature/new-feature
# 开发功能...
git add .
git commit -m "feat: 添加新功能"
git push -u origin feature/new-feature
```

### 场景2：修复bug

```bash
git checkout -b fix/bug-description
# 修复bug...
git add .
git commit -m "fix: 修复bug描述"
git push -u origin fix/bug-description
```

### 场景3：准备发布版本

```bash
git checkout -b release/v1.0.0
# 准备发布内容...
git add .
git commit -m "chore: 准备v1.0.0发布"
git tag -a v1.0.0 -m "版本1.0.0发布"
git push -u origin release/v1.0.0
git push origin --tags
```

## ⚠️ 注意事项

1. **推送前检查**：确保分支名称正确
2. **及时推送**：创建分支后及时推送到远程
3. **分支命名**：使用清晰的命名规范
4. **定期同步**：从主分支定期拉取更新到功能分支
5. **合并前测试**：合并到主分支前充分测试

## 🔍 查看分支信息

```bash
# 查看当前分支
git branch --show-current

# 查看分支的最后提交
git branch -v

# 查看分支的跟踪关系
git branch -vv

# 查看分支图
git log --graph --oneline --all --decorate
```

