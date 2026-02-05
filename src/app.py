#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微爱基金会 Synology 用户管理系统
钉钉机器人应用主入口
"""
import logging
import logging.handlers
import os
import sys

from dingtalk_stream import DingTalkStreamClient, Credential
from dingtalk_stream.chatbot import ChatbotMessage
from dingtalk_stream.card_callback import Card_Callback_Router_Topic

from .config import Settings
from .core import SynologyService
from .services import (
    DingTalkAPIService,
    DingTalkUserService,
    DingTalkMessageService,
    DingTalkCardService
)
from .handlers import ChatbotHandler, CardCallbackHandler

# 配置日志
def setup_logging():
    """配置日志系统，同时输出到控制台和文件（按天分割）"""
    # 创建 logs 目录（如果不存在）
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除已有的处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（按天分割日志）
    log_file = os.path.join(log_dir, 'app.log')
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file,
        when='midnight',  # 每天午夜轮转
        interval=1,  # 间隔1天
        backupCount=30,  # 保留30个备份文件（由于每天轮转一次，即保留30天的日志）
        encoding='utf-8',
        utc=False  # 使用本地时间
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(log_format, date_format)
    file_handler.setFormatter(file_formatter)
    # 设置后缀格式为日期（例如：app.log.2024-01-15）
    # TimedRotatingFileHandler 会在每次轮转时：
    # 1. 将当前的 app.log 重命名为 app.log.2024-01-15（带日期后缀）
    # 2. 创建新的 app.log 文件继续写入
    # 3. 自动删除超过 backupCount 数量的旧备份文件（保留最新的30个）
    file_handler.suffix = '%Y-%m-%d'
    root_logger.addHandler(file_handler)
    
    # 设置 dingtalk-stream 的日志级别为 WARNING，减少无用日志
    logging.getLogger('dingtalk_stream').setLevel(logging.WARNING)

# 初始化日志
setup_logging()
logger = logging.getLogger(__name__)


class DingTalkBotApp:
    """钉钉机器人应用主类"""
    
    def __init__(self, config_path: str = 'config.ini'):
        """初始化应用
        
        Args:
            config_path: 配置文件路径
        """
        try:
            # 加载配置
            self.settings = Settings(config_path)
            logger.info("配置加载成功")
            
            # 初始化核心服务
            self.synology_service = SynologyService(self.settings)
            logger.info("Synology 服务初始化成功")
            
            # 初始化钉钉服务
            self.api_service = DingTalkAPIService(self.settings)
            self.user_service = DingTalkUserService(self.api_service)
            self.message_service = DingTalkMessageService(self.api_service, self.settings)
            self.card_service = DingTalkCardService(self.api_service, self.settings)
            logger.info("钉钉服务初始化成功")
            
        except Exception as e:
            logger.error(f"应用初始化失败: {e}", exc_info=True)
            raise
    
    def run(self):
        """启动 Stream 模式客户端"""
        try:
            # 创建凭证
            credential = Credential(
                self.settings.dingtalk_client_id,
                self.settings.dingtalk_client_secret
            )
            
            # 创建客户端
            client = DingTalkStreamClient(credential)
            
            # 注册聊天机器人消息处理器
            chatbot_handler = ChatbotHandler(
                settings=self.settings,
                synology_service=self.synology_service,
                api_service=self.api_service,
                user_service=self.user_service,
                message_service=self.message_service,
                card_service=self.card_service
            )
            client.register_callback_handler(ChatbotMessage.TOPIC, chatbot_handler)
            logger.info("聊天机器人消息处理器注册成功")
            
            # 注册卡片回调处理器
            card_callback_handler = CardCallbackHandler(
                settings=self.settings,
                synology_service=self.synology_service,
                user_service=self.user_service,
                message_service=self.message_service,
                card_service=self.card_service,
                admin_name=self.settings.admin_name,
                admin_userid=chatbot_handler.admin_userid,
                approver_name=self.settings.approver_name,
                approver_userid=chatbot_handler.approver_userid
            )
            
            try:
                client.register_callback_handler(Card_Callback_Router_Topic, card_callback_handler)
                logger.info("卡片回调处理器注册成功")
            except Exception as e:
                logger.error(f"注册卡片回调处理器失败: {e}", exc_info=True)
                # 尝试使用字符串形式的 topic
                try:
                    client.register_callback_handler("/v1.0/card/instances/callback", card_callback_handler)
                    logger.info("使用字符串形式注册卡片回调处理器成功")
                except Exception as e2:
                    logger.error(f"使用字符串形式注册也失败: {e2}", exc_info=True)
            
            # 打印启动信息
            logger.info("=" * 60)
            logger.info("微爱基金会 Synology 用户管理系统")
            logger.info("机器人服务已启动，正在监听消息和卡片回调...")
            if self.settings.dingtalk_card_template_id:
                logger.info(f"卡片审批流程已启用，模板ID: {self.settings.dingtalk_card_template_id}")
            else:
                logger.warning("卡片模板ID未配置，将使用直接创建用户方式")
            logger.info(f"管理员: {self.settings.admin_name}")
            logger.info(f"审批人: {self.settings.approver_name}")
            logger.info("=" * 60)
            
            print("\n" + "=" * 60)
            print("微爱基金会 Synology 用户管理系统")
            print("机器人服务已启动，正在监听消息和卡片回调...")
            print("按 Ctrl+C 停止服务")
            print("=" * 60 + "\n")
            
            # 启动服务（阻塞运行）
            client.start_forever()
            
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭服务...")
            print("\n正在关闭服务...")
        except Exception as e:
            logger.error(f"启动服务时发生错误: {e}", exc_info=True)
            print(f"\n启动服务时发生错误: {e}")
            raise


def main():
    """主函数"""
    try:
        app = DingTalkBotApp('config.ini')
        app.run()
    except Exception as e:
        logger.error(f"应用异常退出: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

