import socket
import logging
import time

from common.node_manager import NodeManager


class Server:
    def __init__(self, port, listen_backlog, keep_server_running, node_manager_queue):
        logging.info("initializing server")
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self.keep_server_running = keep_server_running
        self.node_manager_queue = node_manager_queue

    def run(self):
        """
        Dummy Server loop

        Server that accepts a new connections and establishes a
        communication with a client. After client with communication
        finishes, servers starts to accept new connections again
        """

        while self.keep_server_running.value:
            logging.info("in server loop")
            # time.sleep(1)
            client_sock = self.__accept_new_connection()
            self.__handle_client_connection(client_sock)
        logging.info("terminating main server")

    def __accept_new_connection(self):
        """
        Accept new connections

        Function blocks until a connection to a client is made.
        Then connection created is printed and returned
        """

        # Connection arrived
        logging.info("Proceed to accept new connections")
        socket_for_client, client_IP = self._server_socket.accept()
        logging.info('Got connection from {}'.format(client_IP))
        return socket_for_client

    def __handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and close the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            msg = client_sock.recv(1024).rstrip()
            logging.info(
                'Message received from connection {}. Msg: {}'
                    .format(client_sock.getpeername(), msg))
            self.__handle_msg(msg.decode())
            # client_sock.send("Your Message has been received: {}\n".format(msg).encode('utf-8'))
        except OSError:
            logging.info("Error while reading socket {}".format(client_sock))
        finally:
            client_sock.close()


    def __handle_msg(self, msg: str):
        if msg == "shutdown":
            self.keep_server_running.value = False
            self.node_manager_queue.put(msg)
            return
        split_msg = msg.split('-')
        if split_msg[0] == "admin":
            logging.info("msg from admin")
            self._handle_admin_msg(split_msg[1])
        elif split_msg[0] == "client":
            logging.info("msg from client")
            self._handle_client_msg(split_msg[1])
        else:
            logging.info("message header unknown")

    def _handle_admin_msg(self, msg: str):
        split_msg = msg.split()
        # logging.info("handling admin msg:", msg)
        if split_msg[0] == 'reg' or split_msg[0] == 'unreg':
            logging.info("[admin msg]: register")
            self.node_manager_queue.put(split_msg[0])
            self.node_manager_queue.put(msg)
            # self._register_client(msg)
        elif split_msg[0] == 'query':
            logging.info("[admin msg]: query")
            self._query_client(msg)
        else:
            logging.info("Unknown command received from admin.")

    def _register_client(self, msg: str):
        logging.info("reg msg: {}".format(msg))
        split_msg = msg.split()
        # split msg:
        #       - 0: reg
        #       - 1: node
        #       - 2: port
        #       - 3: path
        #       - 4: freq
        # self._node_manager.register_node(split_msg[1], int(split_msg[2]), split_msg[3], int(split_msg[4]))
        self.node_manager_queue.put("reg")
        self.node_manager_queue.put([split_msg[1], int(split_msg[2]), split_msg[3], int(split_msg[4])])

    def _unregister_client(self, msg: str):
        logging.info("unreg msg: {}".format(msg))
        split_msg = msg.split()
        # split msg:
        #       - 0: unreg
        #       - 1: node
        #       - 2: path
        self.node_manager_queue.put("unreg")
        self.node_manager_queue.put(split_msg[1], split_msg[2])

    def _query_client(self, msg: str):
        logging.info("query msg: {}".format(msg))
        split_msg = msg.split()
        # split msg:
        #       - 0: query
        #       - 1: node
        #       - 2: path
        self._node_manager.query_node(split_msg[1], split_msg[2])

    def _handle_client_msg(self, msg: str):
        # TODO implementattion
        pass
