#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import struct
import sys
import random
import time


def log_event(message):
    """记录日志到 run_log.txt"""
    with open("run_log.txt", "a", encoding="utf-8") as log_file:   # 追加
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")  # 年月日时分秒
        log_file.write(f"[{timestamp}] {message}\n")
    print(f"[LOG] {message}")  # 同时在屏幕显示


def split_file_into_chunks(file_data, lmin, lmax, seed):
    """
    将文件数据分成随机大小的块

    参数:
        file_data: 文件的原始数据（bytes）
        lmin: 每块最小长度
        lmax: 每块最大长度
        seed: 随机数种子（保证可重复）

    返回:
        chunks: 分块后的列表，每个元素是一块数据
        N: 总块数
    """
    random.seed(seed)  # 设置随机种子，保证每次运行分块结果一样，每个种子的内置无数个随机数是固定值的，伪随机
    chunks = []  # 存分块后的文件字节，一块一块
    position = 0  # 当前位置
    total_length = len(file_data)  # 文件（字节）总长度

    print(f"文件总长度: {total_length} 字节")
    print(f"分块范围: [{lmin}, {lmax}]，随机种子: {seed}")

    while position < total_length:
        remaining = total_length - position  # 还剩多少字节没处理

        # 如果是最后一块，直接取剩余的所有数据
        if remaining <= lmax:
            chunks.append(file_data[position:])
            print(f"  最后一块: {remaining} 字节")
            break

        # 随机生成当前块的长度
        chunk_length = random.randint(lmin, lmax)
        chunks.append(file_data[position:position + chunk_length])  # 对data切片
        print(f"  块 {len(chunks)}: {chunk_length} 字节 (位置 {position}~{position + chunk_length - 1})")
        position += chunk_length

    return chunks, len(chunks)  # len就是N


