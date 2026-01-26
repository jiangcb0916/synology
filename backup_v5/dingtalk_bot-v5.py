#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 版本：5.0.0
# 作者：jiangcb
# 日期：2026-01-22
# 描述：钉钉机器人自动回复消息处理器，可以根据姓名创建Synology用户，并同时发送私聊消息给用户和群聊回调信息
# 应用权限：访问通信录
# 权限：只有管理员拥有访问权限（管理员姓名从config.ini配置文件中读取）
# 优化：支持钉钉卡片审批流程
# 卡片审批流程：
# 1. 用户点击卡片按钮，触发卡片审批流程
# 2. 卡片审批流程中，用户可以点击同意按钮，触发用户创建流程
# 3. 卡片审批流程中，用户可以点击拒绝按钮，触发用户创建失败流程
# 4. 相关配置从config.ini配置文件中读取：管理员姓名、卡片模板ID、钉钉机器人client_id、钉钉机器人client_secret
import configparser
import logging
import re
import requests
import json
import time
import asyncio
from typing import Any, Dict
from datetime import datetime
from dingtalk_stream import DingTalkStreamClient, Credential
from dingtalk_stream.chatbot import ChatbotMessage, ChatbotHandler, AckMessage
from dingtalk_stream.card_callback import CardCallbackMessage, Card_Callback_Router_Topic
from alibabacloud_dingtalk.card_1_0.client import Client as dingtalkcard_1_0Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.card_1_0 import models as dingtalkcard__1__0_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from synology_client import SynologyUserCLI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 设置dingtalk-stream的日志级别为WARNING，减少无用日志
logging.getLogger('dingtalk_stream').setLevel(logging.WARNING)


def convert_json_values_to_string(obj: Dict[str, Any]) -> Dict[str, str]:
    """
    由于接口要求卡片数据的键值对均为 string 类型，需要对卡片数据进行预处理
    
    Args:
        obj: 包含任意类型值的字典
        
    Returns:
        所有值都转换为字符串的字典
    """
    result = {}
    for key, value in obj.items():
        if isinstance(value, str):
            result[key] = value
        else:
            try:
                # 将非字符串值转换为 JSON 字符串
                result[key] = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                # 如果转换失败，使用空字符串
                result[key] = ""
    return result


