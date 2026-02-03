#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息格式化工具
用于生成各种钉钉 Markdown 消息
"""
from typing import List, Dict


class MessageFormatter:
    """消息格式化器"""
    
    # 脚本链接（可以从配置中读取）
    MAC_SCRIPT_LINK = "https://qr.dingtalk.com/page/yunpan?route=previewDentry&spaceId=441584833&fileId=208808669078&type=file"
    WINDOWS_SCRIPT_LINK = "https://qr.dingtalk.com/page/yunpan?route=previewDentry&spaceId=441584833&fileId=208825411677&type=file"
    
    @staticmethod
    def format_success_message(name: str, username: str, password: str) -> str:
        """格式化账户创建成功消息
        
        Args:
            name: 用户姓名
            username: 用户名
            password: 密码
            
        Returns:
            Markdown 格式的成功消息
        """
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
            f"- [点击下载 macOS 挂载脚本]({MessageFormatter.MAC_SCRIPT_LINK})\n"
            "- 使用说明：\n"
            "  1. 下载脚本文件到本地（左上角点击下载）\n"
            "  2. 打开终端，添加可执行权限：`chmod +x 文件名.sh`\n"
            "  3. 双击运行脚本输入登录账户信息即可挂载共享盘\n\n"
            "**🪟 Windows 系统：**\n"
            f"- [点击下载 Windows 挂载脚本]({MessageFormatter.WINDOWS_SCRIPT_LINK})\n"
            "- 使用说明：\n"
            "  1. 下载脚本文件到本地（左上角点击下载）\n"
            "  2. 双击运行脚本输入登录账户信息即可挂载共享盘\n\n"
            "📧 如有疑问，请联系系统管理员"
        )
    
    @staticmethod
    def format_error_message(error_msg: str) -> str:
        """格式化账户创建失败消息
        
        Args:
            error_msg: 错误信息
            
        Returns:
            Markdown 格式的错误消息
        """
        return (
            "### ❌ 帐户开通失败通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            "#### ⚠️ 创建用户失败\n\n"
            f"> **错误信息**：{error_msg}\n\n"
            "📧 如有疑问，请联系系统管理员"
        )
    
    @staticmethod
    def format_user_exists_message(name: str, error_msg: str) -> str:
        """格式化用户已存在消息
        
        Args:
            name: 用户姓名
            error_msg: 错误信息
            
        Returns:
            Markdown 格式的用户已存在消息
        """
        return (
            "### ⚠️ 用户已存在通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            "#### ℹ️ 用户已存在\n\n"
            f"**姓名**：{name}\n\n"
            f"> {error_msg}\n\n"
            "📧 如有疑问，请联系系统管理员"
        )
    
    @staticmethod
    def format_group_success_message(name: str) -> str:
        """格式化群消息成功通知（不含敏感信息）
        
        Args:
            name: 用户姓名
            
        Returns:
            Markdown 格式的群消息
        """
        return (
            "### ✅ 帐户开通完成通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            f"**用户 {name} 的账户已成功创建**\n\n"
            "📧 账户信息已通过私聊发送给用户，请通知用户查收"
        )
    
    @staticmethod
    def format_group_error_message(name: str, error_msg: str) -> str:
        """格式化群消息错误通知（不含敏感信息）
        
        Args:
            name: 用户姓名
            error_msg: 错误信息
            
        Returns:
            Markdown 格式的群消息
        """
        return (
            "### ❌ 帐户开通失败通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            f"**用户 {name} 的账户创建失败**\n\n"
            f"> **错误信息**：{error_msg}\n\n"
            "📧 详细错误信息已通过私聊发送给用户"
        )
    
    @staticmethod
    def format_group_user_exists_message(name: str) -> str:
        """格式化群消息用户已存在通知（不含敏感信息）
        
        Args:
            name: 用户姓名
            
        Returns:
            Markdown 格式的群消息
        """
        return (
            "### ⚠️ 用户已存在通知\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            f"**用户 {name} 的账户已存在**\n\n"
            "📧 详细信息已通过私聊发送给用户"
        )
    
    @staticmethod
    def format_permission_denied_message(admin_name: str) -> str:
        """格式化权限不足消息
        
        Args:
            admin_name: 管理员姓名
            
        Returns:
            Markdown 格式的权限不足消息
        """
        return (
            "### ⚠️ 权限不足\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            "**抱歉，您没有权限使用此功能**\n\n"
            f"只有管理员 **{admin_name}** 可以使用此机器人创建用户账户。\n\n"
            "📧 如需创建用户账户，请联系管理员"
        )
    
    @staticmethod
    def format_user_not_found_message(name: str) -> str:
        """格式化用户未找到消息
        
        Args:
            name: 用户姓名
            
        Returns:
            Markdown 格式的用户未找到消息
        """
        return (
            "### ❌ 用户查找失败\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            "**未找到用户**\n\n"
            f"未找到姓名为 **'{name}'** 的钉钉用户，请确认姓名是否正确。\n\n"
            "**可能的原因：**\n"
            "1. 姓名输入错误\n"
            "2. 该用户不在钉钉组织内\n"
            "3. 该用户已离职或未激活\n\n"
            "账户创建请求已取消。\n\n"
            "📧 如有疑问，请联系系统管理员"
        )
    
    @staticmethod
    def format_approval_reject_message(name: str) -> str:
        """格式化审批拒绝消息
        
        Args:
            name: 用户姓名
            
        Returns:
            Markdown 格式的拒绝消息
        """
        return (
            "### ❌ 账户创建审批已拒绝\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            "**您的账户创建请求已被拒绝**\n\n"
            f"**姓名**：{name}\n\n"
            "📧 如有疑问，请联系系统管理员"
        )
    
    @staticmethod
    def format_user_list_message(users: List[Dict[str, str]]) -> str:
        """格式化用户列表消息
        
        Args:
            users: 用户列表，每个用户包含 username 和 description 字段
            
        Returns:
            Markdown 格式的用户列表消息
        """
        if not users:
            return (
                "### 📋 群晖用户列表\n\n"
                "**微爱基金会 · 共享盘系统**\n\n"
                "---\n\n"
                "**用户总数**：0 人\n\n"
                "---\n\n"
                "**当前没有用户**\n\n"
                "📧 如有疑问，请联系系统管理员"
            )
        
        # 构建用户列表内容
        user_lines = []
        for user in users:
            username = user.get('username', '')
            description = user.get('description', '').strip()
            
            if description:
                user_lines.append(f"**{username}** - {description}")
            else:
                user_lines.append(f"**{username}**")
        
        # 确保每个用户单独一行，使用双换行符确保 Markdown 正确渲染
        user_list_content = "\n\n".join(user_lines)
        
        return (
            "### 📋 群晖用户列表\n\n"
            "**微爱基金会 · 共享盘系统**\n\n"
            "---\n\n"
            f"**用户总数**：{len(users)} 人\n\n"
            "---\n\n"
            "**用户列表**：\n\n"
            f"{user_list_content}\n\n"
            "---\n\n"
            "📧 如有疑问，请联系系统管理员"
        )

