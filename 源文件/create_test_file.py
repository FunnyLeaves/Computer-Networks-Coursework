#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
创建一个测试用的文本文件
内容是一段英文，方便验证反转功能
"""

test_content = """Hello everyone, this is a test file for the TCP reverse task.
The server will reverse each chunk of text and send it back.
This is chunk number one. This is chunk number two.
The quick brown fox jumps over the lazy dog.
Python programming is fun and educational.
TCP socket programming helps us understand how networks work.
Good luck with your assignment!
"""

# 写入文件
with open("readme.txt", "w", encoding="utf-8") as f:
    f.write(test_content)

print("已创建测试文件: readme.txt")
print(f"文件大小: {len(test_content)} 字节")
print("\n文件内容预览:")
print("-" * 50)
print(test_content)
print("-" * 50)