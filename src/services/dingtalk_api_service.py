#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉 API 服务
负责管理 access_token 和基础 API 调用
"""
import logging
import time
import requests
from typing import Optional

from ..config import Settings

logger = logging.getLogger(__name__)


class DingTalkAPIService:
    """钉钉 API 服务"""
    
    def __init__(self, settings: Settings):
        """初始化服务
        
        Args:
            settings: 配置对象
        """
        self.settings = settings
        self.client_id = settings.dingtalk_client_id
        self.client_secret = settings.dingtalk_client_secret
        self._access_token: Optional[str] = None
        self._token_expire_time: float = 0
    
    def get_access_token(self) -> Optional[str]:
        """获取钉钉访问令牌（带缓存）
        
        Returns:
            access_token 或 None
        """
        current_time = time.time()
        
        # 如果 token 未过期，直接返回
        if self._access_token and current_time < self._token_expire_time:
            return self._access_token
        
        # 获取新的 access_token
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
                # token 有效期通常是 7200 秒，提前 5 分钟刷新
                self._token_expire_time = current_time + 7200 - 300
                logger.info("成功获取 access_token")
                return self._access_token
            else:
                logger.error(f"获取 access_token 失败: {data.get('errmsg')}")
                return None
        except Exception as e:
            logger.error(f"获取 access_token 异常: {e}", exc_info=True)
            return None

