from Client import Client

def get_file_size():
    while True:
        try:
            file_Units = int(input("""enter the desired file size units:
                                    1. B
                                    2. KB
                                    3. MB
                                    4. GB
                                    """))
            if not 1 <= file_Units <= 4:
                raise ValueError
        except ValueError:
            print("Invalid input, try again.")
            continue

        try:
            file_size = int(input("Enter file size: "))
            if file_size <= 0:
                raise ValueError
            return file_size, file_size
        except ValueError:
            print("Invalid input, try again.")
            continue


def get_number_of_connections(connection_type):
    while True:
        try:
            connections = int(input(f"Enter number of {connection_type} connections: "))
            if connections < 0:
                raise ValueError
            return connections
        except ValueError:
            print("Invalid input, try again.")
            continue


def startup_state():
    file_size, file_units = get_file_size()
    file_size = file_size * (1024 ** (file_units - 1))
    tcp_connections = get_number_of_connections("TCP")
    udp_connections = get_number_of_connections("UDP")
    return file_size, tcp_connections, udp_connections

# TODO: Check if this is the correct way to run the program --> busy-waiting?
def run_program():
    file_size, tcp_connections, udp_connections = startup_state()
    client = Client(file_size, tcp_connections, udp_connections)
    while True:
        client.run()

