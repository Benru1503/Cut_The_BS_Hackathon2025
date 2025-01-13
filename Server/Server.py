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
    """
    A server that listens on TCP and UDP sockets and broadcasts availability (offers).
    This server:
      - Periodically broadcasts its TCP and UDP ports via UDP (offer packets).
      - Accepts TCP connections to transfer random data to the client.
      - Accepts UDP requests to transfer random data in chunks to the client.
    """

    def __init__(self, broadcast_ip, broadcast_port, tcp_port, udp_port):
        """
        Initializes the Server with broadcast parameters and binds TCP & UDP sockets.

        :param broadcast_ip: IP address to use for broadcasting (e.g., '255.255.255.255').
        :param broadcast_port: Port number to use for broadcasting.
        :param tcp_port: Port number to listen on for TCP connections (0 = ephemeral).
        :param udp_port: Port number to listen on for UDP (0 = ephemeral).
        """
        self.broadcast_ip = broadcast_ip
        self.broadcast_port = broadcast_port

        # Create and bind TCP socket
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(('', tcp_port))
        self.tcp_socket.listen(5)
        self.actual_tcp_port = self.tcp_socket.getsockname()[1]

        # Create and bind UDP socket
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('', udp_port))
        self.actual_udp_port = self.udp_socket.getsockname()[1]

        host_ip = socket.gethostbyname(socket.gethostname())
        print(f"Server started on host IP: {host_ip}")
        print(f"  Broadcasting to {self.broadcast_ip}:{self.broadcast_port}")
        print(f"  Listening TCP on port {self.actual_tcp_port}")
        print(f"  Listening UDP on port {self.actual_udp_port}")

    def start(self):
        """
        Starts the server by launching threads for:
          1) Broadcasting UDP offers.
          2) Accepting incoming TCP connections.
          3) Handling UDP requests on the main thread.
        """
        # Start broadcasting offers in a separate thread
        threading.Thread(target=self._broadcast_offers, daemon=True).start()

        # Start accepting TCP connections in a separate thread
        threading.Thread(target=self._accept_tcp_connections, daemon=True).start()

        # Main thread will handle incoming UDP requests
        self._handle_udp_requests()

    def _broadcast_offers(self):
        """
        Periodically sends broadcast UDP packets containing:
          - A magic cookie.
          - A message type (offer).
          - The server's TCP port.
          - The server's UDP port.
        This runs in a loop and sleeps for BROADCAST_ANNOUNCEMENT_TIME between sends.
        """
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            offer_packet = struct.pack(
                '>IBHH',
                MAGIC_COOKIE,
                MESSAGE_TYPE_OFFER,
                self.actual_udp_port,
                self.actual_tcp_port
            )
            # Broadcast offer packet
            self.udp_socket.sendto(offer_packet, (self.broadcast_ip, self.broadcast_port))
            time.sleep(BROADCAST_ANNOUNCEMENT_TIME)

    def _accept_tcp_connections(self):
        """
        Accepts incoming TCP connections in a loop.
        For each new client, starts a dedicated thread to handle communication.
        """
        while True:
            client_socket, client_addr = self.tcp_socket.accept()
            threading.Thread(
                target=self._handle_tcp_client,
                args=(client_socket, client_addr),
                daemon=True
            ).start()

    def _handle_tcp_client(self, client_socket: socket.socket, client_addr):
        """
        Handles an individual TCP client by reading the requested size (in bytes),
        then sending back the requested amount of random bytes.

        :param client_socket: The accepted client socket.
        :param client_addr: The client's address (IP, port tuple).
        """
        try:
            data = b""

            # Read until newline is found or until connection is broken
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
            # Send exactly the requested number of bytes in 4096-byte chunks
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
        """
        Waits for incoming UDP requests. A valid request packet contains:
          - Magic cookie
          - Message type (request)
          - File size (Q = 8 bytes)
        Upon receiving a valid request, spawns a thread to send random data over UDP..
        """
        while True:
            try:
                data, client_addr = self.udp_socket.recvfrom(2048)
                # Check if request packet is too short
                if len(data) < 13:
                    continue

                cookie, msg_type, file_size = struct.unpack('>IBQ', data[:13])
                # Validate magic cookie and message type
                if cookie != MAGIC_COOKIE or msg_type != MESSAGE_TYPE_REQUEST:
                    continue

                print(f"[UDP] Client {client_addr} requested {file_size} bytes")

                # Spawn a thread to send the data so we don't block receiving further requests
                threading.Thread(
                    target=self._send_udp_data,
                    args=(file_size, client_addr),
                    daemon=True
                ).start()

            except Exception as e:
                print(f"[UDP] Error receiving requests: {e}")

    def _send_udp_data(self, file_size: int, client_addr):
        """
        Sends random data to the client in chunks, each with a header:
          - Magic cookie
          - Message type (payload)
          - Total segments
          - Current segment index
        :param file_size: The total number of bytes to be sent.
        :param client_addr: The client's address for UDP transmission.
        """
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

            # Send header + random data payload
            self.udp_socket.sendto(header + payload, client_addr)
            bytes_sent += chunk_len

        print(f"[UDP] Sent {bytes_sent} bytes to {client_addr}")


def main():
    """
    Main entry point for the SpeedTest Server. Parses command-line arguments,
    creates a Server instance, and starts the server.
    """
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
