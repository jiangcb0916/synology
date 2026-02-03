#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synology 用户管理服务
负责与 Synology NAS 交互，创建和管理用户
"""
import logging
import shlex
import paramiko
from typing import Tuple, List, Dict

from ..config import Settings
from ..utils import NameUtils, PasswordGenerator

logger = logging.getLogger(__name__)

# VLF 组名
VLF_GROUP = "vlf"


class SynologyService:
    """Synology 用户管理服务"""
    
    def __init__(self, settings: Settings):
        """初始化服务
        
        Args:
            settings: 配置对象
        """
        self.settings = settings
        self.host = settings.synology_host
        self.port = settings.synology_ssh_port
        self.username = settings.synology_username
        self.password = settings.synology_password
    
    def _ssh_exec(self, cmd: str) -> Tuple[str, str, int]:
        """执行 SSH 命令
        
        Args:
            cmd: 要执行的命令
            
        Returns:
            (stdout, stderr, exit_status) 元组
        """
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
            )
            
            stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
            stdin.write(self.password + "\n")
            stdin.flush()
            
            out = stdout.read().decode(errors="ignore").strip()
            err = stderr.read().decode(errors="ignore").strip()
            exit_status = stdout.channel.recv_exit_status()
            
            return out, err, exit_status
        finally:
            ssh.close()
    
    def user_exists(self, username: str) -> bool:
        """检查用户是否存在
        
        Args:
            username: 用户名
            
        Returns:
            用户是否存在
        """
        cmd = f"id {shlex.quote(username)}"
        _, _, exit_status = self._ssh_exec(cmd)
        return exit_status == 0
    
    def create_user(self, username: str, password: str, fullname: str, email: str = "") -> Tuple[bool, str]:
        """创建 Synology 用户
        
        Args:
            username: 用户名
            password: 密码
            fullname: 全名/描述
            email: 邮箱（可选）
            
        Returns:
            (成功标志, 错误信息) 元组
        """
        # 创建用户命令
        quoted_password = shlex.quote(password)
        cmd_create = (
            "sudo -S /usr/syno/sbin/synouser --add "
            f"{shlex.quote(username)} "
            f"{quoted_password} "
            f"{shlex.quote(fullname)} "
            "0 "
            f"{shlex.quote(email)} "
            "default"
        )
        
        out, err, exit_status = self._ssh_exec(cmd_create)
        if err or exit_status != 0:
            logger.error(f"创建用户失败: {err}")
            # 检查是否是用户已存在的错误
            error_lower = err.lower()
            if "already exists" in error_lower or "已存在" in error_lower or "exists" in error_lower:
                return False, "用户已存在"
            return False, f"创建用户失败: {err}"
        
        # 将用户加入 vlf 组
        cmd_group = (
            "sudo -S /usr/syno/sbin/synogroup --member "
            f"{shlex.quote(VLF_GROUP)} "
            f"{shlex.quote(username)}"
        )
        
        out, err, exit_status = self._ssh_exec(cmd_group)
        if err or exit_status != 0:
            logger.error(f"加入 vlf 组失败: {err}")
            return False, f"加入vlf组失败: {err}"
        
        logger.info(f"成功创建用户: {username}")
        return True, ""
    
    def create_user_from_name(self, name: str, email: str = "") -> Tuple[bool, str, str, str]:
        """根据姓名创建用户（自动生成用户名和密码）
        
        Args:
            name: 用户姓名
            email: 邮箱（可选）
            
        Returns:
            (成功标志, 用户名, 密码, 错误信息) 元组
        """
        # 生成用户名
        username = NameUtils.to_pinyin(name)
        
        # 检查用户是否已存在
        if self.user_exists(username):
            error_msg = f"用户 {name}（用户名：{username}）已存在"
            logger.warning(error_msg)
            return False, "", "", error_msg
        
        # 生成密码
        password = PasswordGenerator.generate()
        
        # 创建用户
        ok, error_msg = self.create_user(username, password, name, email)
        
        if ok:
            return True, username, password, ""
        else:
            return False, "", "", error_msg
    
    def get_all_users(self) -> Tuple[bool, List[Dict[str, str]], str]:
        """获取所有用户列表（只返回用户名和描述）
        
        Returns:
            (成功标志, 用户列表, 错误信息) 元组
            用户列表格式: [{"username": "...", "description": "..."}, ...]
        """
        # 使用 cat /etc/passwd 获取所有用户信息（Synology 兼容）
        # 格式: username:x:uid:gid:description:home:shell
        cmd = "cat /etc/passwd"
        out, err, exit_status = self._ssh_exec(cmd)
        
        if err or exit_status != 0:
            logger.error(f"查询所有用户失败: stdout={out}, stderr={err}, exit_status={exit_status}")
            error_msg = err if err else (out if out else f"命令执行失败，退出码: {exit_status}")
            return False, [], f"查询失败: {error_msg}"
        
        # 解析输出
        users = []
        lines = out.split('\n')
        
        # 系统用户过滤列表（可选，根据需要调整）
        system_users = {'root', 'daemon', 'bin', 'sys', 'sync', 'games', 
                       'man', 'mail', 'www-data', 'backup', 'list', 'irc', 'nobody',
                       'systemd-network', 'systemd-resolve', 'messagebus', 'sshd',
                       'lp', 'news', 'uucp', 'proxy', 'www', 'ftp', 'guest'}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 跳过注释行
            if line.startswith('#'):
                continue
            
            # 解析 passwd 格式: username:x:uid:gid:description:home:shell
            parts = line.split(':')
            if len(parts) >= 5:
                username = parts[0].strip()
                description = parts[4].strip() if parts[4] else ""
                
                # 过滤系统用户（但保留 admin，因为可能是管理员账户）
                if username in system_users:
                    continue
                
                # 过滤 UID < 1000 的系统用户（通常系统用户的 UID 小于 1000）
                try:
                    uid = int(parts[2]) if len(parts) > 2 else 0
                    if uid < 1000 and username != 'admin':
                        continue
                except (ValueError, IndexError):
                    pass
                
                # 只返回有描述的用户（描述是姓名的用户）
                # 过滤掉没有描述或描述为空的用户
                if not description or description.strip() == "":
                    continue
                
                # 只返回用户名和描述
                users.append({
                    "username": username,
                    "description": description
                })
        
        # 按用户名排序
        users.sort(key=lambda x: x['username'])
        
        logger.info(f"成功获取用户列表，共 {len(users)} 个用户")
        return True, users, ""

