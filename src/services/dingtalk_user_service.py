#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉用户服务
负责查找和管理钉钉用户
"""
import logging
import requests
from typing import Optional, List

from .dingtalk_api_service import DingTalkAPIService

logger = logging.getLogger(__name__)


class DingTalkUserService:
    """钉钉用户服务"""
    
    def __init__(self, api_service: DingTalkAPIService):
        """初始化服务
        
        Args:
            api_service: 钉钉 API 服务
        """
        self.api_service = api_service
    
    def find_user_by_name(self, name: str) -> Optional[str]:
        """根据姓名查找钉钉用户 ID
        
        Args:
            name: 用户姓名
            
        Returns:
            用户 ID 或 None
        """
        access_token = self.api_service.get_access_token()
        if not access_token:
            logger.error("无法获取 access_token，无法查找用户")
            return None
        
        # 尝试多种方法查找用户
        userid = self._search_user_by_name(name, access_token)
        if userid:
            return userid
        
        userid = self._find_user_by_department(name, access_token)
        if userid:
            return userid
        
        logger.warning(f"未找到姓名为 '{name}' 的用户")
        return None
    
    def get_user_name_by_id(self, user_id: str) -> Optional[str]:
        """根据钉钉用户 ID 获取用户姓名
        
        Args:
            user_id: 用户 ID
            
        Returns:
            用户姓名 或 None
        """
        access_token = self.api_service.get_access_token()
        if not access_token:
            logger.error("无法获取 access_token，无法查找用户")
            return None
        
        try:
            url = "https://oapi.dingtalk.com/topapi/v2/user/get"
            params = {"access_token": access_token}
            payload = {"userid": user_id}
            
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
            logger.error(f"通过钉钉 ID 获取用户姓名异常: {e}", exc_info=True)
        
        return None
    
    def _search_user_by_name(self, name: str, access_token: str) -> Optional[str]:
        """使用搜索 API 查找用户
        
        Args:
            name: 用户姓名
            access_token: 访问令牌
            
        Returns:
            用户 ID 或 None
        """
        try:
            url = "https://oapi.dingtalk.com/topapi/smartwork/hrm/employee/queryonjob"
            response = requests.post(
                url,
                params={"access_token": access_token},
                json={"status_list": [2, 3, 5], "offset": 0, "size": 100},
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") == 0:
                for user in result.get("result", {}).get("data_list", []):
                    if user.get("name", "").strip() == name.strip():
                        return user.get("userid")
        except Exception as e:
            logger.debug(f"搜索 API 查找用户失败: {e}")
        
        return None
    
    def _find_user_by_department(self, name: str, access_token: str) -> Optional[str]:
        """通过遍历部门查找用户
        
        Args:
            name: 用户姓名
            access_token: 访问令牌
            
        Returns:
            用户 ID 或 None
        """
        try:
            dept_list = self._get_department_list(access_token)
            if not dept_list:
                logger.warning("无法获取部门列表")
                return None
            
            for dept_id in dept_list:
                userid = self._get_users_in_department(dept_id, name, access_token)
                if userid:
                    return userid
        except Exception as e:
            logger.error(f"通过部门查找用户异常: {e}", exc_info=True)
        
        return None
    
    def _get_department_list(self, access_token: str) -> List[int]:
        """获取所有部门 ID 列表
        
        Args:
            access_token: 访问令牌
            
        Returns:
            部门 ID 列表
        """
        try:
            url = "https://oapi.dingtalk.com/topapi/v2/department/listsub"
            params = {"access_token": access_token}
            dept_list = [1]  # 从根部门开始
            
            def get_sub_depts(dept_id: int):
                payload = {"dept_id": dept_id}
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
                                get_sub_depts(sub_dept_id)
                except Exception:
                    pass
            
            get_sub_depts(1)
            return dept_list
        except Exception as e:
            logger.error(f"获取部门列表失败: {e}", exc_info=True)
            return [1]
    
    def _get_users_in_department(self, dept_id: int, target_name: str, access_token: str) -> Optional[str]:
        """获取指定部门中的用户
        
        Args:
            dept_id: 部门 ID
            target_name: 目标用户姓名
            access_token: 访问令牌
            
        Returns:
            用户 ID 或 None
        """
        try:
            url = "https://oapi.dingtalk.com/topapi/v2/user/list"
            params = {"access_token": access_token}
            cursor = 0
            page_size = 100
            
            while True:
                response = requests.post(
                    url,
                    params=params,
                    json={"dept_id": dept_id, "cursor": cursor, "size": page_size},
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("errcode") != 0:
                    break
                
                user_list = result.get("result", {}).get("list", [])
                if not user_list:
                    break
                
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

