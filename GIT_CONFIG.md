# Git 配置说明

## 配置要求

1. **上传之后不进行跟踪** - 已跟踪的文件可以设置为不跟踪
2. **git后台的删除不影响本地文件** - 从git删除文件时保留本地文件
3. **上传之后不删除本地文件** - 提交时不会删除本地文件
4. **config.ini不上传git** - 已在.gitignore中配置

## 配置步骤

### 1. 初始化Git仓库（如果还没有）

```bash
git init
```

### 2. 确保config.ini不被跟踪

如果`config.ini`已经被git跟踪，需要从git中移除但保留本地文件：

```bash
# 从git索引中移除，但保留本地文件
git rm --cached config.ini

# 提交这个更改
git commit -m "Remove config.ini from git tracking"
```

### 3. 对于已跟踪但不想继续跟踪的文件

如果某些文件已经被跟踪，但之后不想再跟踪（上传后不跟踪），可以使用：

```bash
# 方法1：使用 --skip-worktree（推荐，更安全）
git update-index --skip-worktree <文件路径>

# 方法2：使用 --assume-unchanged（性能更好，但不够安全）
git update-index --assume-unchanged <文件路径>

# 取消设置（如果需要恢复跟踪）
git update-index --no-skip-worktree <文件路径>
# 或
git update-index --no-assume-unchanged <文件路径>
```

### 4. 从git删除文件但保留本地文件

如果需要从git仓库中删除文件，但不删除本地文件：

```bash
# 从git中删除，但保留本地文件
git rm --cached <文件路径>

# 提交更改
git commit -m "Remove file from git but keep local"
```

### 5. 查看当前被跟踪的文件

```bash
# 查看所有被跟踪的文件
git ls-files

# 查看被skip-worktree标记的文件
git ls-files -v | grep ^S

# 查看被assume-unchanged标记的文件
git ls-files -v | grep ^h
```

## 当前配置状态

- ✅ `config.ini` 已在 `.gitignore` 中，不会被跟踪
- ✅ `.gitignore` 已配置Python、日志、备份等常见忽略项

## 注意事项

1. **config.ini包含敏感信息**（密码、密钥等），确保不要提交到git
2. 如果`config.ini`已经被跟踪，必须先执行 `git rm --cached config.ini`
3. 使用`--skip-worktree`比`--assume-unchanged`更安全，因为它会阻止git覆盖本地更改
4. 从远程仓库拉取时，如果远程删除了文件，本地文件不会被删除（因为使用了`--cached`）

## 快速检查脚本

运行以下命令检查config.ini是否被跟踪：

```bash
git ls-files | grep config.ini
```

如果没有输出，说明`config.ini`没有被跟踪，配置正确。

