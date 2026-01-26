#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
姓名处理工具
"""
from pypinyin import pinyin, Style


class NameUtils:
    """姓名处理工具类"""
    
    @staticmethod
    def to_pinyin(name: str) -> str:
        """将中文姓名转换为全拼
        
        Args:
            name: 中文姓名
            
        Returns:
            拼音用户名（小写）
        """
        pinyin_list = pinyin(name, style=Style.NORMAL)
        return "".join([item[0] for item in pinyin_list]).lower()

