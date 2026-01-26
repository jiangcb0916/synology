#!/bin/bash
# upload_with_rsync.sh - 使用rsync上传整个目录

# 配置参数
LOCAL_DIR="/Users/jiangcb/Desktop/app/synology/"  # 本地目录路径（注意结尾的/）
REMOTE_USER="root"
REMOTE_HOST="172.16.80.132"
REMOTE_DIR="/opt/qunhui/"      # 远程目录路径
SSH_PORT="22"                                # SSH端口，默认22
# EXCLUDE_FILE="exclude_list.txt"              # 排除文件列表（可选）

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查本地目录是否存在
if [ ! -d "$LOCAL_DIR" ]; then
    echo -e "${RED}错误：本地目录 '$LOCAL_DIR' 不存在${NC}"
    exit 1
fi

echo -e "${GREEN}开始上传目录: $LOCAL_DIR${NC}"
echo -e "${GREEN}目标服务器: $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR${NC}"
echo ""

# 创建排除文件（如果需要排除特定文件）
# 取消注释以下行来创建示例排除文件
# cat > $EXCLUDE_FILE << EOF
# *.tmp
# *.log
# node_modules/
# .git/
# .DS_Store
# EOF

# 构建rsync命令
RSYNC_CMD="rsync -avz --progress"

# 添加排除文件（如果存在）
if [ -f "$EXCLUDE_FILE" ]; then
    RSYNC_CMD="$RSYNC_CMD --exclude-from=$EXCLUDE_FILE"
    echo -e "${YELLOW}使用排除文件: $EXCLUDE_FILE${NC}"
fi

# 添加端口配置（如果不是默认22）
if [ "$SSH_PORT" != "22" ]; then
    RSYNC_CMD="$RSYNC_CMD -e 'ssh -p $SSH_PORT'"
fi

# 执行上传
echo -e "${YELLOW}执行命令: $RSYNC_CMD $LOCAL_DIR $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR${NC}"
echo ""

# 实际执行rsync命令
eval $RSYNC_CMD "$LOCAL_DIR" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR"

# 检查执行结果
if [ $? -eq 0 ]; then
    echo -e "${GREEN}上传完成！${NC}"
    echo -e "${GREEN}本地目录大小: $(du -sh $LOCAL_DIR | cut -f1)${NC}"
    
    # 可选：验证远程目录大小
    echo -e "${YELLOW}正在验证远程目录...${NC}"
    ssh -p $SSH_PORT $REMOTE_USER@$REMOTE_HOST "du -sh $REMOTE_DIR 2>/dev/null || echo '无法获取远程目录大小'"
else
    echo -e "${RED}上传失败！${NC}"
    exit 1
fi