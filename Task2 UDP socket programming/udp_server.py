#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import struct
import random
import time

# 模拟丢包率（20%）
DROP_RATE = 0.2


def calculate_student_id(last_4_digits):
    """计算 StudentID = 学号后4位 XOR 0x5A3C"""
    return last_4_digits ^ 0x5A3C


def verify_student_id(received_id, expected_last_4):
    """验证 StudentID 是否合法"""
    expected_id = calculate_student_id(expected_last_4)
    return received_id == expected_id


def udp_server(port, expected_last_4=2501):
    """UDP 服务器主函数"""

    print("=" * 50)
    print(f"UDP 服务器启动，监听端口: {port}")
    print(f"模拟丢包率: {DROP_RATE * 100}%")
    print("等待客户端连接...")
    print("=" * 50)
    # socket.AF_INET：使用 IPv4 地址（如 127.0.0.1）
    # socket.SOCK_DGRAM：使用 UDP 协议（无连接、不可靠）
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))

    # 记录客户端地址（连接建立后）
    client_addr = None
    expected_student_id = calculate_student_id(expected_last_4)

    # 接收缓冲区（用于乱序处理）
    recv_buffer = {}
    expected_seq = 0

    try:
        while True:   # 循环处理
            try:
                data, addr = sock.recvfrom(2048)  # 最多接收 2048 字节，同时返回发送方地址 addr

                if len(data) < 2:
                    continue

                pkt_type = struct.unpack("!H", data[:2])[0]  # 取解包后的type [0]因为unpack返回元组
                # 连接请求
                if pkt_type == 1 and len(data) >= 4:
                    student_id = struct.unpack("!H", data[2:4])[0]
                    print(f"[连接请求] 来自 {addr}, StudentID={student_id}")

                    if student_id == expected_student_id:
                        # 验证成功，发送确认
                        ack_pkt = struct.pack("!H", 2)   # type
                        sock.sendto(ack_pkt, addr)  # 返回type类型，确认链接
                        client_addr = addr
                        print(f"[连接确认] 发送给 {addr}，StudentID 验证通过")
                    else:
                        print(f"[拒绝] StudentID 验证失败: {student_id} != {expected_student_id}")

                # 数据报文
                # │Type=3 │  Seq    │ Length  │   Data   │
                # │ 2字节  │  4字节   │ 2字节    │  变长    │
                elif pkt_type == 3 and len(data) >= 8:
                    if client_addr is None or addr != client_addr:  # 未链接或不是发送地址不是连接客户端的消息则跳过
                        continue

                    # 模拟丢包
                    if random.random() < DROP_RATE:  # 如果随机数（0-1的小数）小于丢包率，就执行丢包
                        print(f"[丢包] 模拟丢包，seq 被丢弃")
                        continue  # continue直接跳过了，不回复ACK，就是丢包过程(退出这个大elif)

                    # 继续运行
                    seq, length = struct.unpack("!I H", data[2:8])
                    payload = data[8:8 + length]  # 从8开始取，即真正的文件数据

                    print(f"[收到] 数据包 seq={seq}, len={length}")

                    # 存入缓冲区 UDP 数据包可能乱序到达，需要缓冲区重新排序。 可能客户端发送包顺序为0123，网络传输时可能为2031
                    # 不排序会造成期望序号与发送序号不同，造成不接收数据丢失
                    recv_buffer[seq] = payload  # 按序号存储数据  recv_buffer是一个字典

                    # 累积确认：发送最大连续序号
                    while expected_seq in recv_buffer: # 只要缓冲区里有我期望的下一个序号，就继续往后数,如果没有就是没收到
                        expected_seq += 1

                    # 发送确认
                    ack_seq = expected_seq - 1 # 防止包乱序，确认的包序号始终比expected_seq少1
                    ack_pkt = struct.pack("!H I", 4, ack_seq)
                    sock.sendto(ack_pkt, addr)
                    print(f"[发送] ACK {ack_seq}")

                    # 可选：如果接收完所有数据，可以保存到文件
                    # 这里简单打印接收进度
                    if len(recv_buffer) % 10 == 0:
                        print(f"[进度] 已收到 {len(recv_buffer)} 个数据包")

                else:
                    print(f"[未知报文] Type={pkt_type}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"[错误] {e}")

    except KeyboardInterrupt:
        print("\n[关闭] 服务器被用户中断")
    finally:
        sock.close()
        print("[关闭] 服务器已关闭")


def main():
    import sys

    if len(sys.argv) != 2:
        print("使用方法:")
        print("  python udp_server.py <端口号>")
        print("示例:")
        print("  python udp_server.py 8888")
        sys.exit(1)

    port = int(sys.argv[1])
    udp_server(port)


if __name__ == "__main__":
    main()