#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密码生成工具
"""
import random
import string


class PasswordGenerator:
    """密码生成器"""
    
    @staticmethod
    def generate(length: int = 8) -> str:
        """生成随机密码
        
        Args:
            length: 密码长度
            
        Returns:
            随机密码（只包含字母和数字）
        """
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

