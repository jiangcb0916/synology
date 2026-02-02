#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉卡片服务
负责发送和管理互动卡片
"""
import logging
import json
import time
import asyncio
from typing import Any, Dict, Optional
from datetime import datetime

from alibabacloud_dingtalk.card_1_0.client import Client as dingtalkcard_1_0Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.card_1_0 import models as dingtalkcard__1__0_models
from alibabacloud_tea_util import models as util_models

from .dingtalk_api_service import DingTalkAPIService
from ..config import Settings

logger = logging.getLogger(__name__)


def convert_json_values_to_string(obj: Dict[str, Any]) -> Dict[str, str]:
    """
    将字典中的值转换为字符串（卡片 API 要求）
    
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
                result[key] = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                result[key] = ""
    return result


class DingTalkCardService:
    """钉钉卡片服务"""
    
    def __init__(self, api_service: DingTalkAPIService, settings: Settings):
        """初始化服务
        
        Args:
            api_service: 钉钉 API 服务
            settings: 配置对象
        """
        self.api_service = api_service
        self.settings = settings
        self.client_id = settings.dingtalk_client_id
        self.card_template_id = settings.dingtalk_card_template_id
        # 存储待审批的卡片信息
        self.pending_cards: Dict[str, Dict] = {}
    
    def send_approval_card(
        self,
        name: str,
        target_user_id: str,
        sender_staff_id: str,
        open_conversation_id: Optional[str],
        is_group_message: bool,
        admin_name: str,
        approver_user_id: str
    ) -> bool:
        """发送审批卡片
        
        Args:
            name: 用户姓名（要创建的新用户）
            target_user_id: 目标用户 ID（要创建的新用户 ID）
            sender_staff_id: 发送者 ID
            open_conversation_id: 会话 ID
            is_group_message: 是否群消息
            admin_name: 管理员姓名（申请人）
            approver_user_id: 审批人用户 ID（卡片接收者）
            
        Returns:
            是否发送成功
        """
        if not self.card_template_id:
            logger.error("未配置卡片模板 ID，无法发送卡片")
            return False
        
        access_token = self.api_service.get_access_token()
        if not access_token:
            logger.error("无法获取 access_token，无法发送卡片")
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
                "applicant": admin_name
            }
            
            card_data = dingtalkcard__1__0_models.CreateAndDeliverRequestCardData(
                card_param_map=convert_json_values_to_string(card_data_map)
            )
            
            # 生成唯一的 out_track_id
            out_track_id = f"user-create-{name}-{int(time.time())}"
            
            # 创建请求
            # 卡片发送给审批人，而不是新用户
            create_and_deliver_request = dingtalkcard__1__0_models.CreateAndDeliverRequest(
                user_id=approver_user_id,
                card_template_id=self.card_template_id,
                out_track_id=out_track_id,
                callback_type="STREAM",
                card_data=card_data,
                open_space_id=f"dtv1.card//im_robot.{approver_user_id}",
                im_robot_open_deliver_model=im_robot_open_deliver_model,
                im_robot_open_space_model=im_robot_open_space_model,
                user_id_type=1,
            )
            
            # 异步发送卡片
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self._send_card_async(client, create_and_deliver_request, headers)
                        )
                        result = future.result(timeout=10)
                else:
                    result = asyncio.run(self._send_card_async(client, create_and_deliver_request, headers))
            except RuntimeError:
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
            
            logger.info(f"成功发送审批卡片: {out_track_id}")
            return True
            
        except Exception as e:
            logger.error(f"发送审批卡片失败: {e}", exc_info=True)
            return False
    
    async def _send_card_async(
        self,
        client: dingtalkcard_1_0Client,
        request: dingtalkcard__1__0_models.CreateAndDeliverRequest,
        headers: dingtalkcard__1__0_models.CreateAndDeliverHeaders
    ) -> bool:
        """异步发送卡片
        
        Args:
            client: 卡片客户端
            request: 请求对象
            headers: 请求头
            
        Returns:
            是否发送成功
        """
        try:
            await client.create_and_deliver_with_options_async(
                request,
                headers,
                util_models.RuntimeOptions(),
            )
            return True
        except Exception as err:
            logger.error(f"卡片 API 调用失败: {err}")
            if hasattr(err, 'code') and hasattr(err, 'message'):
                logger.error(f"错误代码: {err.code}, 错误消息: {err.message}")
            return False
    
    def _create_card_client(self) -> dingtalkcard_1_0Client:
        """创建卡片 API 客户端
        
        Returns:
            卡片客户端
        """
        config = open_api_models.Config()
        config.protocol = "https"
        config.region_id = "central"
        return dingtalkcard_1_0Client(config)
    
    def get_pending_card(self, out_track_id: str) -> Optional[Dict]:
        """获取待审批卡片信息
        
        Args:
            out_track_id: 卡片追踪 ID
            
        Returns:
            卡片信息或 None
        """
        return self.pending_cards.get(out_track_id)
    
    def remove_pending_card(self, out_track_id: str):
        """移除待审批卡片
        
        Args:
            out_track_id: 卡片追踪 ID
        """
        if out_track_id in self.pending_cards:
            del self.pending_cards[out_track_id]
    
    def update_card_status(
        self,
        out_track_id: str,
        status: str,
        operator_name: Optional[str] = None
    ) -> bool:
        """更新卡片状态
        
        Args:
            out_track_id: 卡片追踪 ID
            status: 状态（"已同意" 或 "已拒绝"）
            operator_name: 操作者姓名（可选）
            
        Returns:
            是否更新成功
        """
        if not self.card_template_id:
            logger.error("未配置卡片模板 ID，无法更新卡片")
            return False
        
        access_token = self.api_service.get_access_token()
        if not access_token:
            logger.error("无法获取 access_token，无法更新卡片")
            return False
        
        # 获取卡片信息
        card_info = self.pending_cards.get(out_track_id)
        if not card_info:
            logger.warning(f"未找到卡片信息: {out_track_id}")
            return False
        
        name = card_info.get('name')
        target_user_id = card_info.get('target_user_id')
        create_time = card_info.get('create_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        try:
            client = self._create_card_client()
            
            # 创建请求头
            headers = dingtalkcard__1__0_models.UpdateCardHeaders()
            headers.x_acs_dingtalk_access_token = access_token
            
            # 创建卡片数据
            card_data_map = {
                "lastMessage": f"账户创建审批：{name}",
                "title": f"{name} 的账户创建审批",
                "name": name,
                "createTime": create_time,
                "status": status,
            }
            
            if operator_name:
                card_data_map["operator"] = operator_name
            
            # 记录要更新的数据
            logger.info(f"准备更新卡片数据: {out_track_id}, 数据: {card_data_map}")
            
            card_data = dingtalkcard__1__0_models.UpdateCardRequestCardData(
                card_param_map=convert_json_values_to_string(card_data_map)
            )
            
            # 创建卡片更新选项，设置按key更新卡片数据
            card_update_options = dingtalkcard__1__0_models.UpdateCardRequestCardUpdateOptions(
                update_card_data_by_key=True,
                update_private_data_by_key=False
            )
            
            # 创建请求
            update_request = dingtalkcard__1__0_models.UpdateCardRequest(
                out_track_id=out_track_id,
                card_data=card_data,
                card_update_options=card_update_options,
                user_id_type=1,  # 1表示使用unionId，与创建卡片时保持一致
            )
            
            # 异步更新卡片
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self._update_card_async(client, update_request, headers)
                        )
                        result = future.result(timeout=10)
                else:
                    result = asyncio.run(self._update_card_async(client, update_request, headers))
            except RuntimeError:
                result = asyncio.run(self._update_card_async(client, update_request, headers))
            
            if result:
                logger.info(f"成功更新卡片状态: {out_track_id}, 状态: {status}")
            else:
                logger.error(f"更新卡片状态失败: {out_track_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"更新卡片状态时发生错误: {e}", exc_info=True)
            return False
    
    async def _update_card_async(
        self,
        client: dingtalkcard_1_0Client,
        request: dingtalkcard__1__0_models.UpdateCardRequest,
        headers: dingtalkcard__1__0_models.UpdateCardHeaders
    ) -> bool:
        """异步更新卡片
        
        Args:
            client: 卡片客户端
            request: 请求对象
            headers: 请求头
            
        Returns:
            是否更新成功
        """
        try:
            response = await client.update_card_with_options_async(
                request,
                headers,
                util_models.RuntimeOptions(),
            )
            # 检查响应是否成功
            if hasattr(response, 'body') and hasattr(response.body, 'success'):
                if response.body.success:
                    logger.info(f"卡片更新API调用成功: {request.out_track_id}")
                    return True
                else:
                    logger.error(f"卡片更新API返回失败: {request.out_track_id}, 响应: {response.body}")
                    return False
            # 如果没有success字段，假设成功
            logger.info(f"卡片更新API调用完成: {request.out_track_id}")
            return True
        except Exception as err:
            logger.error(f"卡片更新 API 调用失败: {err}", exc_info=True)
            if hasattr(err, 'code') and hasattr(err, 'message'):
                logger.error(f"错误代码: {err.code}, 错误消息: {err.message}")
            elif hasattr(err, 'data'):
                logger.error(f"错误数据: {err.data}")
            return False

