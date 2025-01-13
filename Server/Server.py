import socket
import threading
import time
import struct
import random
import argparse

MAGIC_COOKIE = 0xabcddcba
MESSAGE_TYPE_OFFER = 0x2
MESSAGE_TYPE_REQUEST = 0x3
MESSAGE_TYPE_PAYLOAD = 0x4

BROADCAST_ANNOUNCEMENT_TIME = 1.0


class Server:

    def __init__(self, broadcast_ip, broadcast_port, tcp_port, udp_port):
        self.broadcast_ip = broadcast_ip
        self.broadcast_port = broadcast_port

        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(('', tcp_port))
        self.tcp_socket.listen(5)
        self.actual_tcp_port = self.tcp_socket.getsockname()[1]

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('', udp_port))
        self.actual_udp_port = self.udp_socket.getsockname()[1]

        host_ip = socket.gethostbyname(socket.gethostname())
        print(f"Server started on host IP: {host_ip}")
        print(f"  Broadcasting to {self.broadcast_ip}:{self.broadcast_port}")
        print(f"  Listening TCP on port {self.actual_tcp_port}")
        print(f"  Listening UDP on port {self.actual_udp_port}")

    def start(self):
        threading.Thread(target=self._broadcast_offers, daemon=True).start()

        threading.Thread(target=self._accept_tcp_connections, daemon=True).start()

        self._handle_udp_requests()

    def _broadcast_offers(self):
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            offer_packet = struct.pack(
                '>IBHH',
                MAGIC_COOKIE,
                MESSAGE_TYPE_OFFER,
                self.actual_tcp_port,
                self.actual_udp_port
            )
            self.udp_socket.sendto(offer_packet, (self.broadcast_ip, self.broadcast_port))
            time.sleep(BROADCAST_ANNOUNCEMENT_TIME)

    def _accept_tcp_connections(self):
        while True:
            client_socket, client_addr = self.tcp_socket.accept()
            threading.Thread(
                target=self._handle_tcp_client,
                args=(client_socket, client_addr),
                daemon=True
            ).start()

    def _handle_tcp_client(self, client_socket: socket.socket, client_addr):
        try:
            data = b""

            while True:
                chunk = client_socket.recv(1024)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            requested_str = data.decode().strip()
            requested_size = int(requested_str)
            print(f"[TCP] Client {client_addr} requested {requested_size} bytes")

            bytes_left = requested_size
            buffer_size = 4096
            while bytes_left > 0:
                chunk_size = min(buffer_size, bytes_left)
                random_chunk = random.randbytes(chunk_size)
                client_socket.sendall(random_chunk)
                bytes_left -= chunk_size

        except Exception as e:
            print(f"[TCP] Error with client {client_addr}: {e}")
        finally:
            client_socket.close()

    def _handle_udp_requests(self):
        while True:
            try:
                data, client_addr = self.udp_socket.recvfrom(2048)
                if len(data) < 13:
                    continue

                cookie, msg_type, file_size = struct.unpack('>IBQ', data[:13])
                if cookie != MAGIC_COOKIE or msg_type != MESSAGE_TYPE_REQUEST:
                    continue

                print(f"[UDP] Client {client_addr} requested {file_size} bytes")

                threading.Thread(
                    target=self._send_udp_data,
                    args=(file_size, client_addr),
                    daemon=True
                ).start()

            except Exception as e:
                print(f"[UDP] Error receiving requests: {e}")

    def _send_udp_data(self, file_size: int, client_addr):
        chunk_data_size = 1024
        total_segments = (file_size + chunk_data_size - 1) // chunk_data_size

        bytes_sent = 0
        for segment_idx in range(total_segments):
            start_index = segment_idx * chunk_data_size
            end_index = min(start_index + chunk_data_size, file_size)
            chunk_len = end_index - start_index

            header = struct.pack(
                '>IBQQ',
                MAGIC_COOKIE,
                MESSAGE_TYPE_PAYLOAD,
                total_segments,
                segment_idx
            )

            payload = random.randbytes(chunk_len)

            self.udp_socket.sendto(header + payload, client_addr)
            bytes_sent += chunk_len

        print(f"[UDP] Sent {bytes_sent} bytes to {client_addr}")


def main():
    parser = argparse.ArgumentParser(
        description="SpeedTest Server - broadcasts offers and handles TCP/UDP transfers."
    )
    parser.add_argument('--broadcast-ip', type=str, default='255.255.255.255',
                        help='IP address for UDP broadcast (default: 255.255.255.255)')
    parser.add_argument('--broadcast-port', type=int, default=13117,
                        help='Port for broadcasting UDP offers (default: 13117)')
    parser.add_argument('--tcp-port', type=int, default=0,
                        help='TCP port to listen on, 0 for ephemeral (default: 0)')
    parser.add_argument('--udp-port', type=int, default=0,
                        help='UDP port to listen on, 0 for ephemeral (default: 0)')
    args = parser.parse_args()

    server = Server(
        broadcast_ip=args.broadcast_ip,
        broadcast_port=args.broadcast_port,
        tcp_port=args.tcp_port,
        udp_port=args.udp_port
    )
    server.start()


if __name__ == "__main__":
    main()
