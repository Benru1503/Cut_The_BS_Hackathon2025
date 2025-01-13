from Client import Client


def get_file_size():
    """
    Repeatedly prompts the user for:
      1) Which units for file size (B, KB, MB, GB).
      2) The magnitude of the file size.
    Returns:
      (file_size_in_bytes, unit_option)
    """
    while True:
        try:
            file_units = int(input(
            """Enter file size units:
            1. B
            2. KB
            3. MB
            4. GB
            """))
            if not 1 <= file_units <= 4:
                raise ValueError
        except ValueError:
            print("Invalid input, try again.")
            continue

        try:
            file_size = int(input("Enter file size: "))
            if file_size <= 0:
                raise ValueError
            return file_size, file_units
        except ValueError:
            print("Invalid input, try again.")
            continue


def get_number_of_connections(connection_type):
    """
    Prompts the user to enter the number of connections for a given type (TCP or UDP).

    :param connection_type: String indicating whether it's 'TCP' or 'UDP'.
    :return: Number of connections as an integer.
    """
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
    """
    Gathers initial parameters (file size and number of connections for TCP/UDP)
    from user input.
    Returns:
      file_size_in_bytes, tcp_connections, udp_connections
    """
    file_size, file_units = get_file_size()
    file_size = file_size * (1024 ** (file_units - 1))
    tcp_connections = get_number_of_connections("TCP")
    udp_connections = get_number_of_connections("UDP")
    return file_size, tcp_connections, udp_connections


def run_program():
    """
    Repeatedly:
      - Acquires user input for file size, TCP & UDP connection counts.
      - Creates a Client instance and waits for offers, then runs speed tests..
    """
    file_size, tcp_connections, udp_connections = startup_state()
    client = Client(file_size, tcp_connections, udp_connections)
    while True:
        print("Waiting for offers...")
        client.run()
run_program()