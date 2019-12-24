import socket
from httpserver.utils import debugprint

class HTTPRequest:
    def __init__(self, command, path, headers):
        self.command = command
        self.path = path
        self.headers = headers
    
    def is_connection_keep_alive(self):
        return 'Connection' in self.headers and self.headers['Connection'] == 'keep-alive'

class HTTPResponse:
    
    CRLF = '\r\n'
    CODE_DESCRIPTION = {
        200: 'OK',
        400: 'Bad Request',
        404: 'Not Found'
    }

    def __init__(self, code, headers=None):
        self.code = code
        self.headers = headers

    def formatted_string(self):
        """
        Return a formatted response string to be sent via socket.
        """
        response_lines = [f'HTTP/1.1 {self.code} {self.CODE_DESCRIPTION[self.code]}']
        response_lines.append('Server: Too-simple-http-server')
        for key, value in self.headers.items():
            response_lines.append(f'{key}: {value}')
        return self.CRLF.join(response_lines) + (self.CRLF * 2)

    @staticmethod
    def client_error_400():
        return HTTPResponse(400, { 'Connection': 'close' })
    
    @staticmethod
    def not_found_404():
        return HTTPResponse(404, { 'Connection': 'close' })

class BadRequestError(Exception): pass
class RecvTimeoutError(Exception): pass

class HTTPConnectionHandler:
    """
    Detect & parse a HTTP request from socket. 
    """
    CRLF = '\r\n'
    END_OF_REQUEST = '\r\n\r\n'

    # How much to receive each time, 4096 recommended 
    # (Or adjust to a small number like 64 to test it.)
    buffer_size = 4096

    # How long to wait for each `recv()`
    recv_timeout = 3

    def __init__(self, connection, client_address):
        self.connection = connection
        self.client_address = client_address
        # We will do everything in str. It's inefficient but easier to understand.
        self.unprocessed_data = ''

    def get_request(self):
        """
        Return a detected HTTP request. Will block until it finds a complete request.
        """
        try:
            request = self.__detect_request_from_socket()
        except:
            raise
        return request

    def send_response(self, response):
        """
        Send HTTP response to client.
        """
        response_string = response.formatted_string()
        result = self.connection.sendall(bytes(response_string, 'utf-8'))
        assert result is None, 'Incomplete file sent.'

    def send_file(self, file_path):
        total_bytes_sent = 0
        with open(file_path, 'rb') as f:
            total_bytes_sent = self.connection.sendfile(f)
        return total_bytes_sent

    def close(self):
        self.connection.close()
        debugprint('Closed the socket', self.client_address)

    def __detect_request_from_socket(self):
        """
        Detect one complete HTTP request from the data stream
        """
        try:
            # How long to wait for `recv`
            self.connection.settimeout(self.recv_timeout)
            request_string = None
            while True:
                # If we find a complete request, we break the loop
                if self.END_OF_REQUEST in self.unprocessed_data:
                    end_of_request_index = self.unprocessed_data.index(self.END_OF_REQUEST)
                    # Cut-off a complete request
                    request_string = self.unprocessed_data[:end_of_request_index]
                    # Delete from buffer
                    self.unprocessed_data = self.unprocessed_data[end_of_request_index+len(self.END_OF_REQUEST):]
                    # Return parsed request
                    return self.__parse_request(request_string)

                # Receive data from the client socket as str
                data = self.connection.recv(self.buffer_size).decode('utf-8')
                if not data: 
                    debugprint('No more data from client')
                    break
                # Aggregate data
                self.unprocessed_data += data
        except socket.timeout:
            raise RecvTimeoutError()
        return None

    def __parse_request(self, request_string):
        """
        Parse a request string into actual HTTP request.
        """
        lines = request_string.split(self.CRLF)
        # i.e. 'GET /index.html HTTP/1.1'
        headline = lines[0]
        headline_components = headline.split(' ')
        if len(headline_components) != 3:
            raise BadRequestError('Headline must have 3 parts: ' + headline)

        # Parse headline
        command, resource_path, http_version = headline_components
        if command != 'GET':
            raise BadRequestError('Only GET is supported: ' + command)
        if http_version != 'HTTP/1.1':
            raise BadRequestError('Only HTTP/1 is supported: ' + http_version)

        # Parse key-value headers
        headers = {}
        required_keys = {'Host'} # specify required header(s) here
        for line in lines[1:]:
            key_value = line.split(': ')
            if len(key_value) != 2:
                raise BadRequestError('Malformed key-value header: ' + line)
            key, value = key_value
            headers[key] = value
        if len(headers.keys() & required_keys) < len(required_keys):
            raise BadRequestError('Required headers: ' + ', '.join(required_keys - headers.keys()))
        return HTTPRequest(command, resource_path, headers)