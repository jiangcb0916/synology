# Git 上传命令 - V1.0.0 分支

## 📋 当前状态

- 当前分支：`v1.0.0`
- 远程仓库：`git@github.com:jiangcb0916/synology.git`
- 待提交文件：
  - `src/handlers/card_callback_handler.py` (已修改)
  - `src/services/dingtalk_card_service.py` (已修改)
  - `DINGTALK_CARD_TEMPLATE_GUIDE.md` (新文件)

## 🚀 上传命令

### 方法1：标准流程（推荐）

```bash
# 1. 添加所有更改
git add .

# 2. 提交更改（请根据实际情况修改提交信息）
git commit -m "feat: 添加卡片状态更新功能和模板指南

- 添加卡片状态更新功能（已同意/已拒绝）
- 修复卡片变量显示问题
- 添加钉钉卡片模板完整指南文档"

# 3. 推送到远程分支
git push origin v1.0.0
```

### 方法2：如果远程分支不存在，需要创建

```bash
# 1. 添加所有更改
git add .

# 2. 提交更改
git commit -m "feat: 添加卡片状态更新功能和模板指南"

# 3. 创建并推送到远程分支
git push -u origin v1.0.0
```

### 方法3：如果要创建新的 V1.0.0 分支（大写）

```bash
# 1. 添加所有更改
git add .

# 2. 提交更改
git commit -m "feat: 添加卡片状态更新功能和模板指南"

# 3. 创建新分支 V1.0.0（从当前分支）
git checkout -b V1.0.0

# 4. 推送到远程
git push -u origin V1.0.0
```

## 📝 提交信息建议

根据本次更改，建议使用以下提交信息：

```bash
git commit -m "feat: 添加卡片状态更新功能和模板指南

- 实现卡片状态更新功能（已同意/已拒绝）
- 修复卡片变量显示问题（单大括号改为双大括号）
- 添加 update_card_status 方法
- 优化卡片回调处理逻辑
- 添加钉钉卡片模板完整指南文档"
```

## ⚠️ 注意事项

1. **分支名称**：当前分支是 `v1.0.0`（小写），如果远程已有同名分支，直接推送即可
2. **提交信息**：请根据实际情况修改提交信息
3. **代码审查**：推送前建议检查代码是否有错误

## 🔍 验证命令

推送后，可以使用以下命令验证：

```bash
# 查看远程分支
git branch -r

# 查看提交历史
git log --oneline -5

# 查看当前状态
git status
```

