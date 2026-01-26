# 微爱基金会 Synology 用户管理系统 - 技术文档

**项目名称**: 微爱基金会 Synology 用户管理系统  
**版本**: v6.0.0  
**最后更新**: 2026-01-24  
**状态**: ✅ 生产就绪

---

## 目录

1. [项目概述](#项目概述)
2. [系统架构](#系统架构)
3. [功能特性](#功能特性)
4. [快速开始](#快速开始)
5. [配置说明](#配置说明)
6. [使用指南](#使用指南)
7. [开发文档](#开发文档)
8. [部署运维](#部署运维)
9. [常见问题](#常见问题)

---

## 项目概述

基于钉钉机器人的 Synology NAS 用户自动创建和管理系统，支持审批流程和权限控制。

### 核心特性

- 🤖 **钉钉机器人集成** - 通过钉钉机器人与用户交互
- 👥 **自动用户创建** - 根据姓名自动创建 Synology 用户账户
- 🔐 **权限管理** - 只有管理员可以创建用户
- 📝 **审批流程** - 支持钉钉卡片审批流程（可选）
- 🔒 **安全性** - 敏感信息仅通过私聊发送
- 📊 **智能查找** - 自动在钉钉组织内查找用户

### 技术栈

- **语言**: Python 3.x
- **框架**: dingtalk-stream SDK
- **通信**: SSH (Paramiko)
- **依赖管理**: pip + requirements.txt

---

## 系统架构

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      钉钉开放平台                              │
│                (Stream 模式 - 长连接)                          │
└─────────────────┬───────────────────────────────┬─────────────┘
                  │                               │
                  │ 聊天消息                       │ 卡片回调
                  ↓                               ↓
┌─────────────────────────────────────────────────────────────┐
│                    DingTalk Stream Client                   │
│                    (dingtalk-stream SDK)                    │
└─────────────────┬───────────────────────────────┬─────────────┘
                  │                               │
                  ↓                               ↓
         ┌─────────────────┐           ┌──────────────────────┐
         │ ChatbotHandler  │           │ CardCallbackHandler  │
         │  (消息处理器)    │           │   (卡片回调处理器)    │
         └────────┬────────┘           └──────────┬───────────┘
                  │                               │
                  └───────────┬───────────────────┘
                              │
                              ↓
         ┌────────────────────────────────────────┐
         │          Service Layer (服务层)         │
         │  ┌──────────────────────────────────┐  │
         │  │  DingTalkAPIService              │  │
         │  │  (Token 管理)                    │  │
         │  └───────────┬──────────────────────┘  │
         │              │                          │
         │  ┌───────────┴──────────────────────┐  │
         │  │  DingTalkUserService             │  │
         │  │  (用户查找)                      │  │
         │  └──────────────────────────────────┘  │
         │  ┌──────────────────────────────────┐  │
         │  │  DingTalkMessageService          │  │
         │  │  (消息发送)                      │  │
         │  └──────────────────────────────────┘  │
         │  ┌──────────────────────────────────┐  │
         │  │  DingTalkCardService             │  │
         │  │  (卡片管理)                      │  │
         │  └──────────────────────────────────┘  │
         └────────────────┬───────────────────────┘
                          │
                          ↓
         ┌────────────────────────────────────────┐
         │       Core Layer (核心业务层)           │
         │  ┌──────────────────────────────────┐  │
         │  │  SynologyService                 │  │
         │  │  (Synology 用户管理)             │  │
         │  └──────────────────────────────────┘  │
         └────────────────┬───────────────────────┘
                          │
                          ↓ SSH 连接
         ┌────────────────────────────────────────┐
         │          Synology NAS                  │
         │      (DSM 7.x 用户管理系统)             │
         └────────────────────────────────────────┘
```

### 分层架构

```
┌─────────────────────────────────┐
│    Presentation Layer           │  ← handlers/ (处理器层)
├─────────────────────────────────┤
│    Service Layer                │  ← services/ (服务层)
├─────────────────────────────────┤
│    Business Logic Layer         │  ← core/ (核心业务层)
├─────────────────────────────────┤
│    Infrastructure Layer         │  ← utils/ (工具层)
├─────────────────────────────────┤
│    Configuration Layer          │  ← config/ (配置层)
└─────────────────────────────────┘
```

### 目录结构

```
synology/
├── main.py                    # 主入口文件
├── config.ini                 # 配置文件
├── config.ini.example         # 配置示例
├── requirements.txt           # 依赖包列表
├── README.md                  # 项目说明
├── .gitignore                 # Git忽略配置
├── logs/                      # 日志目录
├── tests/                     # 测试目录
└── src/                       # 源代码目录
    ├── app.py                 # 应用主类
    ├── config/                # 配置管理模块
    │   └── settings.py
    ├── core/                  # 核心业务模块
    │   └── synology_service.py
    ├── services/              # 服务层模块
    │   ├── dingtalk_api_service.py
    │   ├── dingtalk_user_service.py
    │   ├── dingtalk_message_service.py
    │   └── dingtalk_card_service.py
    ├── handlers/              # 处理器模块
    │   ├── chatbot_handler.py
    │   └── card_callback_handler.py
    ├── models/                # 数据模型（预留）
    └── utils/                 # 工具模块
        ├── name_utils.py
        ├── password_generator.py
        └── message_formatter.py
```

---

## 功能特性

### 用户创建流程

#### 无审批模式

```
用户发送消息 → 聊天机器人处理 → 查找钉钉用户 → 创建 Synology 账户 → 发送账户信息
```

#### 审批模式

```
用户发送消息 → 聊天机器人处理 → 发送审批卡片 → 管理员审批 → 创建账户 → 发送通知
```

### 核心模块

#### 1. 配置层 (config/)
- **Settings**: 统一配置管理
  - 配置文件读取和验证
  - 类型安全的属性访问
  - 默认值处理

#### 2. 核心业务层 (core/)
- **SynologyService**: Synology 用户管理
  - SSH 连接管理
  - 用户创建和管理
  - 用户存在性检查

#### 3. 服务层 (services/)
- **DingTalkAPIService**: Token 管理和缓存
- **DingTalkUserService**: 用户查找（多策略）
- **DingTalkMessageService**: 消息发送（私聊/群聊）
- **DingTalkCardService**: 审批卡片管理

#### 4. 处理器层 (handlers/)
- **ChatbotHandler**: 消息处理和权限检查
- **CardCallbackHandler**: 卡片回调处理

#### 5. 工具层 (utils/)
- **NameUtils**: 姓名转拼音
- **PasswordGenerator**: 密码生成
- **MessageFormatter**: 消息格式化

---

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置文件

1. 复制配置示例：
```bash
cp config.ini.example config.ini
```

2. 编辑配置文件：
```ini
[synology]
url = https://your-nas-ip:5001
username = admin
password = your_password
ssh_port = 22

[dingtalk]
client_id = your_client_id
client_secret = your_client_secret
card_template_id = your_card_template_id  # 可选
admin_name = 管理员姓名
```

### 启动应用

```bash
python main.py
```

或

```bash
python3 main.py
```

### 验证安装

```bash
python3 -c "from src.app import DingTalkBotApp; print('✅ 安装成功')"
```

---

## 配置说明

### Synology 配置

| 配置项 | 说明 | 必填 |
|--------|------|------|
| url | Synology NAS 地址 | ✅ |
| username | 管理员用户名 | ✅ |
| password | 管理员密码 | ✅ |
| ssh_port | SSH 端口 | ❌ (默认 22) |

### 钉钉配置

| 配置项 | 说明 | 必填 |
|--------|------|------|
| client_id | 钉钉机器人 Client ID | ✅ |
| client_secret | 钉钉机器人 Client Secret | ✅ |
| card_template_id | 审批卡片模板 ID | ❌ |
| admin_name | 管理员姓名 | ✅ |

### 配置示例

```ini
[synology]
url = https://172.16.70.17:5001
username = admin
password = your_secure_password
ssh_port = 22

[dingtalk]
client_id = dingxxxxxxxxxxxxx
client_secret = your_client_secret_here
card_template_id = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.schema
admin_name = 张三
```

---

## 使用指南

### 通过钉钉机器人创建用户

1. **找到机器人**
   - 在钉钉中搜索并添加机器人

2. **发送创建请求**
   - 格式：`@机器人 用户姓名`
   - 示例：`@用户管理机器人 李四`

3. **等待审批**（如果启用了审批流程）
   - 管理员会收到审批卡片
   - 点击"通过"或"拒绝"

4. **接收账户信息**
   - 用户会通过私聊收到账户信息
   - 包含用户名、密码和挂载脚本

### 权限说明

- ✅ 只有配置文件中指定的管理员可以创建用户
- ❌ 其他用户尝试使用会收到权限不足提示
- 🔒 账户信息仅通过私聊发送，不会在群聊中显示

### 安全最佳实践

1. **配置文件安全**
   - 不要将 `config.ini` 提交到版本控制
   - 使用强密码
   - 定期更换密钥

2. **权限控制**
   - 只授权必要的管理员
   - 定期审计创建的用户

3. **日志管理**
   - 定期检查日志文件
   - 监控异常行为

---

## 开发文档

### 设计原则

#### SOLID 原则

- ✅ **单一职责原则** - 每个类只负责一个功能领域
- ✅ **开闭原则** - 对扩展开放，对修改封闭
- ✅ **里氏替换原则** - 服务可以轻松替换实现
- ✅ **接口隔离原则** - 小而专注的接口
- ✅ **依赖倒置原则** - 依赖抽象而非具体实现

#### 设计模式

1. **依赖注入 (Dependency Injection)**
   - 所有服务通过构造函数注入依赖
   - 提高可测试性

2. **服务层模式 (Service Layer)**
   - 业务逻辑封装在服务层
   - 与表示层分离

3. **策略模式 (Strategy)**
   - 用户查找使用多种策略
   - 易于扩展新策略

4. **模板方法模式 (Template Method)**
   - 消息格式化使用统一模板

### 添加新功能

#### 添加新的消息类型

1. 在 `src/utils/message_formatter.py` 添加格式化方法：
```python
@staticmethod
def format_new_message_type(param1, param2):
    return "# 新消息类型\n\n内容..."
```

2. 在处理器中调用：
```python
message = MessageFormatter.format_new_message_type(p1, p2)
self.message_service.send_private_markdown(user_id, None, "标题", message)
```

#### 添加新的通知渠道

1. 创建新的服务类 `src/services/email_service.py`：
```python
class EmailService:
    def send_email(self, to, subject, content):
        # 实现邮件发送逻辑
        pass
```

2. 在 `src/app.py` 中初始化并注入

#### 添加新的用户查找策略

在 `src/services/dingtalk_user_service.py` 添加新方法：
```python
def _search_user_by_new_method(self, name, token):
    # 实现新的查找策略
    pass
```

### 代码规范

- 使用 Type Hints 提供类型提示
- 所有公共方法必须有文档字符串
- 遵循 PEP 8 代码风格
- 单个方法不超过 50 行
- 单个类不超过 300 行

### 测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_synology_service.py

# 查看测试覆盖率
pytest --cov=src tests/
```

---

## 部署运维

### 系统要求

- Python 3.7+
- 网络访问：钉钉开放平台、Synology NAS
- 权限：Synology 管理员账户

### 部署步骤

1. **准备环境**
```bash
git clone <repository>
cd synology
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2. **配置应用**
```bash
cp config.ini.example config.ini
# 编辑 config.ini
```

3. **启动服务**
```bash
python main.py
```

### 使用 systemd 部署（Linux）

创建服务文件 `/etc/systemd/system/synology-bot.service`：

```ini
[Unit]
Description=Synology User Management Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/synology
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable synology-bot
sudo systemctl start synology-bot
sudo systemctl status synology-bot
```

### 日志管理

日志文件位置：`logs/`

查看日志：
```bash
tail -f logs/app.log
```

### 监控

建议监控指标：
- 应用运行状态
- 用户创建成功率
- API 调用延迟
- 错误日志数量

---

## 常见问题

### Q: 如何禁用审批流程？

A: 在 `config.ini` 中删除或注释掉 `card_template_id` 配置项。

### Q: 如何添加多个管理员？

A: 当前版本只支持单个管理员。如需多个管理员，需要修改代码中的权限检查逻辑。

### Q: 用户创建失败怎么办？

A: 检查以下几点：
1. Synology SSH 连接是否正常
2. 管理员账户是否有权限
3. 用户名是否已存在
4. 查看日志文件获取详细错误信息

### Q: 如何修改密码生成规则？

A: 编辑 `src/utils/password_generator.py` 中的 `generate()` 方法。

### Q: 支持哪些 Synology 系统版本？

A: 已在 DSM 7.x 测试通过，理论上支持所有支持 SSH 的 DSM 版本。

### Q: 如何备份和恢复？

A: 备份以下内容：
- `config.ini` - 配置文件
- `logs/` - 日志文件（可选）

恢复时复制回对应位置即可。

---

## 技术支持

### 问题反馈

如遇到问题，请提供：
1. 错误信息
2. 日志文件
3. 操作步骤
4. 系统环境

### 联系方式

- 内部项目，请联系系统管理员
- Email: admin@example.com

---

## 附录

### 依赖包说明

| 包名 | 版本 | 用途 |
|------|------|------|
| requests | >=2.28.0 | HTTP 请求 |
| urllib3 | <2.0.0 | URL 处理 |
| paramiko | >=2.12.0 | SSH 连接 |
| dingtalk-stream | >=0.8.0 | 钉钉 Stream SDK |
| pypinyin | >=0.49.0 | 拼音转换 |
| alibabacloud-dingtalk | >=2.0.0 | 钉钉卡片 SDK |

### 术语表

- **DSM**: DiskStation Manager - Synology 操作系统
- **Stream 模式**: 钉钉长连接推送模式
- **卡片回调**: 用户点击卡片按钮触发的事件
- **VLF 组**: vlf 用户组，预配置了权限

---

**文档版本**: v6.0.0  
**最后更新**: 2026-01-24  
**作者**: jiangcb  
**许可证**: 内部使用
