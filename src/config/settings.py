#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
统一管理系统配置
"""
import configparser
import os
from typing import Optional


class Settings:
    """配置管理类"""
    
    def __init__(self, config_file: str = "config.ini"):
        """初始化配置
        
        Args:
            config_file: 配置文件路径
        """
        self.config = configparser.ConfigParser()
        
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        self.config.read(config_file, encoding='utf-8')
        self._validate_config()
    
    def _validate_config(self):
        """验证配置完整性"""
        # 验证必需的配置项
        required_sections = {
            'synology': ['url', 'username', 'password'],
            'dingtalk': ['client_id', 'client_secret']
        }
        
        for section, keys in required_sections.items():
            if not self.config.has_section(section):
                raise ValueError(f"缺少配置节: {section}")
            
            for key in keys:
                if not self.config.has_option(section, key):
                    raise ValueError(f"缺少配置项: {section}.{key}")
    
    # Synology 配置
    @property
    def synology_url(self) -> str:
        """Synology URL"""
        return self.config.get('synology', 'url')
    
    @property
    def synology_host(self) -> str:
        """Synology 主机地址"""
        url = self.synology_url
        return url.replace("https://", "").replace("http://", "").split(":")[0]
    
    @property
    def synology_ssh_port(self) -> int:
        """SSH 端口"""
        return self.config.getint('synology', 'ssh_port', fallback=22)
    
    @property
    def synology_username(self) -> str:
        """Synology 用户名"""
        return self.config.get('synology', 'username')
    
    @property
    def synology_password(self) -> str:
        """Synology 密码"""
        return self.config.get('synology', 'password')
    
    # 钉钉配置
    @property
    def dingtalk_client_id(self) -> str:
        """钉钉 Client ID"""
        return self.config.get('dingtalk', 'client_id')
    
    @property
    def dingtalk_client_secret(self) -> str:
        """钉钉 Client Secret"""
        return self.config.get('dingtalk', 'client_secret')
    
    @property
    def dingtalk_card_template_id(self) -> Optional[str]:
        """钉钉卡片模板 ID（可选）"""
        try:
            return self.config.get('dingtalk', 'card_template_id')
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None
    
    @property
    def admin_name(self) -> str:
        """管理员姓名"""
        try:
            return self.config.get('dingtalk', 'admin_name')
        except (configparser.NoSectionError, configparser.NoOptionError):
            return "蒋成博"  # 默认值

