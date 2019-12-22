import os
import mimetypes
from datetime import datetime

from httpserver.TCPServer import TCPServer
from httpserver.HTTPConnectionHandler import HTTPConnectionHandler, HTTPResponse, BadRequestError, RecvTimeoutError
from httpserver.utils import debugprint

def get_last_modified_formatted_string(requested_path):
    timestamp = os.path.getmtime(requested_path)
    time_format = '%a, %d %b %y %T %z'
    return datetime.fromtimestamp(timestamp).strftime(time_format)

class HTTPServer(TCPServer):
    """
    Wrapper for TCPServer that implements HTTP protocol
    """
    def __init__(self, port):
        # We support only GET, so use daemon threads
        TCPServer.__init__(self, port, self.handle_tcp_connection, use_daemon_threads=True)
        self.request_handler_func = None
        self.serve_docroot = None
        self.serve_config = {}

    def handle_tcp_connection(self, connection, client_address):
        http_connection = HTTPConnectionHandler(connection, client_address)
        try:
            while True:
                request = http_connection.get_request()
                if not request: 
                    break
                # TODO: Allow choosing to handle request or serve file
                self.__serve_file(request, http_connection)
                if not request.is_connection_keep_alive(): 
                    break
        except RecvTimeoutError:
            if len(http_connection.unprocessed_data) > 0:
                # There's an incomplete request on timeout
                http_connection.send_response(HTTPResponse.client_error_400())
        except BadRequestError as e:
            debugprint('Bad Request Error', e)
            http_connection.send_response(HTTPResponse.client_error_400())
        finally:
            http_connection.close()

    def register_handler(self, request_handler_func):
        """
        Register a function to handle a request.
        """
        self.request_handler_func = request_handler_func

    def serve(self, docroot, serve_config={}):
        """
        Serve files from `docroot`.
        Can pass config as dict with keys mapped to html pages, i.e.:
        {
            'index': 'custom_index.html',
            '400': '400.html',
            '404': '404.html'
        }
        Note that paths must be relative to `docroot`. Also 'index.html' is the default mapping for 'index'.
        """
        self.serve_docroot = docroot
        self.serve_config = serve_config

    def get_index_html_path(self):
        """
        Get index.html (or any from config) path.
        """
        return os.path.join('/', self.serve_config.get('index', 'index.html'))
    
    def get_abspath_relative_to_docroot(self, path):
        assert self.serve_docroot is not None, 'Must setup `serve_docroot` first.'
        return os.path.abspath(os.path.join(self.serve_docroot, path))

    def __serve_file(self, request, http_connection):
        """
        Return HTTPResponse for serving file.
        """
        requested_path = self.get_index_html_path() if request.path == '/' else request.path
        if requested_path.startswith('/'): 
            requested_path = requested_path[1:]
        abs_requested_path = self.get_abspath_relative_to_docroot(requested_path)
        abs_docroot_path = os.path.abspath(self.serve_docroot)
        del requested_path
        # Won't serve out of docroot
        if not abs_requested_path.startswith(abs_docroot_path):
            if '400' in self.serve_config:
                http_connection.send_response(HTTPResponse.client_error_400())
                http_connection.send_body(self.get_abspath_relative_to_docroot(self.serve_config['400']))
            else:
                http_connection.send_response(HTTPResponse.client_error_400())
            return
        # File not exists
        if not os.path.exists(abs_requested_path):
            if '404' in self.serve_config:
                http_connection.send_response(HTTPResponse.not_found_404())
                http_connection.send_body(self.get_abspath_relative_to_docroot(self.serve_config['404']))
            else:
                http_connection.send_response(HTTPResponse.not_found_404())
            return
        mimetype, _ = mimetypes.guess_type(abs_requested_path)
        file_size = os.path.getsize(abs_requested_path)
        last_modified_time = get_last_modified_formatted_string(abs_requested_path)

        response_headers = {
            'Content-Type': mimetype,
            'Content-Length': file_size,
            'Last-Modified': last_modified_time
        }
        http_connection.send_response(HTTPResponse(200, headers=response_headers))
        n_bytes_sent = http_connection.send_file(abs_requested_path)
        assert n_bytes_sent == file_size, 'Incomplete file sent.'