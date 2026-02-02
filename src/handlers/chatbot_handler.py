#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉机器人消息处理器
负责处理用户发送给机器人的消息
"""
import logging
import re
from typing import Optional, Tuple

from dingtalk_stream.chatbot import ChatbotMessage, ChatbotHandler as BaseChatbotHandler, AckMessage

from ..core import SynologyService
from ..services import (
    DingTalkAPIService,
    DingTalkUserService,
    DingTalkMessageService,
    DingTalkCardService
)
from ..utils import MessageFormatter
from ..config import Settings

logger = logging.getLogger(__name__)


class ChatbotHandler(BaseChatbotHandler):
    """钉钉机器人消息处理器"""
    
    def __init__(
        self,
        settings: Settings,
        synology_service: SynologyService,
        api_service: DingTalkAPIService,
        user_service: DingTalkUserService,
        message_service: DingTalkMessageService,
        card_service: DingTalkCardService
    ):
        """初始化处理器
        
        Args:
            settings: 配置对象
            synology_service: Synology 服务
            api_service: 钉钉 API 服务
            user_service: 钉钉用户服务
            message_service: 钉钉消息服务
            card_service: 钉钉卡片服务
        """
        super(ChatbotHandler, self).__init__()
        self.settings = settings
        self.synology_service = synology_service
        self.api_service = api_service
        self.user_service = user_service
        self.message_service = message_service
        self.card_service = card_service
        
        # 管理员配置
        self.admin_name = settings.admin_name
        self.admin_userid: Optional[str] = None
        self._init_admin_userid()
        
        # 审批人配置
        self.approver_name = settings.approver_name
        self.approver_userid: Optional[str] = None
        self._init_approver_userid()
    
    def _init_admin_userid(self):
        """初始化管理员 userid"""
        try:
            self.admin_userid = self.user_service.find_user_by_name(self.admin_name)
            if self.admin_userid:
                logger.info(f"管理员 {self.admin_name} 的 userid: {self.admin_userid}")
            else:
                logger.warning(f"未找到管理员用户: {self.admin_name}，权限检查将失效")
        except Exception as e:
            logger.error(f"初始化管理员 userid 失败: {e}", exc_info=True)
    
    def _init_approver_userid(self):
        """初始化审批人 userid"""
        try:
            self.approver_userid = self.user_service.find_user_by_name(self.approver_name)
            if self.approver_userid:
                logger.info(f"审批人 {self.approver_name} 的 userid: {self.approver_userid}")
            else:
                logger.warning(f"未找到审批人用户: {self.approver_name}，审批卡片将无法发送")
        except Exception as e:
            logger.error(f"初始化审批人 userid 失败: {e}", exc_info=True)
    
    def _check_admin_permission(self, sender_staff_id: str) -> bool:
        """检查发送者是否有管理员权限
        
        Args:
            sender_staff_id: 发送者 ID
            
        Returns:
            是否有管理员权限
        """
        if not self.admin_userid:
            logger.warning("管理员 userid 未初始化，拒绝所有请求")
            return False
        
        if not sender_staff_id:
            return False
        
        # 比较 userid
        if sender_staff_id == self.admin_userid:
            return True
        
        # 如果 userid 不匹配，尝试获取发送者姓名进行二次验证
        sender_name = self.user_service.get_user_name_by_id(sender_staff_id)
        if sender_name and sender_name.strip() == self.admin_name.strip():
            return True
        
        return False
    
    def _is_group_message(self, message: ChatbotMessage) -> bool:
        """检查是否是群消息
        
        Args:
            message: 消息对象
            
        Returns:
            是否是群消息
        """
        if hasattr(message, 'conversationType'):
            conversation_type = message.conversationType
            return conversation_type == 2 or str(conversation_type) == "2"
        return False
    
    def _get_conversation_id(self, message: ChatbotMessage) -> Optional[str]:
        """获取会话 ID
        
        Args:
            message: 消息对象
            
        Returns:
            会话 ID 或 None
        """
        if hasattr(message, 'openConversationId'):
            return message.openConversationId
        elif hasattr(message, 'conversationId'):
            return message.conversationId
        return None
    
    def _get_sender_info(self, incoming_message: ChatbotMessage, callback_data=None) -> Tuple[Optional[str], Optional[str]]:
        """提取发送者 ID 和会话 ID
        
        Args:
            incoming_message: 消息对象
            callback_data: 回调数据（可选）
            
        Returns:
            (发送者 ID, 会话 ID) 元组
        """
        sender_staff_id = None
        open_conversation_id = None
        
        # 获取发送者 ID
        if hasattr(incoming_message, 'senderStaffId'):
            sender_staff_id = incoming_message.senderStaffId
        elif hasattr(incoming_message, 'senderId'):
            sender_staff_id = incoming_message.senderId
        elif hasattr(incoming_message, 'sender'):
            sender_obj = incoming_message.sender
            if hasattr(sender_obj, 'staffId'):
                sender_staff_id = sender_obj.staffId
            elif hasattr(sender_obj, 'dingtalkId'):
                sender_staff_id = sender_obj.dingtalkId
            elif isinstance(sender_obj, dict):
                sender_staff_id = sender_obj.get('staffId') or sender_obj.get('dingtalkId')
        
        # 获取会话 ID
        open_conversation_id = self._get_conversation_id(incoming_message)
        
        # 从原始数据中获取（如果前面没获取到）
        if (not sender_staff_id or not open_conversation_id) and callback_data and isinstance(callback_data, dict):
            if not sender_staff_id:
                sender_staff_id = (callback_data.get('senderStaffId') or 
                                  callback_data.get('senderId') or
                                  (callback_data.get('sender', {}) or {}).get('staffId') or
                                  (callback_data.get('sender', {}) or {}).get('dingtalkId'))
            if not open_conversation_id:
                open_conversation_id = (callback_data.get('openConversationId') or 
                                       callback_data.get('conversationId'))
        
        return sender_staff_id, open_conversation_id
    
    def _extract_name(self, content: str) -> Optional[str]:
        """从消息内容中提取姓名
        
        Args:
            content: 消息内容
            
        Returns:
            姓名或 None
        """
        if not content:
            return None
        
        # 移除多余的空格和换行
        name = content.strip()
        
        # 移除 @机器人的标识
        name = re.sub(r'@[^\s@]+', '', name).strip()
        name = re.sub(r'@.*$', '', name).strip()
        
        # 如果清理后还有内容，就认为是姓名
        if name:
            return name
        
        return None
    
    def _send_messages(
        self,
        sender_staff_id: Optional[str],
        open_conversation_id: Optional[str],
        is_group_message: bool,
        title: str,
        content: str
    ) -> bool:
        """统一发送私聊和群消息
        
        Args:
            sender_staff_id: 发送者 ID
            open_conversation_id: 会话 ID
            is_group_message: 是否群消息
            title: 消息标题
            content: 消息内容
            
        Returns:
            是否至少发送了一条消息
        """
        private_sent = False
        group_sent = False
        
        # 优先发送私聊消息
        if sender_staff_id:
            try:
                private_sent = self.message_service.send_private_markdown(
                    sender_staff_id, open_conversation_id, title, content
                )
                if not private_sent:
                    logger.warning(f"私聊消息发送失败: {title}")
            except Exception as e:
                logger.error(f"发送私聊消息异常: {e}", exc_info=True)
        
        # 如果是群消息，也发送群回复
        if is_group_message and open_conversation_id:
            try:
                group_sent = self.message_service.send_group_markdown(
                    open_conversation_id, title, content
                )
                if not group_sent:
                    logger.warning(f"群消息发送失败: {title}")
            except Exception as e:
                logger.error(f"发送群消息异常: {e}", exc_info=True)
        
        # 如果都没有发送成功，记录错误
        if not private_sent and not group_sent:
            logger.error(
                f"消息发送失败：私聊={private_sent}, 群聊={group_sent}, "
                f"sender_staff_id={sender_staff_id}, open_conversation_id={open_conversation_id}"
            )
        
        return private_sent or group_sent
    
    async def process(self, callback):
        """处理机器人接收到的消息
        
        Args:
            callback: 回调对象
            
        Returns:
            (状态码, 消息) 元组
        """
        incoming_message = None
        try:
            incoming_message = ChatbotMessage.from_dict(callback.data)
            
            # 检查消息类型
            is_group_message = self._is_group_message(incoming_message)
            if hasattr(callback, 'data') and isinstance(callback.data, dict):
                conversation_type = callback.data.get('conversationType')
                if conversation_type:
                    is_group_message = (conversation_type == 2 or str(conversation_type) == "2")
            
            # 检查消息内容
            if not hasattr(incoming_message, 'text') or not incoming_message.text:
                return AckMessage.STATUS_OK, 'OK'
            
            raw_content = incoming_message.text.content.strip() if hasattr(incoming_message.text, 'content') else ""
            
            # 获取发送者 ID 和会话 ID
            sender_staff_id, open_conversation_id = self._get_sender_info(incoming_message, callback.data)
            
            # 权限检查：只有管理员可以创建用户
            if not self._check_admin_permission(sender_staff_id):
                sender_name = self.user_service.get_user_name_by_id(sender_staff_id) if sender_staff_id else "未知用户"
                logger.warning(f"用户 {sender_name} ({sender_staff_id}) 尝试创建用户，但无权限")
                permission_denied_msg = MessageFormatter.format_permission_denied_message(self.admin_name)
                self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                   "权限不足", permission_denied_msg)
                return AckMessage.STATUS_OK, 'OK'
            
            # 如果消息为空，直接返回
            if not raw_content:
                self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                   "输入提示", "**请输入您的姓名**\n\n格式：`姓名@机器人`")
                return AckMessage.STATUS_OK, 'OK'
            
            # 清理消息内容，提取姓名
            name = self._extract_name(raw_content)
            
            if not name:
                reply_content = "**未识别到姓名**\n\n请按格式输入：`姓名@机器人`\n\n例如：`张三@机器人`"
                self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                   "格式错误", reply_content)
                return AckMessage.STATUS_OK, 'OK'
            
            # 根据姓名查找对应的钉钉用户 ID
            target_user_id = self.user_service.find_user_by_name(name)
            if not target_user_id:
                logger.warning(f"未找到姓名为 '{name}' 的钉钉用户")
                error_content = MessageFormatter.format_user_not_found_message(name)
                self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                   "用户查找失败", error_content)
                return AckMessage.STATUS_OK, 'OK'
            
            # 如果配置了卡片模板 ID，发送审批卡片；否则直接创建用户
            if self.settings.dingtalk_card_template_id:
                # 卡片发送给审批人，而不是新用户
                if not self.approver_userid:
                    logger.error("审批人 userid 未初始化，无法发送审批卡片")
                    self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                       "系统错误", "**系统错误**\n\n审批人信息未配置，无法发送审批卡片")
                    return AckMessage.STATUS_OK, 'OK'
                
                card_sent = self.card_service.send_approval_card(
                    name=name,
                    target_user_id=target_user_id,
                    sender_staff_id=sender_staff_id,
                    open_conversation_id=open_conversation_id,
                    is_group_message=is_group_message,
                    admin_name=self.admin_name,
                    approver_user_id=self.approver_userid
                )
                if not card_sent:
                    logger.error("发送审批卡片失败，回退到直接创建用户")
                    self._create_user_directly(name, target_user_id, open_conversation_id, is_group_message)
            else:
                logger.warning("未配置卡片模板 ID，使用直接创建用户方式")
                self._create_user_directly(name, target_user_id, open_conversation_id, is_group_message)
            
            return AckMessage.STATUS_OK, 'OK'
            
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}", exc_info=True)
            try:
                if incoming_message:
                    sender_staff_id, open_conversation_id = self._get_sender_info(incoming_message)
                    is_group = self._is_group_message(incoming_message)
                    error_msg = f"**处理消息时发生错误**\n\n`{str(e)}`"
                    self._send_messages(sender_staff_id, open_conversation_id, is_group, "系统错误", error_msg)
            except Exception as reply_error:
                logger.error(f"回复错误消息时也发生错误: {reply_error}", exc_info=True)
            return AckMessage.STATUS_OK, 'OK'
    
    def _create_user_directly(
        self,
        name: str,
        target_user_id: str,
        open_conversation_id: Optional[str],
        is_group_message: bool
    ):
        """直接创建用户（不通过卡片审批）
        
        Args:
            name: 用户姓名
            target_user_id: 目标用户 ID
            open_conversation_id: 会话 ID
            is_group_message: 是否群消息
        """
        ok, username, password, error_msg = self.synology_service.create_user_from_name(name)
        
        if ok:
            reply_content = MessageFormatter.format_success_message(name, username, password)
            # 发送消息给目标用户
            self.message_service.send_private_markdown(target_user_id, None, "帐户开通完成通知", reply_content)
            # 如果是群消息，同时发送群回复
            if is_group_message and open_conversation_id:
                group_reply = MessageFormatter.format_group_success_message(name)
                self.message_service.send_group_markdown(open_conversation_id, "帐户开通完成通知", group_reply)
        else:
            # 检查是否是用户已存在的错误
            if "已存在" in error_msg:
                reply_content = MessageFormatter.format_user_exists_message(name, error_msg)
                group_reply = MessageFormatter.format_group_user_exists_message(name) if is_group_message else None
            else:
                reply_content = MessageFormatter.format_error_message(error_msg)
                group_reply = MessageFormatter.format_group_error_message(name, error_msg) if is_group_message else None
            
            self.message_service.send_private_markdown(target_user_id, None, "帐户开通失败通知", reply_content)
            if is_group_message and open_conversation_id and group_reply:
                self.message_service.send_group_markdown(open_conversation_id, "帐户开通失败通知", group_reply)