class UserBotHandler(ChatbotHandler):
    """钉钉机器人消息处理器"""
    
    def __init__(self, synology_client, client_id, client_secret, card_template_id=None, admin_name="蒋成博"):
        super(UserBotHandler, self).__init__()
        self.synology_client = synology_client
        self.client_id = client_id
        self.client_secret = client_secret
        self.card_template_id = card_template_id
        self._access_token = None
        self._token_expire_time = 0
        # 管理员姓名（从配置文件读取）
        self.admin_name = admin_name
        # 管理员 userid（在初始化时查找）
        self.admin_userid = None
        # 存储待审批的卡片信息：out_track_id -> {name, target_user_id, sender_staff_id, open_conversation_id, is_group_message}
        self.pending_cards = {}
        self._init_admin_userid()
    
    def _is_group_message(self, message):
        """检查是否是群消息"""
        if hasattr(message, 'conversationType'):
            conversation_type = message.conversationType
            return conversation_type == 2 or str(conversation_type) == "2"
        return False
    
    def _get_conversation_id(self, message):
        """获取会话ID"""
        if hasattr(message, 'openConversationId'):
            return message.openConversationId
        elif hasattr(message, 'conversationId'):
            return message.conversationId
        return None
    
    def _init_admin_userid(self):
        """初始化管理员 userid"""
        try:
            self.admin_userid = self.find_user_by_name(self.admin_name)
            if self.admin_userid:
                logger.info(f"管理员 {self.admin_name} 的 userid: {self.admin_userid}")
            else:
                logger.warning(f"未找到管理员用户: {self.admin_name}，权限检查将失效")
        except Exception as e:
            logger.error(f"初始化管理员 userid 失败: {e}", exc_info=True)
    
    def _check_admin_permission(self, sender_staff_id):
        """检查发送者是否有管理员权限"""
        if not self.admin_userid:
            logger.warning("管理员 userid 未初始化，拒绝所有请求")
            return False
        
        if not sender_staff_id:
            return False
        
        # 比较 userid
        if sender_staff_id == self.admin_userid:
            return True
        
        # 如果 userid 不匹配，尝试获取发送者姓名进行二次验证
        sender_name = self.get_user_name_by_id(sender_staff_id)
        if sender_name and sender_name.strip() == self.admin_name.strip():
            return True
        
        return False
    
    def get_user_name_by_id(self, user_id):
        """根据钉钉用户ID获取用户姓名"""
        access_token = self._get_access_token()
        if not access_token:
            logger.error("无法获取access_token，无法查找用户")
            return None
        
        try:
            # 使用钉钉API获取用户信息
            url = "https://oapi.dingtalk.com/topapi/v2/user/get"
            params = {
                "access_token": access_token
            }
            
            payload = {
                "userid": user_id
            }
            
            response = requests.post(url, params=params, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") == 0:
                user_info = result.get("result", {})
                name = user_info.get("name", "")
                if name:
                    return name
            else:
                logger.error(f"获取用户信息失败: {result.get('errmsg')}")
        except Exception as e:
            logger.error(f"通过钉钉ID获取用户姓名异常: {e}", exc_info=True)
        
        return None
    
    def _get_sender_info(self, incoming_message, callback_data=None):
        """提取发送者ID和会话ID"""
        sender_staff_id = None
        open_conversation_id = None
        
        # 获取发送者ID
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
        
        # 获取会话ID
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
    
    def reply_markdown(self, title, markdown_content, incoming_message):
        """回复群消息（Markdown格式）"""
        if self._is_group_message(incoming_message):
            open_conversation_id = self._get_conversation_id(incoming_message)
            if open_conversation_id:
                return self.send_group_markdown(open_conversation_id, title, markdown_content)
        return super().reply_markdown(title, markdown_content, incoming_message)
    
    def reply_text(self, text_content, incoming_message):
        """回复群消息（文本格式，转换为Markdown）"""
        if self._is_group_message(incoming_message):
            open_conversation_id = self._get_conversation_id(incoming_message)
            if open_conversation_id:
                markdown_content = text_content.replace('\n', '\n\n')
                return self.send_group_markdown(open_conversation_id, "通知", markdown_content)
        return super().reply_text(text_content, incoming_message)
    
    def _send_messages(self, sender_staff_id, open_conversation_id, is_group_message, title, content):
        """统一发送私聊和群消息，确保至少发送一条消息"""
        private_sent = False
        group_sent = False
        
        # 优先发送私聊消息
        if sender_staff_id:
            try:
                private_sent = self.send_private_markdown(sender_staff_id, open_conversation_id, title, content)
                if not private_sent:
                    logger.warning(f"私聊消息发送失败: {title}")
            except Exception as e:
                logger.error(f"发送私聊消息异常: {e}", exc_info=True)
        
        # 如果是群消息，也发送群回复
        if is_group_message and open_conversation_id:
            try:
                group_sent = self.send_group_markdown(open_conversation_id, title, content)
                if not group_sent:
                    logger.warning(f"群消息发送失败: {title}")
            except Exception as e:
                logger.error(f"发送群消息异常: {e}", exc_info=True)
        
        # 如果都没有发送成功，记录错误
        if not private_sent and not group_sent:
            logger.error(f"消息发送失败：私聊={private_sent}, 群聊={group_sent}, sender_staff_id={sender_staff_id}, open_conversation_id={open_conversation_id}")
        
        return private_sent or group_sent
    
    async def process(self, callback):
        """处理机器人接收到的消息"""
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
            
            # 获取发送者ID和会话ID
            sender_staff_id, open_conversation_id = self._get_sender_info(incoming_message, callback.data)
            
            # 权限检查：只有管理员可以创建用户
            if not self._check_admin_permission(sender_staff_id):
                sender_name = self.get_user_name_by_id(sender_staff_id) if sender_staff_id else "未知用户"
                logger.warning(f"用户 {sender_name} ({sender_staff_id}) 尝试创建用户，但无权限")
                permission_denied_msg = (
                    "### ⚠️ 权限不足\n\n"
                    "**微爱基金会 · 共享盘系统**\n\n"
                    "---\n\n"
                    "**抱歉，您没有权限使用此功能**\n\n"
                    f"只有管理员 **{self.admin_name}** 可以使用此机器人创建用户账户。\n\n"
                    "📧 如需创建用户账户，请联系管理员"
                )
                self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                   "权限不足", permission_denied_msg)
                return AckMessage.STATUS_OK, 'OK'
            
            # 如果消息为空，直接返回
            if not raw_content:
                self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                   "输入提示", "**请输入您的姓名**\n\n格式：`姓名@机器人`")
                return AckMessage.STATUS_OK, 'OK'
            
            # 清理消息内容，移除@机器人的标识和多余空格
            name = self._extract_name(raw_content)
            
            if not name:
                reply_content = "**未识别到姓名**\n\n请按格式输入：`姓名@机器人`\n\n例如：`张三@机器人`"
                self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                   "格式错误", reply_content)
                return AckMessage.STATUS_OK, 'OK'
            
            # 根据姓名查找对应的钉钉用户ID
            target_user_id = self.find_user_by_name(name)
            if not target_user_id:
                logger.warning(f"未找到姓名为 '{name}' 的钉钉用户")
                error_content = (
                    "### ❌ 用户查找失败\n\n"
                    "**微爱基金会 · 共享盘系统**\n\n"
                    "---\n\n"
                    f"**未找到用户**\n\n"
                    f"未找到姓名为 **'{name}'** 的钉钉用户，请确认姓名是否正确。\n\n"
                    "**可能的原因：**\n"
                    "1. 姓名输入错误\n"
                    "2. 该用户不在钉钉组织内\n"
                    "3. 该用户已离职或未激活\n\n"
                    "账户创建请求已取消。\n\n"
                    "📧 如有疑问，请联系系统管理员"
                )
                send_result = self._send_messages(sender_staff_id, open_conversation_id, is_group_message, 
                                                 "用户查找失败", error_content)
                return AckMessage.STATUS_OK, 'OK'
            
            # 如果配置了卡片模板ID，发送审批卡片；否则直接创建用户
            if self.card_template_id:
                # 发送审批卡片
                card_sent = self.send_approval_card(
                    name=name,
                    target_user_id=target_user_id,
                    sender_staff_id=sender_staff_id,
                    open_conversation_id=open_conversation_id,
                    is_group_message=is_group_message
                )
                if not card_sent:
                    logger.error(f"发送审批卡片失败，回退到直接创建用户")
                    # 如果卡片发送失败，回退到直接创建用户
                    self._create_user_directly(name, target_user_id, open_conversation_id, is_group_message)
            else:
                logger.warning("未配置卡片模板ID，使用直接创建用户方式")
                # 如果没有配置卡片模板，直接创建用户
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
    
    def _get_access_token(self):
        """获取钉钉访问令牌"""
        import time
        current_time = time.time()
        
        # 如果token未过期，直接返回
        if self._access_token and current_time < self._token_expire_time:
            return self._access_token
        
        # 获取新的access_token
        url = "https://oapi.dingtalk.com/gettoken"
        params = {
            "appkey": self.client_id,
            "appsecret": self.client_secret
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("errcode") == 0:
                self._access_token = data.get("access_token")
                # token有效期通常是7200秒，提前5分钟刷新
                self._token_expire_time = current_time + 7200 - 300
                return self._access_token
            else:
                logger.error(f"获取access_token失败: {data.get('errmsg')}")
                return None
        except Exception as e:
            logger.error(f"获取access_token异常: {e}", exc_info=True)
            return None
    
    def find_user_by_name(self, name):
        """根据姓名查找钉钉用户ID"""
        access_token = self._get_access_token()
        if not access_token:
            logger.error("无法获取access_token，无法查找用户")
            return None
        
        # 先尝试使用搜索API（更高效）
        userid = self._search_user_by_name(name, access_token)
        if userid:
            return userid
        
        # 如果搜索失败，尝试遍历所有部门
        userid = self._find_user_by_department(name, access_token)
        if userid:
            return userid
        
        # 最后尝试旧版API
        userid = self._find_user_by_name_old_api(name, access_token)
        if userid:
            return userid
        
        logger.warning(f"未找到姓名为 '{name}' 的用户")
        return None
    
    def _search_user_by_name(self, name, access_token):
        """使用搜索API查找用户"""
        try:
            url = "https://oapi.dingtalk.com/topapi/smartwork/hrm/employee/queryonjob"
            response = requests.post(url, params={"access_token": access_token},
                                   json={"status_list": [2, 3, 5], "offset": 0, "size": 100},
                                   timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") == 0:
                for user in result.get("result", {}).get("data_list", []):
                    if user.get("name", "").strip() == name.strip():
                        return user.get("userid")
        except Exception:
            pass
        return None
    
    def _find_user_by_department(self, name, access_token):
        """通过遍历部门查找用户"""
        try:
            # 先获取根部门列表
            dept_list = self._get_department_list(access_token)
            if not dept_list:
                logger.warning("无法获取部门列表")
                return None
            
            # 遍历所有部门查找用户
            for dept_id in dept_list:
                userid = self._get_users_in_department(dept_id, name, access_token)
                if userid:
                    return userid
        except Exception as e:
            logger.error(f"通过部门查找用户异常: {e}", exc_info=True)
        
        return None
    
    def _get_department_list(self, access_token):
        """获取所有部门ID列表"""
        try:
            url = "https://oapi.dingtalk.com/topapi/v2/department/listsub"
            params = {
                "access_token": access_token
            }
            
            dept_list = [1]  # 从根部门开始
            
            # 递归获取所有子部门
            def get_sub_depts(dept_id):
                payload = {
                    "dept_id": dept_id
                }
                try:
                    response = requests.post(url, params=params, json=payload, timeout=10)
                    response.raise_for_status()
                    result = response.json()
                    if result.get("errcode") == 0:
                        sub_depts = result.get("result", [])
                        for dept in sub_depts:
                            sub_dept_id = dept.get("dept_id")
                            if sub_dept_id and sub_dept_id not in dept_list:
                                dept_list.append(sub_dept_id)
                                get_sub_depts(sub_dept_id)  # 递归获取子部门
                except:
                    pass
            
            get_sub_depts(1)
            return dept_list
        except Exception as e:
            logger.error(f"获取部门列表失败: {e}", exc_info=True)
            return [1]  # 至少返回根部门
    
    def _get_users_in_department(self, dept_id, target_name, access_token):
        """获取指定部门中的用户"""
        try:
            url = "https://oapi.dingtalk.com/topapi/v2/user/list"
            params = {"access_token": access_token}
            cursor = 0
            page_size = 100
            
            while True:
                response = requests.post(url, params=params, 
                                       json={"dept_id": dept_id, "cursor": cursor, "size": page_size}, 
                                       timeout=10)
                response.raise_for_status()
                result = response.json()
                
                if result.get("errcode") != 0:
                    break
                
                user_list = result.get("result", {}).get("list", [])
                if not user_list:
                    break
                
                # 在用户列表中查找匹配的姓名
                for user in user_list:
                    user_name = user.get("name", "").strip()
                    if user_name == target_name.strip():
                        return user.get("userid")
                
                if not result.get("result", {}).get("has_more", False):
                    break
                cursor += page_size
        except Exception:
            pass
        return None
    
    def _find_user_by_name_old_api(self, name, access_token):
        """使用旧版API根据姓名查找用户（备用方法）"""
        try:
            url = "https://oapi.dingtalk.com/topapi/user/listbypage"
            params = {"access_token": access_token}
            page_size = 100
            offset = 0
            
            while True:
                response = requests.post(url, params=params,
                                       json={"department_id": 1, "offset": offset, "size": page_size},
                                       timeout=10)
                response.raise_for_status()
                result = response.json()
                
                if result.get("errcode") != 0:
                    logger.error(f"旧版API查询用户列表失败: {result.get('errmsg')}")
                    return None
                
                user_list = result.get("result", {}).get("list", [])
                if not user_list:
                    break
                
                for user in user_list:
                    user_name = user.get("name", "").strip()
                    if user_name == name.strip():
                        return user.get("userid")
                
                if not result.get("result", {}).get("has_more", False):
                    break
                offset += page_size
        except Exception as e:
            logger.error(f"旧版API查找用户异常: {e}", exc_info=True)
        return None
    
    def _send_api_request(self, url, headers, payload, msg_type="Markdown"):
        """统一的API请求发送方法"""
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json() if response.status_code == 200 else {}
            
            if response.status_code == 200:
                if (result.get("errcode") == 0 or result.get("success") == True or 
                    result.get("processQueryKey") is not None or
                    (not result.get("code") and not result.get("errcode"))):
                    return True, None
            
            error_code = result.get("code") or result.get("errcode")
            error_msg = result.get("message") or result.get("errmsg")
            return False, (error_code, error_msg, response.status_code)
        except Exception as e:
            return False, (None, str(e), None)
    
    def send_private_markdown(self, receiver_staff_id, open_conversation_id, title, markdown_content):
        """发送私聊Markdown消息给指定用户"""
        access_token = self._get_access_token()
        if not access_token:
            return False
        
        # 优先使用批量发送接口（更可靠）
        if receiver_staff_id:
            result = self._send_private_batch([receiver_staff_id], title, markdown_content, "sampleMarkdown")
            if result:
                return True
        
        # 如果批量发送失败且没有openConversationId，无法使用单聊接口
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
    
    def _send_private_batch(self, user_ids, title_or_content, content_or_none, msg_key):
        """统一的批量发送接口"""
        access_token = self._get_access_token()
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
                if msg_key == "sampleMarkdown":
                    clean_text = (title_or_content + "\n\n" + content_or_none).replace("**", "").replace("### ", "").replace("## ", "").replace("# ", "")
                    return self._send_private_batch(user_ids, clean_text, None, "sampleText")
        return success
    
    def send_group_markdown(self, open_conversation_id, title, markdown_content):
        """发送群聊Markdown消息"""
        access_token = self._get_access_token()
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
    
    def _extract_name(self, content):
        """从消息内容中提取姓名"""
        if not content:
            return None
        
        # 移除多余的空格和换行
        name = content.strip()
        
        # 移除@机器人的标识（可能包含机器人的名称或ID）
        # 匹配 @机器人名 或 @机器人ID 等格式
        name = re.sub(r'@[^\s@]+', '', name).strip()
        name = re.sub(r'@.*$', '', name).strip()
        
        # 如果清理后还有内容，就认为是姓名
        if name:
            return name
        
        return None
    
    def _format_success_message(self, name, username, password):
        """格式化成功消息（钉钉 Markdown）"""
        mac_script_link = "https://qr.dingtalk.com/page/yunpan?route=previewDentry&spaceId=441584833&fileId=208808669078&type=file"
        windows_script_link = "https://qr.dingtalk.com/page/yunpan?route=previewDentry&spaceId=441584833&fileId=208825411677&type=file"
        return (
            "### ✅ 帐户开通完成通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            "#### 🎉 用户帐户已成功创建\n\n"
            f"**姓名**：{name}\n\n"
            "**登录账户信息**：\n\n"
            f"**用户名**：{username}\n\n"
            f"**密码**：{password}\n\n"
            "---\n\n"
            "#### 📥 共享盘挂载脚本\n\n"
            "**请根据您的操作系统下载对应的脚本：**\n\n"
            "**🍎 macOS 系统：**\n"
            f"- [点击下载 macOS 挂载脚本]({mac_script_link})\n"
            "- 使用说明：\n"
            "  1. 下载脚本文件到本地（左上角点击下载）\n"
            "  2. 打开终端，添加可执行权限：`chmod +x 文件名.sh`\n"
            "  3. 双击运行脚本输入登录账户信息即可挂载共享盘\n\n"
            "**🪟 Windows 系统：**\n"
            f"- [点击下载 Windows 挂载脚本]({windows_script_link})\n"
            "- 使用说明：\n"
            "  1. 下载脚本文件到本地（左上角点击下载）\n"
            "  2. 双击运行脚本输入登录账户信息即可挂载共享盘\n\n"
            "📧 如有疑问，请联系系统管理员"
        )
    
    def _format_error_message(self, error_msg):
        """格式化错误消息（钉钉 Markdown）"""
        return (
            "### ❌ 帐户开通失败通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            "#### ⚠️ 创建用户失败\n\n"
            f"> **错误信息**：{error_msg}\n\n"
            "📧 如有疑问，请联系系统管理员"
        )
    
    def _format_user_exists_message(self, name, error_msg):
        """格式化用户已存在消息（钉钉 Markdown）"""
        return (
            "### ⚠️ 用户已存在通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            "#### ℹ️ 用户已存在\n\n"
            f"**姓名**：{name}\n\n"
            f"> {error_msg}\n\n"
            "📧 如有疑问，请联系系统管理员"
        )
    
    def _format_group_success_message(self, name):
        """格式化群消息成功通知（不包含敏感信息）"""
        return (
            "### ✅ 帐户开通完成通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            f"**用户 {name} 的账户已成功创建**\n\n"
            "📧 账户信息已通过私聊发送给用户，请通知用户查收"
        )
    
    def _format_group_error_message(self, name, error_msg):
        """格式化群消息错误通知（不包含敏感信息）"""
        return (
            "### ❌ 帐户开通失败通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            f"**用户 {name} 的账户创建失败**\n\n"
            f"> **错误信息**：{error_msg}\n\n"
            "📧 详细错误信息已通过私聊发送给用户"
        )
    
    def _format_group_user_exists_message(self, name):
        """格式化群消息用户已存在通知（不包含敏感信息）"""
        return (
            "### ⚠️ 用户已存在通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            f"**用户 {name} 的账户已存在**\n\n"
            "📧 详细信息已通过私聊发送给用户"
        )
    
    def _create_user_directly(self, name, target_user_id, open_conversation_id, is_group_message):
        """直接创建用户（不通过卡片审批）"""
        ok, username, password, error_msg = self.synology_client.create_user_from_name(name)
        
        if ok:
            reply_content = self._format_success_message(name, username, password)
            # 发送消息给目标用户（输入的姓名对应的用户）
            self.send_private_markdown(target_user_id, None, "帐户开通完成通知", reply_content)
            # 如果是群消息，同时发送群回复
            if is_group_message and open_conversation_id:
                group_reply = self._format_group_success_message(name)
                self.send_group_markdown(open_conversation_id, "帐户开通完成通知", group_reply)
        else:
            # 检查是否是用户已存在的错误
            if "已存在" in error_msg:
                reply_content = self._format_user_exists_message(name, error_msg)
                group_reply = self._format_group_user_exists_message(name) if is_group_message else None
            else:
                reply_content = self._format_error_message(error_msg)
                group_reply = self._format_group_error_message(name, error_msg) if is_group_message else None
            
            self.send_private_markdown(target_user_id, None, "帐户开通失败通知", reply_content)
            if is_group_message and open_conversation_id and group_reply:
                self.send_group_markdown(open_conversation_id, "帐户开通失败通知", group_reply)
    
    def _create_card_client(self):
        """创建卡片API客户端"""
        config = open_api_models.Config()
        config.protocol = "https"
        config.region_id = "central"
        return dingtalkcard_1_0Client(config)
    
    def send_approval_card(self, name, target_user_id, sender_staff_id, open_conversation_id, is_group_message):
        """发送审批卡片给目标用户"""
        if not self.card_template_id:
            logger.error("未配置卡片模板ID，无法发送卡片")
            return False
        
        access_token = self._get_access_token()
        if not access_token:
            logger.error("无法获取access_token，无法发送卡片")
            return False
        
        try:
            client = self._create_card_client()
            
            # 创建请求头
            headers = dingtalkcard__1__0_models.CreateAndDeliverHeaders()
            headers.x_acs_dingtalk_access_token = access_token
            
            # 创建机器人交付模型
            im_robot_open_deliver_model = dingtalkcard__1__0_models.CreateAndDeliverRequestImRobotOpenDeliverModel(
                space_type='IM_ROBOT',
                robot_code=self.client_id,
            )
            
            # 创建搜索支持模型
            search_support = dingtalkcard__1__0_models.CreateAndDeliverRequestImRobotOpenSpaceModelSearchSupport(
                search_icon="",
                search_desc=f"账户创建审批：{name}"
            )
            
            # 创建最后消息国际化
            last_message_i18n = {
                'ZH_CN': f"账户创建审批：{name}"
            }
            
            # 创建空间模型
            im_robot_open_space_model = dingtalkcard__1__0_models.CreateAndDeliverRequestImRobotOpenSpaceModel(
                support_forward=True,
                last_message_i18n=last_message_i18n,
                search_support=search_support,
            )
            
            # 创建卡片数据
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            card_data_map = {
                "lastMessage": f"账户创建审批：{name}",
                "title": f"{name} 的账户创建审批",
                "name": name,
                "createTime": current_time,
                "status": "待审批",
                "applicant": self.admin_name
            }
            
            card_data = dingtalkcard__1__0_models.CreateAndDeliverRequestCardData(
                card_param_map=convert_json_values_to_string(card_data_map)
            )
            
            # 生成唯一的 out_track_id
            out_track_id = f"user-create-{name}-{int(time.time())}"
            
            # 创建请求
            create_and_deliver_request = dingtalkcard__1__0_models.CreateAndDeliverRequest(
                user_id=target_user_id,
                card_template_id=self.card_template_id,
                out_track_id=out_track_id,
                callback_type="STREAM",
                card_data=card_data,
                open_space_id=f"dtv1.card//im_robot.{target_user_id}",
                im_robot_open_deliver_model=im_robot_open_deliver_model,
                im_robot_open_space_model=im_robot_open_space_model,
                user_id_type=1,
            )
            
            # 异步调用（使用 asyncio）
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环已经在运行，使用 run_coroutine_threadsafe
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self._send_card_async(client, create_and_deliver_request, headers))
                        result = future.result(timeout=10)
                else:
                    result = asyncio.run(self._send_card_async(client, create_and_deliver_request, headers))
            except RuntimeError:
                # 如果没有事件循环，创建一个新的
                result = asyncio.run(self._send_card_async(client, create_and_deliver_request, headers))
            
            if not result:
                return False
            
            # 保存卡片信息用于后续回调处理
            self.pending_cards[out_track_id] = {
                'name': name,
                'target_user_id': target_user_id,
                'sender_staff_id': sender_staff_id,
                'open_conversation_id': open_conversation_id,
                'is_group_message': is_group_message,
                'create_time': current_time
            }
            
            return True
            
        except Exception as e:
            logger.error(f"发送审批卡片失败: {e}", exc_info=True)
            return False
    
    async def _send_card_async(self, client, request, headers):
        """异步发送卡片"""
        try:
            await client.create_and_deliver_with_options_async(
                request,
                headers,
                util_models.RuntimeOptions(),
            )
            return True
        except Exception as err:
            logger.error(f"卡片API调用失败: {err}")
            if hasattr(err, 'code') and hasattr(err, 'message'):
                logger.error(f"错误代码: {err.code}, 错误消息: {err.message}")
            return False


class CardCallbackHandlerImpl:
    """卡片回调处理器，处理用户点击卡片按钮的事件"""
    
    def __init__(self, user_bot_handler):
        self.user_bot_handler = user_bot_handler
    
    def pre_start(self):
        """预启动方法，SDK 要求所有处理器必须实现此方法"""
        pass
    
    async def raw_process(self, callback):
        """处理原始回调数据"""
        try:
            # 如果已经是 CardCallbackMessage 对象，直接处理
            if isinstance(callback, CardCallbackMessage):
                return await self.process(callback)
            
            # 如果是字典，直接处理（不尝试转换，避免 to_dict 错误）
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
    
    async def process(self, callback):
        """处理卡片回调事件"""
        try:
            # 解析卡片回调消息 - 支持多种格式
            # 处理字典类型（最常见的情况）
            if isinstance(callback, dict):
                callback_data = callback
            # 处理 CardCallbackMessage 对象
            elif isinstance(callback, CardCallbackMessage):
                # 优先从 data 属性获取
                if hasattr(callback, 'data') and isinstance(callback.data, dict):
                    callback_data = callback.data
                # 如果有 to_dict 方法且可调用，使用它
                elif hasattr(callback, 'to_dict') and callable(getattr(callback, 'to_dict', None)):
                    try:
                        callback_data = callback.to_dict()
                    except (AttributeError, TypeError):
                        callback_data = callback.__dict__ if hasattr(callback, '__dict__') else {}
                else:
                    callback_data = callback.__dict__ if hasattr(callback, '__dict__') else {}
            # 处理有 data 属性的对象
            elif hasattr(callback, 'data'):
                data = callback.data
                callback_data = data if isinstance(data, dict) else {}
            else:
                callback_data = {}
            
            # 获取 out_track_id（卡片的唯一标识）
            out_track_id = callback_data.get('outTrackId') or callback_data.get('out_track_id')
            if not out_track_id:
                logger.error("无法获取 out_track_id")
                return {"status": "FAIL"}
            
            # 获取按钮点击信息
            content = callback_data.get('content', {})
            content_dict = {}
            
            # 解析 content（可能是 JSON 字符串）
            if isinstance(content, str):
                try:
                    content_dict = json.loads(content)
                except:
                    content_dict = {}
            elif isinstance(content, dict):
                content_dict = content
            
            # 从 content 中提取 cardPrivateData
            card_private_data = content_dict.get('cardPrivateData', {}) if isinstance(content_dict, dict) else {}
            params = card_private_data.get('params', {}) if isinstance(card_private_data, dict) else {}
            
            # 获取用户操作 - 根据钉钉卡片回调的实际格式解析
            # 优先从 cardPrivateData.params.action 获取
            user_action = (params.get('action') or
                          card_private_data.get('action') if isinstance(card_private_data, dict) else None or
                          content_dict.get('action') if isinstance(content_dict, dict) else None or
                          callback_data.get('action') or
                          callback_data.get('actionValue'))
            
            # 获取操作者信息 - 从 userId 字段获取（卡片回调中 userId 就是操作者）
            operator_user_id = callback_data.get('userId')
            if not operator_user_id:
                # 尝试从 operator 字段获取
                operator = callback_data.get('operator') or {}
                if isinstance(operator, dict):
                    operator_user_id = operator.get('userId') or operator.get('userid') or operator.get('dingtalkId')
                elif isinstance(operator, str):
                    operator_user_id = operator
            
            # 查找对应的待审批卡片信息
            card_info = self.user_bot_handler.pending_cards.get(out_track_id)
            if not card_info:
                logger.warning(f"未找到对应的卡片信息: {out_track_id}")
                return {"status": "FAIL", "message": "未找到对应的卡片信息"}
            
            name = card_info.get('name')
            target_user_id = card_info.get('target_user_id')
            sender_staff_id = card_info.get('sender_staff_id')
            open_conversation_id = card_info.get('open_conversation_id')
            is_group_message = card_info.get('is_group_message', False)
            
            # 权限检查：只有管理员可以审批
            if not self.user_bot_handler._check_admin_permission(operator_user_id):
                operator_name = self.user_bot_handler.get_user_name_by_id(operator_user_id) if operator_user_id else "未知用户"
                logger.warning(f"用户 {operator_name} ({operator_user_id}) 尝试审批，但无权限")
                
                # 发送权限不足消息给操作者
                permission_denied_msg = (
                    "### ⚠️ 权限不足\n\n"
                    "**微爱基金会 · 共享盘系统**\n\n"
                    "---\n\n"
                    "**抱歉，您没有权限进行审批操作**\n\n"
                    f"只有管理员 **{self.user_bot_handler.admin_name}** 可以审批账户创建请求。\n\n"
                    "📧 如需审批，请联系管理员"
                )
                if operator_user_id:
                    self.user_bot_handler.send_private_markdown(operator_user_id, None, "权限不足", permission_denied_msg)
                
                return {"status": "FAIL", "message": "权限不足"}
            
            # 判断用户操作 - 支持多种可能的 action 值
            if user_action in ['approve', '同意', 'agree', 'confirm', 'accept', '通过']:
                # 用户点击了同意按钮
                # 创建用户
                ok, username, password, error_msg = self.user_bot_handler.synology_client.create_user_from_name(name)
                
                if ok:
                    # 创建成功
                    
                    # 发送成功消息给目标用户
                    reply_content = self.user_bot_handler._format_success_message(name, username, password)
                    self.user_bot_handler.send_private_markdown(target_user_id, None, "帐户开通完成通知", reply_content)
                    
                    # 如果是群消息，同时发送群回复
                    if is_group_message and open_conversation_id:
                        group_reply = self.user_bot_handler._format_group_success_message(name)
                        self.user_bot_handler.send_group_markdown(open_conversation_id, "帐户开通完成通知", group_reply)
                    
                    # 通知管理员
                    if sender_staff_id:
                        admin_notice = (
                            f"### ✅ 账户创建审批已通过\n\n"
                            f"**用户 {name} 的账户创建审批已通过**\n\n"
                            f"账户信息已发送给用户"
                        )
                        self.user_bot_handler.send_private_markdown(sender_staff_id, None, "审批结果通知", admin_notice)
                    
                    # 从待审批列表中移除
                    if out_track_id in self.user_bot_handler.pending_cards:
                        del self.user_bot_handler.pending_cards[out_track_id]
                    
                    return {"status": "SUCCESS"}
                else:
                    # 创建失败
                    logger.error(f"创建用户失败: {error_msg}")
                    
                    # 发送失败消息
                    if "已存在" in error_msg:
                        reply_content = self.user_bot_handler._format_user_exists_message(name, error_msg)
                    else:
                        reply_content = self.user_bot_handler._format_error_message(error_msg)
                    
                    self.user_bot_handler.send_private_markdown(target_user_id, None, "帐户开通失败通知", reply_content)
                    
                    # 通知管理员
                    if sender_staff_id:
                        admin_notice = (
                            f"### ❌ 账户创建失败\n\n"
                            f"**用户 {name} 的账户创建失败**\n\n"
                            f"错误信息：{error_msg}"
                        )
                        self.user_bot_handler.send_private_markdown(sender_staff_id, None, "审批结果通知", admin_notice)
                    
                    # 从待审批列表中移除
                    if out_track_id in self.user_bot_handler.pending_cards:
                        del self.user_bot_handler.pending_cards[out_track_id]
                    
                    return {"status": "FAIL", "message": error_msg}
            
            elif user_action in ['reject', '拒绝', 'deny', 'cancel', 'reject', '拒绝']:
                # 管理员点击了拒绝按钮
                
                # 只发送拒绝通知给目标用户（不发送给管理员，因为管理员就是操作者）
                reject_content = (
                    "### ❌ 账户创建审批已拒绝\n\n"
                    "**微爱基金会 · 共享盘系统**\n\n"
                    "---\n\n"
                    f"**您的账户创建请求已被拒绝**\n\n"
                    f"**姓名**：{name}\n\n"
                    "📧 如有疑问，请联系系统管理员"
                )
                self.user_bot_handler.send_private_markdown(target_user_id, None, "审批结果通知", reject_content)
                
                # 从待审批列表中移除
                if out_track_id in self.user_bot_handler.pending_cards:
                    del self.user_bot_handler.pending_cards[out_track_id]
                
                return {"status": "SUCCESS"}
            else:
                logger.warning(f"未知的操作类型: {user_action}")
                return {"status": "FAIL", "message": f"未知的操作类型: {user_action}"}
                
        except Exception as e:
            logger.error(f"处理卡片回调时发生错误: {e}", exc_info=True)
            return {"status": "FAIL", "message": str(e)}


class DingTalkBotApp:
    """钉钉机器人应用主类"""
    
    def __init__(self, config_path='config.ini'):
        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding='utf-8')
        
        # 读取钉钉配置
        try:
            self.client_id = self.config.get('dingtalk', 'client_id')
            self.client_secret = self.config.get('dingtalk', 'client_secret')
            # 读取管理员姓名（可选，默认为"蒋成博"）
            try:
                self.admin_name = self.config.get('dingtalk', 'admin_name')
            except:
                self.admin_name = "蒋成博"
                logger.warning("未配置管理员姓名，使用默认值: 蒋成博")
        except Exception as e:
            logger.error(f"读取钉钉配置失败: {e}")
            raise
        
        # 验证配置
        if not self.client_id or not self.client_secret:
            raise ValueError("client_id 或 client_secret 不能为空")
        
        # 初始化Synology客户端
        self.synology_client = SynologyUserCLI(config_path)
    
    def run(self):
        """启动 Stream 模式客户端"""
        try:
            # 创建凭证
            credential = Credential(self.client_id, self.client_secret)
            
            # 创建客户端
            client = DingTalkStreamClient(credential)
            
            # 读取卡片模板ID（可选）
            try:
                card_template_id = self.config.get('dingtalk', 'card_template_id')
            except:
                card_template_id = None
                logger.warning("未配置卡片模板ID，将使用直接创建用户方式")
            
            # 注册回调处理器：监听机器人收到的消息
            handler = UserBotHandler(self.synology_client, self.client_id, self.client_secret, card_template_id, self.admin_name)
            client.register_callback_handler(ChatbotMessage.TOPIC, handler)
            
            # 注册卡片回调处理器：监听卡片按钮点击事件
            card_handler = CardCallbackHandlerImpl(handler)
            try:
                client.register_callback_handler(Card_Callback_Router_Topic, card_handler)
            except Exception as e:
                logger.error(f"注册卡片回调处理器失败: {e}", exc_info=True)
                # 尝试使用字符串形式的 topic
                try:
                    client.register_callback_handler("/v1.0/card/instances/callback", card_handler)
                except Exception as e2:
                    logger.error(f"使用字符串形式注册也失败: {e2}", exc_info=True)
            
            logger.info("机器人服务已启动，正在监听消息和卡片回调...")
            if card_template_id:
                logger.info(f"卡片审批流程已启用，模板ID: {card_template_id}")
            else:
                logger.warning("卡片模板ID未配置，将使用直接创建用户方式")
            print("机器人服务已启动，正在监听消息和卡片回调...")
            
            # 启动服务（阻塞运行）
            client.start_forever()
            
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭服务...")
            print("\n正在关闭服务...")
        except Exception as e:
            logger.error(f"启动服务时发生错误: {e}", exc_info=True)
            print(f"\n启动服务时发生错误: {e}")
            raise


if __name__ == '__main__':
    bot = DingTalkBotApp('config.ini')
    bot.run()
