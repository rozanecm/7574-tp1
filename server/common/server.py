import socket
import logging
import time
import os

from common.node_manager import NodeManager


class Server:
    def __init__(self, port, listen_backlog, keep_server_running, admin_to_nodes_manager_msgs_queue, logger_queue):
        logging.info("initializing server")
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self.keep_server_running = keep_server_running
        self.admin_to_nodes_manager_msgs_queue = admin_to_nodes_manager_msgs_queue
        self.logger_queue = logger_queue

    def run(self):
        """
        Dummy Server loop

        Server that accepts a new connections and establishes a
        communication with a client. After client with communication
        finishes, servers starts to accept new connections again
        """
        while self.keep_server_running.value:
            logging.info("in server loop")
            # TODO aceptar en thread pool.
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
        socket_for_client, client_ip = self._server_socket.accept()
        logging.info('Got connection from {}'.format(client_ip))
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
            self.__handle_msg(msg.decode(), client_sock)
            # client_sock.sendall("Your Message has been received: {}\n".format(msg).encode('utf-8'))
        except OSError:
            logging.info("Error while reading socket {}".format(client_sock))
        finally:
            client_sock.close()

    def __handle_msg(self, msg: str, client_sock):
        split_msg = msg.split(":")
        if split_msg[0] == 'reg':
            self._register_client(split_msg[1])
        elif split_msg[0] == 'unreg':
            self._unregister_client(split_msg[1])
        elif split_msg[0] == 'query':
            logging.info("[admin msg]: query: {}".format(msg))
            self._query_client(split_msg[1], client_sock)
        elif msg == "shutdown":
            self.keep_server_running.value = False
            self.admin_to_nodes_manager_msgs_queue.put(msg)
            return
        else:
            logging.info("message header unknown")

    def _register_client(self, msg: str):
        logging.info("reg msg: {}".format(msg))
        split_msg = msg.split()
        # split msg:
        #       - 0: node
        #       - 1: port
        #       - 2: path
        #       - 3: freq
        self.admin_to_nodes_manager_msgs_queue.put("reg")
        self.admin_to_nodes_manager_msgs_queue.put([split_msg[0], int(split_msg[1]), split_msg[2], int(split_msg[3])])

    def _unregister_client(self, msg: str):
        logging.info("unreg msg: {}".format(msg))
        split_msg = msg.split()
        # split msg:
        #       - 0: node
        #       - 1: path
        self.admin_to_nodes_manager_msgs_queue.put("unreg")
        self.admin_to_nodes_manager_msgs_queue.put(split_msg[0], split_msg[1])

    def _query_client(self, msg: str, client_sock):
        logging.info("query msg: {}".format(msg))
        split_msg = msg.split()
        # split msg:
        #       - 0: node
        #       - 1: path
        #     TODO impl
        self.send_tgz_to_admin(client_sock, self.get_filepath_last_backup(split_msg[0], split_msg[1]))

    def get_filepath_last_backup(self, node_name, path):
        filename_to_match = node_name + "-" + path.replace("/", "-")
        logging.info("partial filename_to_match: {}".format(filename_to_match))
        files_for_this_backup = []
        logging.info("ls: {}".format(os.listdir()))
        for element in os.listdir():
            if element[:len(filename_to_match)] == filename_to_match:
                files_for_this_backup.append(element)
        logging.info("all files for this node, path: {}".format(files_for_this_backup))
        if files_for_this_backup:
            filepath_last_backup = self.get_latest_from_paths(files_for_this_backup)
            logging.info("filepath last backup: {}".format(filepath_last_backup))
            return filepath_last_backup
        else:
            return ""

    def get_latest_from_paths(self, paths):
        largest_path = ""
        largest_number = 0
        for path in paths:
            if int(''.join(filter(str.isdigit, path))) > largest_number:
                largest_number = int(''.join(filter(str.isdigit, path)))
                largest_path = path
        return largest_path

    def send_tgz_to_admin(self, client_sock, path_to_tgz):
        logging.info("sending tgz to admin")
        try:
            with open(path_to_tgz, "rb") as f:
                chunk = f.read(1024)
                while chunk:
                    client_sock.sendall(chunk)
                    chunk = f.read(1024)
        except:
            client_sock.sendall("No file found")
        logging.info("before shutdown after sending tgz")
        client_sock.shutdown(socket.SHUT_RDWR)
        logging.info("before close after sending tgz")
        client_sock.close()
