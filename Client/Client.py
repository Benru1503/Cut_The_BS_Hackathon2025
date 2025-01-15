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
    """
    A client that:
      - Waits for a UDP broadcast offer from the server.
      - Retrieves the server's IP, TCP port, and UDP port.
      - Initiates TCP transfers (requesting random data) and measures speed.
      - Initiates UDP transfers (requesting random data) and measures speed, packet loss, etc.
    """

    def __init__(self, file_size, TCP_connections, UDP_connections):
        """
        Initializes the Client with:
          - The file size to request in bytes.
          - The number of TCP connections to open.
          - The number of UDP connections to open.

        :param file_size: Total file size (in bytes) to request.
        :param TCP_connections: How many simultaneous TCP connections to open.
        :param UDP_connections: How many simultaneous UDP connections to open.
        """
        self.file_size = file_size
        self.tcp_connections = TCP_connections
        self.udp_connections = UDP_connections
        self.server_ip = None
        self.tcp_port = None
        self.udp_port = None

    def listen_for_offers(self):
        """
        Listens on UDP port 13117 for broadcast offers from the server.
        Once an offer is received and validated, closes the socket and
        stores the server IP address and ports..
        """
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to the broadcast port
        udp_socket.bind(('', 13117))
        while True:
            message, addr = udp_socket.recvfrom(1024)
            magic_cookie, message_type, udp_port, tcp_port = struct.unpack('!IBHH', message)
            # Validate the magic cookie and message type
            if magic_cookie == MAGIC_COOKIE and message_type == MESSAGE_TYPE_OFFER:
                print(f"Received offer from {addr[0]}: TCP port {tcp_port}, UDP port {udp_port}")
                self.server_ip = addr[0]
                self.tcp_port = tcp_port
                self.udp_port = udp_port
                udp_socket.close()
                break

    def tcp_transfer(self, connection_id):
        """
        Performs a single TCP transfer to measure speed.
        Connects to the server's TCP port, requests the file size, and
        receives random data until the server stops sending.

        :param connection_id: Identifier for this TCP connection.
        """
        print(f"Starting TCP transfer #{connection_id} to {self.server_ip}:{self.tcp_port}")
        try:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((self.server_ip, self.tcp_port))
            # Send requested file size as a string, ended with newline
            tcp_socket.sendall(f"{self.file_size}\n".encode())

            start_time = time.time()
            total_received = 0

            # Receive data until the server closes the connection
            while True:
                data = tcp_socket.recv(1024)
                if not data:
                    break
                total_received += len(data)

            end_time = time.time()
            total_time = end_time - start_time
            # Compute speed in bits per second
            speed = (total_received * 8) / total_time
            print(
                f"TCP transfer #{connection_id} finished, total time: {total_time:.2f} seconds, total speed: {speed:.2f} bits/second\n")
        except Exception as e:
            print(f"TCP transfer #{connection_id} error: {e}")
        finally:
            tcp_socket.close()

    def udp_transfer(self, connection_id):
        """
        Performs a single UDP transfer to measure speed and packet loss.
        Sends a request packet (with magic cookie, message type, and file size)
        then reads the received data until it times out, calculating statistics.

        :param connection_id: Identifier for this UDP connection.
        """
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

                # Validate minimum length for the header
                if len(data) < 21:
                    # Not a valid packet, ignore
                    continue

                cookie, msg_type, total_segs, curr_seg = struct.unpack('>IBQQ', data[:21])
                payload = data[21:]

                # Validate cookie and message type
                if cookie != MAGIC_COOKIE or msg_type != MESSAGE_TYPE_PAYLOAD:
                    continue

                total_received += len(payload)
                total_segments_reported = total_segs
                received_segments.add(curr_seg)

            end_time = time.time()
            total_time = end_time - start_time

            # Calculate speed in bits/second
            speed = (total_received * 8) / total_time if total_time > 0 else 0

            # If the server indicated how many segments it intended to send:
            if total_segments_reported is not None:
                num_segments_received = len(received_segments)
                num_segments_lost = total_segments_reported - num_segments_received
                packet_loss_percent = (num_segments_lost / total_segments_reported) * 100
                success_percent = 100 - packet_loss_percent
            else:
                # If we never got a valid packet with total_segments
                success_percent = 100

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
        """
        Conducts the speed test by launching multiple threads:
          - For each TCP connection, starts a thread to do a TCP transfer.
          - For each UDP connection, starts a thread to do a UDP transfer.
        Waits for all threads to complete.
        """
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
        """
        Main client workflow:
          - Listen for server offers (broadcast).
          - Once an offer is received, run a speed test (TCP & UDP).
        """
        self.listen_for_offers()
        self.speed_test()
