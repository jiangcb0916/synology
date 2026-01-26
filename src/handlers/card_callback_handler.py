#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉卡片回调处理器
负责处理用户点击卡片按钮的事件
"""
import logging
import json
from typing import Dict, Optional

from dingtalk_stream.card_callback import CardCallbackMessage

from ..core import SynologyService
from ..services import DingTalkUserService, DingTalkMessageService, DingTalkCardService
from ..utils import MessageFormatter
from ..config import Settings

logger = logging.getLogger(__name__)


class CardCallbackHandler:
    """卡片回调处理器"""
    
    def __init__(
        self,
        settings: Settings,
        synology_service: SynologyService,
        user_service: DingTalkUserService,
        message_service: DingTalkMessageService,
        card_service: DingTalkCardService,
        admin_name: str,
        admin_userid: Optional[str]
    ):
        """初始化处理器
        
        Args:
            settings: 配置对象
            synology_service: Synology 服务
            user_service: 钉钉用户服务
            message_service: 钉钉消息服务
            card_service: 钉钉卡片服务
            admin_name: 管理员姓名
            admin_userid: 管理员用户 ID
        """
        self.settings = settings
        self.synology_service = synology_service
        self.user_service = user_service
        self.message_service = message_service
        self.card_service = card_service
        self.admin_name = admin_name
        self.admin_userid = admin_userid
    
    def pre_start(self):
        """预启动方法，SDK 要求所有处理器必须实现此方法"""
        pass
    
    def _check_admin_permission(self, user_id: str) -> bool:
        """检查用户是否有管理员权限
        
        Args:
            user_id: 用户 ID
            
        Returns:
            是否有管理员权限
        """
        if not self.admin_userid:
            logger.warning("管理员 userid 未初始化，拒绝所有请求")
            return False
        
        if not user_id:
            return False
        
        # 比较 userid
        if user_id == self.admin_userid:
            return True
        
        # 如果 userid 不匹配，尝试获取用户姓名进行二次验证
        user_name = self.user_service.get_user_name_by_id(user_id)
        if user_name and user_name.strip() == self.admin_name.strip():
            return True
        
        return False
    
    async def raw_process(self, callback):
        """处理原始回调数据
        
        Args:
            callback: 回调对象
            
        Returns:
            处理结果字典
        """
        try:
            # 如果已经是 CardCallbackMessage 对象，直接处理
            if isinstance(callback, CardCallbackMessage):
                return await self.process(callback)
            
            # 如果是字典，直接处理
            if isinstance(callback, dict):
                return await self.process(callback)
            
            # 如果是 CardCallbackMessage 对象，尝试获取 data 属性
            if hasattr(callback, 'data'):
                return await self.process(callback.data if isinstance(callback.data, dict) else callback)
            
            # 其他情况，直接处理
            return await self.process(callback)
        except Exception as e:
            logger.error(f"处理卡片回调原始数据时发生错误: {e}", exc_info=True)
            return {"status": "FAIL", "message": str(e)}
    
    async def process(self, callback) -> Dict:
        """处理卡片回调事件
        
        Args:
            callback: 回调对象
            
        Returns:
            处理结果字典
        """
        try:
            # 解析卡片回调消息
            callback_data = self._parse_callback_data(callback)
            
            # 获取 out_track_id（卡片的唯一标识）
            out_track_id = callback_data.get('outTrackId') or callback_data.get('out_track_id')
            if not out_track_id:
                logger.error("无法获取 out_track_id")
                return {"status": "FAIL"}
            
            # 获取按钮点击信息
            content = callback_data.get('content', {})
            content_dict = self._parse_content(content)
            
            # 从 content 中提取 cardPrivateData
            card_private_data = content_dict.get('cardPrivateData', {}) if isinstance(content_dict, dict) else {}
            params = card_private_data.get('params', {}) if isinstance(card_private_data, dict) else {}
            
            # 获取用户操作
            user_action = self._extract_user_action(params, card_private_data, content_dict, callback_data)
            
            # 获取操作者信息
            operator_user_id = self._extract_operator_user_id(callback_data)
            
            # 查找对应的待审批卡片信息
            card_info = self.card_service.get_pending_card(out_track_id)
            if not card_info:
                logger.warning(f"未找到对应的卡片信息: {out_track_id}")
                return {"status": "FAIL", "message": "未找到对应的卡片信息"}
            
            name = card_info.get('name')
            target_user_id = card_info.get('target_user_id')
            sender_staff_id = card_info.get('sender_staff_id')
            open_conversation_id = card_info.get('open_conversation_id')
            is_group_message = card_info.get('is_group_message', False)
            
            # 权限检查：只有管理员可以审批
            if not self._check_admin_permission(operator_user_id):
                operator_name = self.user_service.get_user_name_by_id(operator_user_id) if operator_user_id else "未知用户"
                logger.warning(f"用户 {operator_name} ({operator_user_id}) 尝试审批，但无权限")
                
                # 发送权限不足消息给操作者
                permission_denied_msg = (
                    "### ⚠️ 权限不足\n\n"
                    "**微爱基金会 · 共享盘系统**\n\n"
                    "---\n\n"
                    "**抱歉，您没有权限进行审批操作**\n\n"
                    f"只有管理员 **{self.admin_name}** 可以审批账户创建请求。\n\n"
                    "📧 如需审批，请联系管理员"
                )
                if operator_user_id:
                    self.message_service.send_private_markdown(operator_user_id, None, "权限不足", permission_denied_msg)
                
                return {"status": "FAIL", "message": "权限不足"}
            
            # 判断用户操作
            if user_action in ['approve', '同意', 'agree', 'confirm', 'accept', '通过']:
                return await self._handle_approve(
                    name, target_user_id, sender_staff_id, 
                    open_conversation_id, is_group_message, out_track_id
                )
            elif user_action in ['reject', '拒绝', 'deny', 'cancel']:
                return await self._handle_reject(
                    name, target_user_id, out_track_id
                )
            else:
                logger.warning(f"未知的操作类型: {user_action}")
                return {"status": "FAIL", "message": f"未知的操作类型: {user_action}"}
                
        except Exception as e:
            logger.error(f"处理卡片回调时发生错误: {e}", exc_info=True)
            return {"status": "FAIL", "message": str(e)}
    
    def _parse_callback_data(self, callback) -> Dict:
        """解析回调数据
        
        Args:
            callback: 回调对象
            
        Returns:
            回调数据字典
        """
        if isinstance(callback, dict):
            return callback
        elif isinstance(callback, CardCallbackMessage):
            if hasattr(callback, 'data') and isinstance(callback.data, dict):
                return callback.data
            elif hasattr(callback, 'to_dict') and callable(getattr(callback, 'to_dict', None)):
                try:
                    return callback.to_dict()
                except (AttributeError, TypeError):
                    return callback.__dict__ if hasattr(callback, '__dict__') else {}
            else:
                return callback.__dict__ if hasattr(callback, '__dict__') else {}
        elif hasattr(callback, 'data'):
            data = callback.data
            return data if isinstance(data, dict) else {}
        else:
            return {}
    
    def _parse_content(self, content) -> Dict:
        """解析 content 字段
        
        Args:
            content: content 字段
            
        Returns:
            解析后的字典
        """
        if isinstance(content, str):
            try:
                return json.loads(content)
            except Exception:
                return {}
        elif isinstance(content, dict):
            return content
        else:
            return {}
    
    def _extract_user_action(self, params: Dict, card_private_data: Dict, content_dict: Dict, callback_data: Dict) -> Optional[str]:
        """提取用户操作
        
        Args:
            params: 参数字典
            card_private_data: 卡片私有数据
            content_dict: 内容字典
            callback_data: 回调数据
            
        Returns:
            用户操作或 None
        """
        return (
            params.get('action') or
            card_private_data.get('action') if isinstance(card_private_data, dict) else None or
            content_dict.get('action') if isinstance(content_dict, dict) else None or
            callback_data.get('action') or
            callback_data.get('actionValue')
        )
    
    def _extract_operator_user_id(self, callback_data: Dict) -> Optional[str]:
        """提取操作者用户 ID
        
        Args:
            callback_data: 回调数据
            
        Returns:
            操作者用户 ID 或 None
        """
        operator_user_id = callback_data.get('userId')
        if not operator_user_id:
            operator = callback_data.get('operator') or {}
            if isinstance(operator, dict):
                operator_user_id = operator.get('userId') or operator.get('userid') or operator.get('dingtalkId')
            elif isinstance(operator, str):
                operator_user_id = operator
        return operator_user_id
    
    async def _handle_approve(
        self,
        name: str,
        target_user_id: str,
        sender_staff_id: str,
        open_conversation_id: Optional[str],
        is_group_message: bool,
        out_track_id: str
    ) -> Dict:
        """处理审批通过
        
        Args:
            name: 用户姓名
            target_user_id: 目标用户 ID
            sender_staff_id: 发送者 ID
            open_conversation_id: 会话 ID
            is_group_message: 是否群消息
            out_track_id: 卡片追踪 ID
            
        Returns:
            处理结果字典
        """
        # 创建用户
        ok, username, password, error_msg = self.synology_service.create_user_from_name(name)
        
        if ok:
            # 创建成功
            reply_content = MessageFormatter.format_success_message(name, username, password)
            self.message_service.send_private_markdown(target_user_id, None, "帐户开通完成通知", reply_content)
            
            # 如果是群消息，同时发送群回复
            if is_group_message and open_conversation_id:
                group_reply = MessageFormatter.format_group_success_message(name)
                self.message_service.send_group_markdown(open_conversation_id, "帐户开通完成通知", group_reply)
            
            # 通知管理员
            if sender_staff_id:
                admin_notice = (
                    f"### ✅ 账户创建审批已通过\n\n"
                    f"**用户 {name} 的账户创建审批已通过**\n\n"
                    f"账户信息已发送给用户"
                )
                self.message_service.send_private_markdown(sender_staff_id, None, "审批结果通知", admin_notice)
            
            # 从待审批列表中移除
            self.card_service.remove_pending_card(out_track_id)
            
            return {"status": "SUCCESS"}
        else:
            # 创建失败
            logger.error(f"创建用户失败: {error_msg}")
            
            # 发送失败消息
            if "已存在" in error_msg:
                reply_content = MessageFormatter.format_user_exists_message(name, error_msg)
            else:
                reply_content = MessageFormatter.format_error_message(error_msg)
            
            self.message_service.send_private_markdown(target_user_id, None, "帐户开通失败通知", reply_content)
            
            # 通知管理员
            if sender_staff_id:
                admin_notice = (
                    f"### ❌ 账户创建失败\n\n"
                    f"**用户 {name} 的账户创建失败**\n\n"
                    f"错误信息：{error_msg}"
                )
                self.message_service.send_private_markdown(sender_staff_id, None, "审批结果通知", admin_notice)
            
            # 从待审批列表中移除
            self.card_service.remove_pending_card(out_track_id)
            
            return {"status": "FAIL", "message": error_msg}
    
    async def _handle_reject(
        self,
        name: str,
        target_user_id: str,
        out_track_id: str
    ) -> Dict:
        """处理审批拒绝
        
        Args:
            name: 用户姓名
            target_user_id: 目标用户 ID
            out_track_id: 卡片追踪 ID
            
        Returns:
            处理结果字典
        """
        # 只发送拒绝通知给目标用户
        reject_content = MessageFormatter.format_approval_reject_message(name)
        self.message_service.send_private_markdown(target_user_id, None, "审批结果通知", reject_content)
        
        # 从待审批列表中移除
        self.card_service.remove_pending_card(out_track_id)
        
        return {"status": "SUCCESS"}

