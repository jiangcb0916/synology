#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import getpass
import paramiko
import shlex
import sys
import random
import string
import logging
from pypinyin import pinyin, Style

VLF_GROUP = "vlf"


class SynologyUserCLI:
    def __init__(self, config_file="config.ini"):
        cfg = configparser.ConfigParser()
        cfg.read(config_file, encoding="utf-8")

        url = cfg.get("synology", "url")
        self.host = url.replace("https://", "").replace("http://", "").split(":")[0]
        self.port = cfg.getint("synology", "ssh_port", fallback=22)
        self.username = cfg.get("synology", "username")
        self.password = cfg.get("synology", "password")

    def _ssh_exec(self, cmd):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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
        ssh.close()
        return out, err, exit_status

    def create_user(self, username, password, fullname, email):
        # 1️⃣ 创建用户（允许所有应用，自动加入users组）
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
            logger = logging.getLogger(__name__)
            logger.error(f"创建用户失败: {err}")
            # 检查是否是用户已存在的错误
            error_lower = err.lower()
            if "already exists" in error_lower or "已存在" in error_lower or "exists" in error_lower:
                return False, "用户已存在"
            return False, f"创建用户失败: {err}"

        # 2️⃣ 将用户加入vlf组（组内已配置所需权限）
        cmd_group = (
            "sudo -S /usr/syno/sbin/synogroup --member "
            f"{shlex.quote(VLF_GROUP)} "
            f"{shlex.quote(username)}"
        )

        out, err, exit_status = self._ssh_exec(cmd_group)
        if err or exit_status != 0:
            return False, f"加入vlf组失败: {err}"

        return True, ""

    @staticmethod
    def name_to_pinyin(name):
        """将中文姓名转换为全拼"""
        pinyin_list = pinyin(name, style=Style.NORMAL)
        return "".join([item[0] for item in pinyin_list]).lower()

    @staticmethod
    def generate_random_password(length=8):
        """生成随机密码（只包含字母和数字，避免特殊字符问题）"""
        chars = string.ascii_letters + string.digits
        password = ''.join(random.choice(chars) for _ in range(length))
        # 确保密码不包含会被shlex.quote改变的特殊字符
        # 由于我们只使用字母和数字，shlex.quote不会改变密码
        return password

    def user_exists(self, username):
        """检查用户是否存在"""
        cmd = f"id {shlex.quote(username)}"
        out, err, exit_status = self._ssh_exec(cmd)
        # exit_status == 0 表示用户存在
        return exit_status == 0

    def create_user_from_name(self, name, email=""):
        """根据姓名创建用户（自动生成用户名和密码）"""
        username = self.name_to_pinyin(name)
        
        # 先检查用户是否已存在
        if self.user_exists(username):
            return False, "", "", f"用户 {name}（用户名：{username}）已存在"
        
        password = self.generate_random_password()
        
        ok, msg = self.create_user(username, password, name, email)
        if ok:
            return True, username, password, ""
        else:
            return False, "", "", msg

    def run(self):
        print("\n=== DSM7 用户创建 CLI（加入vlf组）===\n")

        username = input("用户名: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            sys.exit(1)

        password = getpass.getpass("密码: ")
        confirm = getpass.getpass("确认密码: ")
        if password != confirm:
            print("❌ 两次密码不一致")
            sys.exit(1)

        fullname = input("描述 / 全名 [可留空]: ").strip() or username
        email = input("邮箱 [可留空]: ").strip()

        print("\n🚀 正在创建用户并配置权限...\n")

        ok, msg = self.create_user(username, password, fullname, email)
        if not ok:
            print("❌ 失败：")
            print(msg)
            return

        print("✅ 用户创建成功（自动加入users组）")
        print(f"✅ 已加入 {VLF_GROUP} 组（组内权限已配置）")
        print("\n🎉 完成")


if __name__ == "__main__":
    SynologyUserCLI("config.ini").run()