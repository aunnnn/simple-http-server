# From TCP to HTTP: An Introduction to Web Server
A simple HTTP server built directly from socket APIs. 

Run:
```python
python demo.py
```
Then go to `localhost:8080`.

Change `sample_docroot` in `demo.py` to any other folder to serve from that root.

---

HTTP, TCP, Web server, Socket, etc. I've had some ideas but never knew a good way to wrap my head around it. We heard statements like "TCP is a transport layer" and "HTTP sits on top of TCP" and nod along, **but what do they actually mean though?**

In this guide I will show how to build a simple HTTP server on top of TCP via Socket programming.

## 1. TCP Server with Socket API
Socket programming is like a low-level tool for communicating with other computers via the internet. We will create [`TCPServer`](./httpserver/TCPServer.py) as a thin wrapper over the socket API to handle the details of creating and starting a TCP socket. We will have a while-True loop to wait for incoming connections from clients. Note that this part would be the lowest-level code we have.

Once there's a new connection, `socket.accept()` will unblock and return a newly created socket (we called it `connection` in code), we spawn a new thread to work on it. This way, the main thread can continue to focus on just accepting & spawning threads for new connections. After this point, server and client can communicate through `send()` and `recv()` methods of the socket API.

[Quick intro for socket programming at the bottom.](#brief-overview-of-socket-programming-and-tcp)

## 2. From TCP to HTTP
Next, we create [`HTTPServer`](./httpserver/HTTPServer.py) which extends `TCPServer` to make it *understand HTTP requests* and able to *send back HTTP responses* to the client via the socket. The meat of this work is in [`HTTPConnectionHandler`](./httpserver/HTTPConnectionHandler.py).

### 2.1 Make the Server Understand HTTP
To understand what someone's talking about on the internet, we just have to know how to *detect* and *parse* the HTTP language. `HTTPConnectionHandler` does just that, though only a very small subset of it.

#### Detecting/Delimiting a Request
One of the things this class handles is *detecting a complete request*, i.e. find where it starts and ends. Since the socket API is just all about reliable streams of data, it doesn't care about the semantic of that data. In addition, each request *can have variable length* so we can't just pull off 1024 bytes from the socket and call it a complete request.

First recall the format of HTTP request and response, which involves 4 sections: 
1. Start-line, 
2. Key-Value Headers,
3. `\r\n` (Indicate the end of meta-information)
4. Body (Optional, i.e. in POST request, or response)

Each line in section 1 and 2 end with `\r\n` (called "Carriage Return Line Feed" or CRLF). If there's a body, it immediately follows that CRLF in section 3, **without any extra `\r\n` after it.**

Below is a sample request (sent by `curl localhost:8080 -v`):
```
GET / HTTP/1.1\r\n
Host: localhost:8080\r\n
User-Agent: curl/7.64.0\r\n
Accept: */*\r\n
\r\n
```
New lines above are just for readability. Also, there's no body here since it's a GET request.

Now here's the catch: *There are always two `\r\n`'s at the end of the meta-information part.* Using this fact, we can continuously pull data from the socket, until we find `\r\n\r\n`, where we will cut off a substring up until that point:
```python
while True:
    if '\r\n\r\n' in self.unprocessed_data:
        end_of_request_index = self.unprocessed_data.index('\r\n\r\n')
        # Cut off a request
        request_string = self.unprocessed_data[:end_of_request_index]
        # Delete from buffer
        self.unprocessed_data = self.unprocessed_data[end_of_request_index+len('\r\n\r\n'):]
        # Return parsed request
        return self.__parse_request(request_string)

    # Receive 1024 bytes from the socket at a time
    data = self.connection.recv(1024).decode('utf-8')
    if not data:
        break
    # Concat
    self.unprocessed_data += data
```
More code for the detection part is at `HTTPConnectionHandler.__detect_request_from_socket`.

More details about the format of HTTP Messages is [here.](https://developer.mozilla.org/en-US/docs/Web/HTTP/Messages)

#### Parsing a Request
Now we have a string that *potentially* represents a request, and we just have to parse it into a HTTP request according to the protocol. This deals with details like splitting lines with `\r\n`, validating that the start-line should be in the form of `GET /cat.png HTTP/1.1`, the header should be in the form of `Key: Value`, etc. At any point if there's something wrong in the format, we just raise `400 Bad Request`. See `HTTPConnectionHandler.__parse_request`.

### 2.2 Make the Server Talks HTTP
Here we have to **respond** back in the same HTTP language. We use the same format as explained before.

Some of the things that we implement: 
- Send back `400 Bad Request` when the format of request from client is wrong.
- Send back `404 Not Found` when we can't find something the client wants.
- Provide `Content-Type` and `Content-Length` when we send response back with a body*.

The last bit is important. Since we're serving some files, there will be a body which is binary data. It could be an image, a HTML file, or whatever. **How do client know where is the end of the body?** Remember there's no special delimiter like `\r\n` at the end. On the other hand, *having one is not a good idea*. Whatever a special delimiter we choose, we can't have that in the data we will send, else the client doesn't know the actual ending of the data.

**Here comes the `Content-Length` header.** It tells you how many bytes the body has so that the client knows that 1. there's a body following the header section, and 2. how long that body is, so it cuts off the request at the right point. See `HTTPServer.__serve_file` for more details.

---
## Brief Overview of Socket Programming and TCP

Socket provides a set of *low-level* APIs that allow two computers to talk to each other. A regular web or mobile engineer may never need to know about it, but whenever two machines communicate on the internet, it always involves sockets under the hood. Socket has support for TCP (or UDP) where we can build something like HTTP upon it.

Imagine socket as a data pipe, where both ends (client and server) will be used to communicate *real-time*. Each end is uniquely identified with an IP address and a port number, i.e. (`127.0.0.1`, `8080`). A server's port number for HTTP is agreed by everyone as `80`, just so the browser knows where to contact. A client's port number is not important and can be anything (that is not reserved by the OS).

As a side note: Previously when I heard about socket, I always thought it is something *special* and high-level. Something that is different from what I did in everyday coding tasks, which just involves sending out API requests and parsing JSON responses. However it is the **opposite**. Socket's always been sitting underneath, abstracted away from my everyday tasks the entire time. It is **TCP**, or a transport layer inside all the networking libraries I've been using!

There will be some formality to set up the socket. The process will be different for setting up a passive socket (server) that waits for incoming connections, and an active socket (client) that initiates the outgoing connection.

To start a listening socket for server:
- `socket()`: create a socket
- `bind()`: bind to a socket address
- `listen()`: start to accept connections

Then, we accept each connection by calling this in a loop:
- `accept()`: returns a new connection (*blocks* until there's one)

For client it is simpler:
- `socket()`: create a socket
- `connect()`: connect to a remote socket at given address

After this, client and server communicate with `send()` and `recv()`. The sender will put the data on the pipe (or buffer) with `send()` and the receiver will pull it out with `recv()`. Your Operating System then continues the job of actually sending it.

How much you send or receive are independent. Sender may send 1 MB, and you may receive one byte each time with `recv(1)`. But that would require a million of `recv()` calls...

I imagine `send` as `append` and `recv` as `pop` in a FIFO queue. I.e. you CANNOT view data at arbitrary index. You see the data only when you remove it from the pipe. You also CANNOT undo sending or receiving. What is sent is sent for good.

Recall that TCP provides a reliable *stream* of data transfer between two hosts. This means *all the data* will be ensured to arrive *in the order* that it is sent. If we specify the TCP option when creating a socket, then we are sure that `recv()` and `send()` deliver data in the original order that they are executed.

A great mini-book for this is [Beej's Guide to Network Programming](https://beej.us/guide/bgnet/). This [Socket Programming in Python](https://realpython.com/python-sockets) article is also good. The [official doc](https://docs.python.org/3/library/socket.html) is always helpful.
