#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import struct
import sys
import time
import random


def log_event(message):
    """记录日志"""
    with open("udp_run_log.txt", "a", encoding="utf-8") as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\n")
    print(f"[LOG] {message}")


def calculate_student_id(last_4_digits):
    """计算 StudentID = 学号后4位 XOR 0x5A3C"""
    return last_4_digits ^ 0x5A3C


def split_data(data, min_len, max_len):
    """将数据分成多个包（40-80字节）"""
    random.seed(42)  # 固定种子，便于调试
    packets = []
    pos = 0
    total = len(data)

    while pos < total:
        remaining = total - pos
        if remaining <= max_len:
            packets.append(data[pos:])
            break
        pkt_len = random.randint(min_len, max_len)
        packets.append(data[pos:pos + pkt_len])
        pos += pkt_len

    return packets


def udp_client(server_ip, server_port, file_path, timeout_ms=300):
    """UDP 客户端主函数"""

    print("=" * 50)
    print("UDP 客户端启动（模拟可靠传输）")
    print(f"服务器: {server_ip}:{server_port}")
    print(f"文件: {file_path}")
    print("=" * 50)

    # 清空日志
    open("udp_run_log.txt", "w").close()

    # 1. 读取文件
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
        print(f"读取文件成功，大小: {len(file_data)} 字节")
        log_event(f"读取文件 {file_path}，大小 {len(file_data)} 字节")
    except FileNotFoundError:
        print(f"错误: 找不到文件 {file_path}")
        return

    # 2. 分包（每包40-80字节）
    packets = split_data(file_data, 40, 80)
    total_packets = len(packets)
    print(f"分成 {total_packets} 个数据包")
    log_event(f"分包完成，共 {total_packets} 包")

    # 3. 创建 UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout_ms / 1000.0)  # 设置超时时间 毫秒转化为秒，设置最多等待时间
    # AF_INET	IPv4
    # SOCK_DGRAM	UDP 协议

    # 4. 连接建立
    print("\n--- 连接建立阶段 ---")
    student_id_raw = 2501  # 替换成你的学号后4位
    student_id = calculate_student_id(student_id_raw)

    # 发送连接请求
    conn_req = struct.pack("!HH", 1, student_id)  # type和id进行编码 一个H两字节
    sock.sendto(conn_req, (server_ip, server_port)) # 将编码好的字节头发送到服务器，后面的元组告诉要发送的地址
    log_event(f"发送连接请求: Type=1, StudentID={student_id} (原始={student_id_raw})")
    print(f"发送连接请求，StudentID={student_id}")

    # 等待连接确认
    try:
        ack_data, _ = sock.recvfrom(1024)  # 括号内缓冲区大小，即最多接收的字节数，一般设置1024
        ack_type, = struct.unpack("!H", ack_data[:2])
        if ack_type == 2:
            log_event(f"收到连接确认: Type=2")
            print("连接建立成功！")
        else:
            print("连接建立失败")
            return
    except socket.timeout:
        print("连接超时，服务器无响应")
        log_event("连接超时")
        return

    # 5. 数据传输阶段（GBN 协议）
    print("\n--- 数据传输阶段 ---")

    base = 0  # 窗口基序号，即最早的已发送未确认的包序号
    next_seq = 0  # 下一个要发送的序号  标记每个要发送的包 pkt发送时要带上seq序号
    window_size_bytes = 400  # 窗口大小（字节）  一次最多可发送的字节限额
    """
    一个一个传	发1→等ACK→发2→等ACK→发3...	 慢（网络空闲时间长）
    窗口批量传	发1、2、3、4、5 → 等ACK → 发6、7、8、9、10	 快（充分利用网络）
    简单理解：窗口就像一次性可以寄多个快递，不用等第一个签收再寄第二个。
    序号:     0    1    2    3    4    5    6    7    8    9
        │    │    │    │    │    │    │    │    │    │    │
    状态:    ✅   ✅   ⏳   ⏳   ⏳  ❌   ❌   ❌   ❌   ❌
        │    │    │    │    │    │
        └────┴────┴────┴────┴────┘
             窗口（400字节）   窗口内有五个，下一个第六个序号5在等待是因为窗口400字节，每个包大概80字节，最多能进五个       
    base = 2     ← 最早还没被确认的包（2号还没收到ACK）
    next_seq = 5 ← 下一个要发送的包（5号还没发）
    """

    # 记录每个包的信息
    sent_packets = {}  # seq -> (data, send_time, length)  字典，键是包的序号，值是数据，发送时间，长度
    acked = [False] * total_packets   # acked是标记列表，默认所有包没发送时全为False   用于标记哪些包已确认

    # 统计信息
    rtt_list = []   # rtt记录包数据发出到接收的往返时间
    retransmit_count = 0  # 重传次数
    total_sent = 0    # 总发送次数（包括重传）

    # 计算每个包的字节长度
    packet_lengths = [len(p) for p in packets]  # 遍历包列表，对每个包记录长度存到新列表中

    def can_send():
        """检查是否可以发送新包"""
        if next_seq >= total_packets:  # 下一个包的序号不能超过包的总数，>=因为包序号从0开始
            return False
        # 计算窗口内字节总数
        window_bytes = 0
        for i in range(base, next_seq):   # 从窗口基序号（最早未确认的包）遍历到下一个要传送的序号
            if not acked[i]:  # 如果没传过
                window_bytes += packet_lengths[i]  # 仍在当前窗口内但未确认的包的字节数累加
        return window_bytes + packet_lengths[next_seq] <= window_size_bytes  #返回False或True

    def send_packet(seq):
        """发送一个数据包"""
        nonlocal total_sent
        data = packets[seq]
        pkt = struct.pack("!H I H", 3, seq, len(data)) + data # packet(数据包) 报文头加数据的完整包裹
        send_time = time.time()
        sock.sendto(pkt, (server_ip, server_port))
        sent_packets[seq] = (data, send_time, len(data))  # 字典记录信息
        total_sent += 1
        log_event(f"发送数据包: seq={seq}, len={len(data)}")
        print(f"发送第 {seq} 包 (字节 {sum(packet_lengths[:seq])}~{sum(packet_lengths[:seq + 1]) - 1})")

    def handle_ack(ack_seq):  # ack_seq	服务器确认收到的序号	3（表示服务器已收到序号0、1、2、3）
        """处理确认"""
        nonlocal base, retransmit_count  # 告诉 Python，这里的 base 和 retransmit_count 不是本函数内的局部变量，
        # 而是外层函数（udp_client）中定义的变量。为什么需要：因为要在函数内修改它们。
        if ack_seq >= base and not acked[ack_seq]:   # 忽略已经确认的旧包和已标记确认的包避免重复确认
            # 计算 RTT
            if ack_seq in sent_packets:  # 字典
                _, send_time, _ = sent_packets[ack_seq]
                rtt = (time.time() - send_time) * 1000
                rtt_list.append(rtt)
                print(f"收到 ACK {ack_seq}，RTT={rtt:.2f}ms")
                log_event(f"收到 ACK: seq={ack_seq}, RTT={rtt:.2f}ms")

            # 累积确认
            for i in range(base, ack_seq + 1):
                if not acked[i]:
                    acked[i] = True
                    # 从 sent_packets 中删除已确认的包（可选）  已确认发送的包不需要再记录信息了
                    if i in sent_packets:
                        del sent_packets[i]

            # 移动窗口
            while base < total_packets and acked[base]:
                base += 1

    # 发送所有包
    while base < total_packets:
        # 发送窗口内的新包
        while can_send():  # 函数
            send_packet(next_seq)  # 函数
            next_seq += 1

        # 等待 ACK 或超时
        try:
            response, _ = sock.recvfrom(2048)
            if len(response) >= 6:
                resp_type, ack_seq = struct.unpack("!H I", response[:6])  # type和最大连续序号
                if resp_type == 4:
                    handle_ack(ack_seq)
        except socket.timeout:
            # 超时，重传所有未确认的包
            print("超时！重传未确认的包...")
            log_event("超时发生，开始重传")
            retransmit_count += 1

            for seq in range(base, next_seq):  # 遍历基序号到下一个要发送的序号，找到未确认的包重传（标记列表中为False）
                if not acked[seq]:
                    data, _, _ = sent_packets[seq]  # 直接接收原来保存到字典中的数据，方便重传
                    pkt = struct.pack("!H I H", 3, seq, len(data)) + data
                    sock.sendto(pkt, (server_ip, server_port))
                    sent_packets[seq] = (data, time.time(), len(data))
                    total_sent += 1
                    print(f"重传第 {seq} 包")
                    log_event(f"重传数据包: seq={seq}")

    # 6. 打印统计信息
    print("\n" + "=" * 50)
    print("传输完成！统计信息：")
    print("=" * 50)

    # 计算丢包率
    packet_loss_rate = (total_sent - total_packets) / total_sent * 100    # 总发送次数  包的总数
    print(f"原始包数: {total_packets}")
    print(f"实际发送次数（含重传）: {total_sent}")
    print(f"重传次数: {retransmit_count}")
    print(f"丢包率: {packet_loss_rate:.2f}%")

    # 计算 RTT 统计
    if rtt_list:
        avg_rtt = sum(rtt_list) / len(rtt_list)
        max_rtt = max(rtt_list)    # 最慢的一次传输花了多久，最大RTT
        min_rtt = min(rtt_list)

        # 计算标准差
        variance = sum((x - avg_rtt) ** 2 for x in rtt_list) / len(rtt_list)
        std_rtt = variance ** 0.5

        print(f"RTT 统计:")
        print(f"  最大: {max_rtt:.2f}ms")
        print(f"  最小: {min_rtt:.2f}ms")
        print(f"  平均: {avg_rtt:.2f}ms")
        print(f"  标准差: {std_rtt:.2f}ms")

    sock.close()
    print("\n连接关闭")


def main():
    if len(sys.argv) != 4:
        print("使用方法:")
        print("  python udp_client.py <服务器IP> <端口> <文件路径>")
        print("示例:")
        print("  python udp_client.py 127.0.0.1 8888 input.txt")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_port = int(sys.argv[2])
    file_path = sys.argv[3]

    udp_client(server_ip, server_port, file_path)


if __name__ == "__main__":
    main()