import socket
import threading
import time
import struct
import sys
import Client

MAGIC_COOKIE = 0xabcddcba
MESSAGE_TYPE_OFFER = 0x2
MESSAGE_TYPE_REQUEST = 0x3
MESSAGE_TYPE_PAYLOAD = 0x4


class Client:

    def __init__(self, file_size, TCP_connections, UDP_connections):
        self.file_size = file_size
        self.tcp_connections = TCP_connections
        self.udp_connections = UDP_connections
        self.server_ip = None
        self.tcp_port = None
        self.udp_port = None

    def listen_for_offers(self):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind(('', 13117))  # Bind to the broadcast port
        while True:
            message, addr = udp_socket.recvfrom(1024)
            magic_cookie, message_type, tcp_port, udp_port = struct.unpack('!IBHH', message)
            if magic_cookie == MAGIC_COOKIE and message_type == MESSAGE_TYPE_OFFER:
                print(f"Received offer from {addr[0]}: TCP port {tcp_port}, UDP port {udp_port}")
                self.server_ip = addr[0]
                self.tcp_port = tcp_port
                self.udp_port = udp_port
                udp_socket.close()
                break

    def tcp_transfer(self, connection_id):
        print(f"Starting TCP transfer #{connection_id} to {self.server_ip}:{self.tcp_port}")
        try:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((self.server_ip, self.tcp_port))
            tcp_socket.sendall(f"{self.file_size}\n".encode())

            start_time = time.time()
            total_received = 0

            while True:
                data = tcp_socket.recv(1024)
                if not data:
                    break
                total_received += len(data)

            end_time = time.time()
            total_time = end_time - start_time
            speed = (total_received * 8) / total_time  # Convert bytes to bits and divide by time
            print(
                f"TCP transfer #{connection_id} finished, total time: {total_time:.2f} seconds, total speed: {speed:.2f} bits/second\n")
        except Exception as e:
            print(f"TCP transfer #{connection_id} error: {e}")
        finally:
            tcp_socket.close()

    def udp_transfer(self, connection_id):
        print(f"Starting UDP transfer #{connection_id} to {self.server_ip}:{self.udp_port}")
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Send REQUEST packet
            request_packet = struct.pack('!IBQ', MAGIC_COOKIE, MESSAGE_TYPE_REQUEST, self.file_size)
            udp_socket.sendto(request_packet, (self.server_ip, self.udp_port))

            start_time = time.time()
            total_received = 0
            received_segments = set()  # Keep track of unique segment indices
            total_segments_reported = None

            while True:
                udp_socket.settimeout(1)
                try:
                    data, _ = udp_socket.recvfrom(4096)
                except socket.timeout:
                    # 1-second timeout with no data means server has stopped sending
                    break
                # followed by the payload data
                if len(data) < 21:
                    # Not a valid packet, ignore
                    continue

                cookie, msg_type, total_segs, curr_seg = struct.unpack('>IBQQ', data[:21])
                payload = data[21:]

                if cookie != MAGIC_COOKIE or msg_type != MESSAGE_TYPE_PAYLOAD:
                    # Not a valid payload packet
                    continue

                total_received += len(payload)

                # Keep track of the total number of segments
                total_segments_reported = total_segs
                # Add this segment index to the set
                received_segments.add(curr_seg)

            end_time = time.time()
            total_time = end_time - start_time

            # Calculate speed in bits/second
            speed = (total_received * 8) / total_time if total_time > 0 else 0

            # If the server told us how many segments it intended to send:
            if total_segments_reported is not None:
                num_segments_received = len(received_segments)
                # Compute packet loss
                num_segments_lost = total_segments_reported - num_segments_received
                packet_loss_percent = (num_segments_lost / total_segments_reported) * 100
                success_percent = 100 - packet_loss_percent
            else:
                # Fallback if, for some reason, we never got a valid packet with total_segments
                success_percent = 100  # We cannot measure properly, assume no loss

            print(
                f"UDP transfer #{connection_id} finished, total time: {total_time:.2f} seconds, "
                f"total speed: {speed:.2f} bits/s, "
                f"percentage of packets received successfully: {success_percent:.2f}%\n"
            )
        except Exception as e:
            print(f"UDP transfer #{connection_id} error: {e}")
        finally:
            udp_socket.close()

    def speed_test(self):
        print("Starting speed test...")
        threads = []

        # Launch TCP threads
        for i in range(1, self.tcp_connections + 1):
            t = threading.Thread(target=self.tcp_transfer, args=(i,))
            threads.append(t)
            t.start()

        # Launch UDP threads
        for i in range(1, self.udp_connections + 1):
            t = threading.Thread(target=self.udp_transfer, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        print("All transfers complete, listening to offer requests")

    def run(self):
        self.listen_for_offers()
        self.speed_test()
