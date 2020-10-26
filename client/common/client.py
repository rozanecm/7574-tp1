import os
import socket
import logging
import tarfile
import time
import hashlib

from concurrent.futures import ThreadPoolExecutor


class Client:
    def __init__(self, port, client_id, listen_backlog, keep_client_running):
        logging.info("initializing client")
        self.id = client_id
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self.keep_client_running = keep_client_running
        self.executor = ThreadPoolExecutor(5)

    def run(self):
        """
        Dummy Server loop

        Server that accepts a new connections and establishes a
        communication with a client. After client with communication
        finishes, servers starts to accept new connections again
        """

        while self.keep_client_running.value:
            logging.info("in server loop")
            client_sock = self.__accept_new_connection()
            self.__handle_client_connection(client_sock)
            # self.executor.submit(self.__handle_client_connection, client_sock)

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
            if msg.decode() == "shutdown":
                self.keep_client_running.value = False
                return
            else:
                self.executor.submit(self.__handle_msg, client_sock, msg.decode())
        except OSError:
            logging.info("Error while reading socket {}".format(client_sock))
        finally:
            client_sock.close()

    def __handle_msg(self, client_sock, msg: str):
        # Msg is a path to backup + hash in format
        # path:md5
        logging.info("msg received at client handling msg: {}".format(msg))
        path, md5 = msg.split(":")
        path_to_tgz = self.compress_path(path)
        logging.info("new md5:      {}".format(self.md5Checksum(path_to_tgz)))
        logging.info("received md5: {}".format(md5))
        if self.md5Checksum(path_to_tgz) != md5:
            client_sock.sendall("updates needed: y".encode())
            self.send_tgz_to_client(client_sock, path_to_tgz)
            self.remove_local_tgz(path_to_tgz)
        else:
            logging.info("won't send tgz")
            client_sock.sendall("updates needed: n".encode())
            logging.info("before shutdown")
            client_sock.shutdown(socket.SHUT_RDWR)
            logging.info("before close")
            client_sock.close()

    def compress_path(self, path):
        """compress path to tgz"""
        # src: https://stackoverflow.com/questions/28176904/how-to-make-a-tar-file-backup-of-a-directory-in-python
        archive_name = os.path.join(os.getcwd(), path.replace("/", "-"))
        # go back one path because we're in volume/client/id
        path = os.path.realpath(os.path.join("../..", path))

        with tarfile.open(archive_name, mode='w:gz') as archive:
            logging.info("in with statement")
            archive.add(path, recursive=True)
        logging.info("successfully created tgz file")
        return archive_name

    def md5Checksum(self, filepath):
        m = hashlib.md5()
        archive = tarfile.open(filepath, 'r:gz')
        for member in archive.getmembers():
            if member.isfile():
                with archive.extractfile(member) as target:
                    while True:
                        data = target.read(8192)
                        if not data:
                            break
                        m.update(data)
        return m.hexdigest()

    def send_tgz_to_client(self, client_sock, path_to_tgz):
        logging.info("sending tgz to client")
        with open(path_to_tgz, "rb") as f:
            chunk = f.read(1024)
            while chunk:
                client_sock.sendall(chunk)
                chunk = f.read(1024)
        logging.info("before shutdown after sending tgz")
        client_sock.shutdown(socket.SHUT_RDWR)
        logging.info("before close after sending tgz")
        client_sock.close()

    def remove_local_tgz(self, path):
        logging.info("removing tmp file")
        os.remove(path)
        logging.info("after removing tmp file")