def tcp_client(server_ip, server_port, file_path, lmin, lmax, seed):
    """TCP客户端主函数"""

    print("=" * 50)
    print("TCP 客户端启动")
    print(f"服务器: {server_ip}:{server_port}")
    print(f"文件: {file_path}")
    print(f"分块范围: [{lmin}, {lmax}]")
    print("=" * 50)

    # 清空日志文件
    open("run_log.txt", "w", encoding="utf-8").close()

    # 1. 读取文件内容
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        print(f"成功读取文件，大小: {len(file_data)} 字节")
        log_event(f"读取文件 {file_path}，大小 {len(file_data)} 字节")
    except FileNotFoundError:
        print(f"错误: 找不到文件 {file_path}")
        return

    # 2. 分块
    chunks, N = split_file_into_chunks(file_data, lmin, lmax, seed)
    print(f"\n文件被分成 {N} 块")
    log_event(f"分块完成，共 {N} 块")

    # 3. 连接服务器
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # TCP套接字
        sock.connect((server_ip, server_port))  # ip和端口  sock相当于互相联系的电话，内置各种联系和使用方法
        print(f"已连接到服务器 {server_ip}:{server_port}")
        log_event(f"连接到服务器 {server_ip}:{server_port}")
    except Exception as e:
        print(f"连接服务器失败: {e}")
        return
    # socket.AF_INET	使用 IPv4 地址
    # socket.SOCK_STREAM	使用 TCP 协议
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # sock 是一个对象，类型是 socket.socket
    # 这个对象内置了这些方法：
    sock.connect()   # 连接服务器
    sock.send()      # 发送数据
    sock.recv()      # 接收数据
    sock.close()     # 关闭连接
    sock.bind()      # 绑定地址（服务器用）
    sock.listen()    # 监听（服务器用）
    sock.accept()    # 接受连接（服务器用）
    """



    # 4. 发送Initialization 报文 (Type=1)  告诉服务器type=1,N=5,准备开始发送了
    # struct.pack("!HI") 的含义：
    # ! 表示网络字节序（大端）
    # H 表示无符号短整数 (2字节) -> Type
    # I 表示无符号整数 (4字节) -> N
    # 原始数据: Type=1, N=5  打包后: b'\x00\x01\x00\x00\x00\x05'-->这就是print出的init_packet
    init_packet = struct.pack("!HI", 1, N)  # 把type=1和N这两个整数转换成二进制字节，方便网络传输。
    sock.send(init_packet)  # send需要bytes类型
    print(f"发送 Initialization: N={N}")
    log_event(f"发送 Initialization 报文: Type=1, N={N}")

    # 5. 接收 agree 报文 (Type=2)
    agree_data = sock.recv(2)  # agree报文只有2字节 任务书规定 agree 报文只有 Type 字段（2字节）recv中的是字节数
    agree_type, = struct.unpack("!H", agree_data)  # 将字节重新转化为整数类型  2字节--> 整数2  因为是元组所以要逗号
    print(f"收到 agree 报文: Type={agree_type}")
    log_event(f"收到 agree 报文: Type={agree_type}")

    if agree_type != 2:
        print("错误: 服务器没有正确响应")
        return
    """
    发送端：                接收端：
    send(6字节)  ──────→   recv(2)  ← 只取前2字节
                          recv(4)  ← 再取后4字节
    如果 recv(100)：程序会一直等，直到收到100字节（永远不会来）
    """

    # 6. 逐块发送 reverseRequest 并接收 reverseAnswer
    reversed_chunks = []  # 存放所有反转后的数据

    for i, chunk in enumerate(chunks, start=1):  # enumerate是一个遍历方法，遍历每个数据块，i从start=1开始计数
        chunk_length = len(chunk)

        # 发送 reverseRequest (Type=3)
        # 格式: Type(2B) + Length(4B) + Data
        request_packet = struct.pack("!HI", 3, chunk_length) + chunk  # 打包时要有头部和数据块，2+4+chunk，都是type类型
        sock.send(request_packet)
        print(f"发送 reverseRequest 第 {i} 块: {chunk_length} 字节")
        log_event(f"发送 reverseRequest 报文: 块={i}, Type=3, Length={chunk_length}")

        # 接收 reverseAnswer (Type=4)
        # 先接收头部 (Type 2字节 + Length 4字节 = 6字节)
        header = sock.recv(6)
        if len(header) < 6:
            print(f"错误: 接收头部失败")
            break

        resp_type, resp_length = struct.unpack("!HI", header)

        # 再接收实际数据
        reversed_data = sock.recv(resp_length)

        # 将反转后的数据解码为字符串（假设是英文文本）
        reversed_text = reversed_data.decode('ascii', errors='ignore') # 以ASCII解码，忽略无法解码的字节
        print(f"收到 reverseAnswer 第 {i} 块: {reversed_text[:50]}..." if len(
            reversed_text) > 50 else f"收到 reverseAnswer 第 {i} 块: {reversed_text}")
        log_event(f"收到 reverseAnswer 报文: 块={i}, Type=4, Length={resp_length}")

        reversed_chunks.append(reversed_text)

    # 7. 生成完整的反转文件
    output_path = "reversed_output.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in reversed(reversed_chunks):  # ← 反向遍历
            f.write(chunk)

    print(f"\n完成！反转后的文件已保存为: {output_path}")
    log_event(f"反转完成，输出文件: {output_path}")

    # 8. 关闭连接
    sock.close()
    print("连接已关闭")


def main():
    """命令行入口"""
    # 通过命令行传参
    # 如 python tcp_client.py 127.0.0.1 8888 input.txt 50 100 42
    if len(sys.argv) != 7:
        print("使用方法:")
        print("  python tcp_client.py <服务器IP> <端口> <文件路径> <Lmin> <Lmax> <随机种子>")
        print("示例:")
        print("  python tcp_client.py 127.0.0.1 8888 input.txt 50 100 42")
        sys.exit(1)
    # 对参数进行匹配 ↓
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    file_path = sys.argv[3]
    lmin = int(sys.argv[4])
    lmax = int(sys.argv[5])
    seed = int(sys.argv[6])

    tcp_client(server_ip, server_port, file_path, lmin, lmax, seed)


if __name__ == "__main__":
    main()