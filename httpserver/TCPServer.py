import socket
import sys
import threading
from httpserver.utils import debugprint

class TCPServer:
    """
    TCP server, which handles reliable streams of data between client and server in socket. 
    We can build HTTP layer on top of this via `connection_handler_func`.

    If use daemon threads, those threads will be killed automatically when the main app exits.
    Probably simpler when this is a read-only server, i.e. no writes, otherwise it could end up in inconsistent state.
    """
    def __init__(self, port, connection_handler_func, max_number_of_active_threads=None, use_daemon_threads=False):
        self.host = ''
        self.port = port
        self.connection_handler_func = connection_handler_func
        self.use_daemon_threads = use_daemon_threads

        self.socket = None

        # Number of unaccepted new connections on the backlog queue to the specified port (if more it refuses)
        # If we handle each new connection fast (i.e. spawn a new thread for it and move on), this should be fine.
        self.connection_backlog_queue_size = 5

        # Maximum number of active threads
        if max_number_of_active_threads is not None:
            self.semaphore = threading.BoundedSemaphore(value=max_number_of_active_threads)
        else:
            self.semaphore = None

        self.__threads = {}

    def __find_socket_to_bind_and_listen(self):
        address_filter = (
            self.host,
            self.port,
            socket.AF_UNSPEC,   # either IPv4/6
            socket.SOCK_STREAM, # TCP (i.e. instead of UDP)
            0,
            socket.AI_PASSIVE   # For listening & bind; Wait for incoming connection
        )
        # `getaddrinfo` returns eligible address(es) that match the filter
        # Use one that works
        for res in socket.getaddrinfo(*address_filter):
            af, socktype, proto, _, sa = res
            try:
                s = socket.socket(af, socktype, proto)
            except OSError:
                s = None
                continue
            try:
                # Allow reuse local addresses
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(sa)
                s.listen(self.connection_backlog_queue_size)
            except OSError as e:
                debugprint('OSError', e)
                s.close()
                s = None
                continue
            break
        if s is None:
            debugprint('Could not open socket')
            sys.exit(1)
        debugprint('Opened a socket.')
        return s

    def serve_forever(self):
        """
        Open socket and start receiving connections. 
        At each receive, spawn a new thread to handle the request.
        """
        self.socket = self.__find_socket_to_bind_and_listen()

        # Now socket is opened, wait for incoming connection from client...
        while True:
            # New connection found, accept and spawn a new thread to handle it.
            connection, client_address = self.socket.accept()
            debugprint('Accepted new client', client_address)
            t = threading.Thread(target=self.__handle_new_connection_thread, args=(connection, client_address))
            t.daemon = self.use_daemon_threads
            t.start()
            if not self.use_daemon_threads:
                self.__threads[t.ident] = t

    def __handle_new_connection_thread(self, connection, client_address):
        if self.semaphore: self.semaphore.acquire()
        try:
            self.connection_handler_func(connection, client_address)
        finally:
            if self.semaphore: self.semaphore.release()
            # Clean-up
            if not self.use_daemon_threads:
                del self.__threads[threading.get_ident()]

    def server_close(self):
        self.socket.close()
        if not self.use_daemon_threads:
            for t in self.__threads.values():
                t.join()