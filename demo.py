from httpserver.HTTPServer import HTTPServer
import signal
import sys

server = None

def signal_handler(signum, frame):
    if signum == signal.SIGINT:
        print('Closing server...')
        server.server_close()
        print('Server closed.')
        sys.exit()
    else:
        print('Other signal received', signum)

def on_request(request):
    print('Got request:', request)

if __name__ == "__main__":
    server = HTTPServer(8080)
    server.serve('sample_docroot', {
        '400': '400.html',
        '404': '404.html'
    })
    # Handle server close with ctrl+c in terminal
    signal.signal(signal.SIGINT, signal_handler)    
    # Start the server...
    server.serve_forever()