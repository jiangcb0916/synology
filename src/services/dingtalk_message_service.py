#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉消息服务
负责发送各种类型的钉钉消息
"""
import logging
import json
import requests
from typing import Optional, List, Tuple

from .dingtalk_api_service import DingTalkAPIService
from ..config import Settings

logger = logging.getLogger(__name__)


class DingTalkMessageService:
    """钉钉消息服务"""
    
    def __init__(self, api_service: DingTalkAPIService, settings: Settings):
        """初始化服务
        
        Args:
            api_service: 钉钉 API 服务
            settings: 配置对象
        """
        self.api_service = api_service
        self.settings = settings
        self.client_id = settings.dingtalk_client_id
    
    def send_private_markdown(
        self,
        receiver_staff_id: str,
        open_conversation_id: Optional[str],
        title: str,
        markdown_content: str
    ) -> bool:
        """发送私聊 Markdown 消息
        
        Args:
            receiver_staff_id: 接收者用户 ID
            open_conversation_id: 会话 ID（可选）
            title: 消息标题
            markdown_content: Markdown 内容
            
        Returns:
            是否发送成功
        """
        access_token = self.api_service.get_access_token()
        if not access_token:
            return False
        
        # 优先使用批量发送接口
        if receiver_staff_id:
            result = self._send_private_batch(
                [receiver_staff_id],
                title,
                markdown_content,
                "sampleMarkdown"
            )
            if result:
                return True
        
        # 如果批量发送失败且没有 openConversationId，无法使用单聊接口
        if not open_conversation_id:
            return False
        
        # 使用单聊接口
        url = "https://api.dingtalk.com/v1.0/robot/privateChatMessages/send"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": access_token
        }
        payload = {
            "robotCode": self.client_id,
            "openConversationId": open_conversation_id,
            "msgKey": "sampleMarkdown",
            "msgParam": json.dumps({"title": title, "text": markdown_content}, ensure_ascii=False)
        }
        
        success, error = self._send_api_request(url, headers, payload)
        if not success and error:
            # 如果失败，尝试批量发送
            return self._send_private_batch([receiver_staff_id], title, markdown_content, "sampleMarkdown")
        return success
    
    def send_group_markdown(
        self,
        open_conversation_id: str,
        title: str,
        markdown_content: str
    ) -> bool:
        """发送群聊 Markdown 消息
        
        Args:
            open_conversation_id: 会话 ID
            title: 消息标题
            markdown_content: Markdown 内容
            
        Returns:
            是否发送成功
        """
        access_token = self.api_service.get_access_token()
        if not access_token:
            return False
        
        url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": access_token
        }
        payload = {
            "robotCode": self.client_id,
            "openConversationId": open_conversation_id,
            "msgKey": "sampleMarkdown",
            "msgParam": json.dumps({"title": title, "text": markdown_content}, ensure_ascii=False)
        }
        
        success, error = self._send_api_request(url, headers, payload)
        if not success and error:
            error_code, error_msg, status_code = error
            if error_msg:
                logger.error(f"发送群消息失败: {error_msg}, code: {error_code}")
        return success
    
    def _send_private_batch(
        self,
        user_ids: List[str],
        title_or_content: str,
        content_or_none: Optional[str],
        msg_key: str
    ) -> bool:
        """统一的批量发送接口
        
        Args:
            user_ids: 用户 ID 列表
            title_or_content: 标题或内容
            content_or_none: 内容（可选）
            msg_key: 消息类型
            
        Returns:
            是否发送成功
        """
        access_token = self.api_service.get_access_token()
        if not access_token:
            return False
        
        url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
        headers = {
            "Content-Type": "application/json",
            "x-acs-dingtalk-access-token": access_token
        }
        
        if msg_key == "sampleMarkdown":
            msg_param = {"title": title_or_content, "text": content_or_none}
        else:
            msg_param = {"content": title_or_content}
        
        payload = {
            "robotCode": self.client_id,
            "userIds": user_ids,
            "msgKey": msg_key,
            "msgParam": json.dumps(msg_param, ensure_ascii=False)
        }
        
        success, error = self._send_api_request(url, headers, payload)
        if not success and error:
            error_code, error_msg, status_code = error
            # 如果是参数错误，尝试使用文本格式
            if status_code == 400 or (error_msg and ("参数" in error_msg or "invalid" in str(error_code).lower())):
                if msg_key == "sampleMarkdown" and content_or_none:
                    clean_text = (title_or_content + "\n\n" + content_or_none).replace(
                        "**", ""
                    ).replace("### ", "").replace("## ", "").replace("# ", "")
                    return self._send_private_batch(user_ids, clean_text, None, "sampleText")
        return success
    
    def _send_api_request(
        self,
        url: str,
        headers: dict,
        payload: dict
    ) -> Tuple[bool, Optional[Tuple]]:
        """统一的 API 请求发送方法
        
        Args:
            url: API URL
            headers: 请求头
            payload: 请求体
            
        Returns:
            (是否成功, 错误信息) 元组
        """
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json() if response.status_code == 200 else {}
            
            if response.status_code == 200:
                if (result.get("errcode") == 0 or 
                    result.get("success") == True or 
                    result.get("processQueryKey") is not None or
                    (not result.get("code") and not result.get("errcode"))):
                    return True, None
            
            error_code = result.get("code") or result.get("errcode")
            error_msg = result.get("message") or result.get("errmsg")
            return False, (error_code, error_msg, response.status_code)
        except Exception as e:
            logger.error(f"API 请求异常: {e}", exc_info=True)
            return False, (None, str(e), None)

