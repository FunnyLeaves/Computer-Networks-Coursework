#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import struct
import threading


def reverse_bytes(data):
    """
    反转数据

    参数:
        data: bytes 类型的数据

    返回:
        反转后的 bytes
    """
    return data[::-1]


def handle_client(conn, client_address):
    """
    处理单个客户端的连接

    参数:
        conn: 与客户端连接的socket对象
        client_address: 客户端地址
    """
    print(f"[新连接] 客户端 {client_address} 已连接")

    try:
        # 1. 接收 Initialization 报文 (6字节)
        init_data = conn.recv(6)
        if len(init_data) < 6:
            print(f"[错误] 客户端 {client_address} 发送的初始化报文不完整")
            return

        pkt_type, N = struct.unpack("!HI", init_data)
        print(f"[收到] 客户端 {client_address}: Initialization, Type={pkt_type}, N={N}")

        # 2. 发送 agree 报文 (2字节)
        agree_packet = struct.pack("!H", 2)
        conn.send(agree_packet)
        print(f"[发送] 客户端 {client_address}: agree 报文")

        # 3. 循环处理每一块数据
        for i in range(N):
            # 接收 reverseRequest 头部 (6字节)
            header = conn.recv(6)
            if len(header) < 6:
                print(f"[错误] 客户端 {client_address} 块 {i + 1} 头部不完整")
                break

            req_type, length = struct.unpack("!HI", header)

            # 接收实际数据
            data = conn.recv(length)
            if len(data) < length:
                print(f"[错误] 客户端 {client_address} 块 {i + 1} 数据不完整")
                break

            print(f"[收到] 客户端 {client_address} 块 {i + 1}: 类型={req_type}, 长度={length}")
            print(f"       原始数据前50字节: {data[:50]}")

            # 反转数据
            reversed_data = reverse_bytes(data)
            print(f"[处理] 块 {i + 1} 反转完成")

            # 发送 reverseAnswer 报文
            # 格式: Type(2B) + Length(4B) + reverseData
            response_packet = struct.pack("!HI", 4, len(reversed_data)) + reversed_data
            conn.send(response_packet)
            print(f"[发送] 客户端 {client_address} 块 {i + 1}: reverseAnswer 回复")

        print(f"[完成] 客户端 {client_address} 所有块处理完毕")

    except Exception as e:
        print(f"[错误] 处理客户端 {client_address} 时发生异常: {e}")
    finally:
        conn.close()
        print(f"[断开] 客户端 {client_address} 连接已关闭")


def tcp_server(port):
    """
    TCP 服务器主函数

    参数:
        port: 监听的端口号
    """
    print("=" * 50)
    print(f"TCP 服务器启动，监听端口: {port}")
    print("等待客户端连接...")
    print("=" * 50)

    # 创建 TCP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # server_socket是主服务器socked只有一个，相当于前台 监听socked

    # 允许地址重用（方便调试，不用等端口释放）
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # 绑定到所有网络接口的指定端口
    server_socket.bind(("0.0.0.0", port))   # 0.0.0.0 8888 代表监听所有网卡
    # bind作用是将socked绑定到一个特定的IP和端口号上，告诉操作系统整个socked要用这个地址

    # 开始监听，最多允许5个等待连接  允许的最大连线
    server_socket.listen(5)

    client_count = 0

    try:
        while True:
            # 接受客户端连接 server_socked是一个主服务器，里面等待着很多申请，每次accept返回一个新的镜像socked进行服务
            conn, addr = server_socket.accept()
            client_count += 1
            print(f"\n[连接 {client_count}] 来自 {addr}")

            # 为每个客户端创建独立的线程
            client_thread = threading.Thread(
                target=handle_client,   # target调用什么函数
                args=(conn, addr),      # args传入的参数
                daemon=True  # 主线程退出时自动结束
            )
            client_thread.start()

            print(f"[状态] 当前活跃线程数: {threading.active_count() - 1}")

    except KeyboardInterrupt:
        print("\n[关闭] 服务器被用户中断")
    finally:
        server_socket.close()
        print("[关闭] 服务器已关闭")


def main():
    """命令行入口"""
    import sys

    if len(sys.argv) != 2:
        print("使用方法:")
        print("  python tcp_server.py <端口号>")
        print("示例:")
        print("  python tcp_server.py 8888")
        sys.exit(1)

    port = int(sys.argv[1])
    tcp_server(port)


if __name__ == "__main__":
    main()