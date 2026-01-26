# Git 版本控制使用指南

## 📋 当前项目状态

- ✅ Git仓库已初始化
- ✅ 远程仓库：`git@github.com:jiangcb0916/synology.git`
- ✅ 当前分支：`main`
- ✅ 已配置忽略文件：`config.ini`、`.specstory/`、`backup_v5/`、`.cursorindexingignore`

## 🚀 日常版本控制流程

### 1. 查看当前状态

```bash
# 查看工作区状态
git status

# 查看文件变更详情
git diff

# 查看已暂存的文件
git diff --staged
```

### 2. 添加文件到暂存区

```bash
# 添加所有更改的文件
git add .

# 添加特定文件
git add <文件名>

# 添加特定目录
git add <目录名>/

# 交互式添加（可以选择性添加）
git add -p
```

### 3. 提交更改

```bash
# 提交暂存区的更改
git commit -m "提交说明信息"

# 提交时添加详细描述
git commit -m "简短说明" -m "详细描述"

# 修改最后一次提交（如果忘记添加文件）
git commit --amend
```

**提交信息规范建议：**
- `feat: 添加新功能`
- `fix: 修复bug`
- `docs: 更新文档`
- `style: 代码格式调整`
- `refactor: 代码重构`
- `test: 添加测试`
- `chore: 构建/工具链相关`

### 4. 推送到远程仓库

```bash
# 推送到远程main分支
git push

# 首次推送或推送到新分支
git push -u origin main

# 推送到指定分支
git push origin <分支名>
```

## 📦 完整上传流程示例

### 第一次上传新项目

```bash
# 1. 初始化git仓库（如果还没有）
git init

# 2. 添加所有文件
git add .

# 3. 提交
git commit -m "Initial commit: 项目初始化"

# 4. 添加远程仓库
git remote add origin git@github.com:jiangcb0916/synology.git

# 5. 设置分支名
git branch -M main

# 6. 推送到远程
git push -u origin main
```

### 日常更新项目

```bash
# 1. 查看更改
git status

# 2. 添加更改
git add .

# 3. 提交更改
git commit -m "描述你的更改"

# 4. 推送到远程
git push
```

## 🔄 版本管理操作

### 查看历史记录

```bash
# 查看提交历史
git log

# 简洁模式
git log --oneline

# 查看最近N条记录
git log -n 5

# 图形化显示分支
git log --graph --oneline --all
```

### 创建标签（版本号）

```bash
# 创建标签
git tag v1.0.0

# 创建带注释的标签
git tag -a v1.0.0 -m "版本1.0.0发布"

# 查看所有标签
git tag

# 推送标签到远程
git push origin v1.0.0

# 推送所有标签
git push origin --tags
```

### 回退版本

```bash
# 查看提交历史（获取commit hash）
git log --oneline

# 回退到指定版本（保留工作区更改）
git reset --soft <commit-hash>

# 回退到指定版本（保留暂存区）
git reset --mixed <commit-hash>

# 回退到指定版本（完全回退）
git reset --hard <commit-hash>

# 撤销最后一次提交（保留更改）
git reset --soft HEAD~1
```

## 🌿 分支管理

### 创建和切换分支

```bash
# 创建新分支
git branch <分支名>

# 切换到分支
git checkout <分支名>

# 创建并切换到新分支
git checkout -b <分支名>

# 查看所有分支
git branch

# 查看远程分支
git branch -r
```

### 合并分支

```bash
# 切换到主分支
git checkout main

# 合并分支
git merge <分支名>

# 删除分支
git branch -d <分支名>

# 强制删除分支
git branch -D <分支名>
```

## 📥 从远程获取更新

```bash
# 获取远程更新（不合并）
git fetch origin

# 拉取并合并远程更新
git pull

# 拉取指定分支
git pull origin main
```

## 🔍 常用查询命令

```bash
# 查看被跟踪的文件
git ls-files

# 查看被忽略的文件
git status --ignored

# 查看某个文件的修改历史
git log -- <文件路径>

# 查看文件的详细变更
git log -p -- <文件路径>
```

## ⚠️ 注意事项

1. **提交前检查**：使用 `git status` 确认要提交的文件
2. **敏感信息**：确保 `config.ini` 等敏感文件不会被提交
3. **提交信息**：写清楚提交说明，方便后续查看历史
4. **定期推送**：及时推送到远程，避免本地丢失
5. **分支保护**：重要项目建议保护 `main` 分支

## 🛠️ 故障处理

### 撤销未提交的更改

```bash
# 撤销工作区的更改
git restore <文件>

# 撤销所有工作区更改
git restore .

# 撤销暂存区的文件
git restore --staged <文件>
```

### 解决冲突

```bash
# 拉取时如果有冲突
git pull

# 手动解决冲突后
git add <冲突文件>
git commit -m "解决冲突"
```

### 查看远程仓库信息

```bash
# 查看远程仓库
git remote -v

# 修改远程仓库地址
git remote set-url origin <新地址>

# 删除远程仓库
git remote remove origin
```

## 📚 推荐工作流程

1. **开始工作前**：`git pull` 获取最新代码
2. **修改文件后**：`git status` 查看更改
3. **准备提交**：`git add .` 添加更改
4. **提交更改**：`git commit -m "说明"`
5. **推送代码**：`git push`
6. **定期创建标签**：`git tag v1.x.x` 标记重要版本

## 🔗 相关资源

- [Git官方文档](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com/)
- [Git Cheat Sheet](https://education.github.com/git-cheat-sheet-education.pdf)

