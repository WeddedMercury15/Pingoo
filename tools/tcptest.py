import sys
import socket
import time
import argparse
import signal
import os

# Add this global flag variable to track whether Ctrl+C was used or not
ctrl_c_used = False

def custom_gaierror(msg):
    class CustomGaiError(socket.gaierror):
        def __init__(self, message):
            super().__init__(-1, message)

    raise CustomGaiError(msg)

def signal_handler(sig, frame):
    global ctrl_c_used
    ctrl_c_used = True

def resolve_ip(hostname, force_ipv4=False):
    try:
        # 默认使用IPv4进行DNS查询
        family = socket.AF_INET if force_ipv4 else socket.AF_INET6

        # 使用系统默认的DNS服务器进行查询
        addr_info = socket.getaddrinfo(hostname, None, family)
        ip = addr_info[0][4][0]  # 获取IP地址

        return ip

    except socket.gaierror:
        raise ValueError(f"TCPing 请求找不到主机 {hostname}。请检查该名称，然后重试.")

def tcping(domain, port, request_nums, force_ipv4, force_ipv6, timeout=1000, continuous_ping=False, ttl=64):
    try:
        ip = None

        if force_ipv4:
            # 如果使用 -4 参数，只使用IPv4进行DNS查询
            ip = resolve_ip(domain, force_ipv4=True)
        elif force_ipv6:
            # 如果使用 -6 参数，只使用IPv6进行DNS查询
            ip = resolve_ip(domain, force_ipv4=False)
        else:
            # 否则，根据系统的网络配置来选择DNS查询方式
            try:
                # 尝试使用IPv4进行DNS查询
                ip = resolve_ip(domain, force_ipv4=True)
            except ValueError:
                # 如果IPv4查询失败，则使用IPv6进行DNS查询
                ip = resolve_ip(domain, force_ipv4=False)

        print(f"\n正在 TCPing {domain}:{port} [{ip}:{port}] 具有 32 字节的数据:")
        request_num = 1
        response_times = []
        received_count = 0
        lost_count = 0

        try:
            while continuous_ping or request_num <= request_nums:
                if ctrl_c_used:  # Check if Ctrl+C was used
                    break

                start_time = time.time()
                try:
                    with socket.create_connection((ip, port), timeout=timeout / 1000) as conn:
                        # Set the TTL value before sending the ping request
                        conn.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
                        
                        end_time = time.time()
                        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                        response_times.append(response_time)
                        print(f"来自 {ip}:{port} 的回复: 字节=32 时间={response_time:.0f}ms TTL={ttl}")
                        received_count += 1
                        request_num += 1
                        time.sleep(1)
                except socket.timeout:
                    print("请求超时。")
                    lost_count += 1
                    request_num += 1
                    time.sleep(1)
                except (OSError, ConnectionRefusedError) as e:
                    if isinstance(e, OSError) and e.errno == 10049:
                        print("请求超时。")
                        lost_count += 1
                        request_num += 1
                        time.sleep(1)
                    else:
                        print(f"无法连接到 {ip}:{port}。")
                        lost_count += 1
                        request_num += 1
                        time.sleep(1)

        except KeyboardInterrupt:
            pass

        packet_loss_rate = (lost_count / request_num) * 100 if request_num > 0 else 0.0
        avg_delay = sum(response_times) / received_count if received_count > 0 else 0.0
        min_delay = min(response_times) if received_count > 0 else 0.0
        max_delay = max(response_times) if received_count > 0 else 0.0

        print(f"\n{ip}:{port} 的 TCPing 统计信息:")
        print(f"    数据包: 已发送 = {request_num - 1}, 已接收 = {received_count}，丢失 = {lost_count} ({packet_loss_rate:.1f}% 丢失)")

        if received_count > 0:
            print("往返行程的估计时间(以毫秒为单位):")
            print(f"    最短 = {min_delay:.0f}ms，最长 = {max_delay:.0f}ms，平均 = {avg_delay:.0f}ms")
        else:
            print("请求全部超时，无法计算往返行程时间.")

        if ctrl_c_used:  # Only print "Control-C" if Ctrl+C was used
            print("Control-C")

    except ValueError as e:
        print(e)

def main():
    script_name = os.path.basename(sys.argv[0])  # 获取脚本或可执行文件名称

    parser = argparse.ArgumentParser(description=f"{script_name} - 使用 TCP 协议检查目标主机端口的可达性。",
                                    formatter_class=argparse.RawDescriptionHelpFormatter,
                                    epilog="示例:\n"
                                            f"{script_name} yohoky.com 80\n"
                                            f"{script_name} yohoky.com 80 -d 1.1.1.1\n"
                                            f"{script_name} yohoky.com 80 -n 10 -w 500\n"
                                            f"{script_name} yohoky.com 80 -4\n"
                                            f"{script_name} yohoky.com 80 -6")

    parser.add_argument("domain", help="要 TCPing 的目标主机名。")
    parser.add_argument("port", type=int, help="目标主机的端口号。")
    parser.add_argument("-n", dest="request_nums", metavar="count", type=int, default=4, help="要发送的回显请求数。")
    parser.add_argument("-d", dest="dns_server", metavar="DNS_server", default=None, help="自定义 DNS 服务器地址。")
    parser.add_argument("-w", dest="timeout", metavar="timeout", type=int, default=1000, help="等待每次回复的超时时间(毫秒)。")
    parser.add_argument("-4", dest="force_ipv4", action="store_true", help="强制使用 IPv4。")
    parser.add_argument("-6", dest="force_ipv6", action="store_true", help="强制使用 IPv6。")
    parser.add_argument("-t", dest="continuous_ping", action="store_true", help="Ping 指定的主机，直到停止。\n若要查看统计信息并继续操作，请键入 Ctrl+Break； \n若要停止，请键入 Ctrl+C。")
    parser.add_argument("-i", dest="ttl", metavar="TTL", type=int, default=64, help="指定发送的TCP包的生存时间（TTL）值。")

    args = parser.parse_args()

    try:
        if args.request_nums < 1:
            args.request_nums = 4

        tcping(args.domain, args.port, args.request_nums, args.force_ipv4, args.force_ipv6, args.timeout, args.continuous_ping, args.ttl)

    except ValueError as e:
        print(e)

if __name__ == '__main__':
    # 设置 SIGINT 的信号处理程序 (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    main()
