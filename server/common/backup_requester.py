import json
import os
import socket
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import socket
import re


class BackupRequester:
    def __init__(self, node_to_backup_queue_from_node_manager_to_backup_requester, logger_queue):
        self.node_to_backup_queue_from_node_manager_to_backup_requester = node_to_backup_queue_from_node_manager_to_backup_requester
        self.logger_queue = logger_queue

        self.executor = ThreadPoolExecutor(5)

    def run(self):
        logging.info("now in dir: {}".format(os.getcwd()))
        while True:
            logging.info("requesting backups...")
            new_node_to_backup = self.node_to_backup_queue_from_node_manager_to_backup_requester.get()
            if new_node_to_backup == "shutdown":
                break
            # self.request_backup_to_node(new_node_to_backup)
            self.executor.submit(self.request_backup_to_node, new_node_to_backup)
        logging.info("terminating backups requester...")

    def request_backup_to_node(self, node):
        """
        Each individual backup will be requested here.
        :param node: is fully described by dict with keys 'node', 'port', 'path', 'md5'
        :return:
        """
        filename = os.getcwd() + "/" + self.get_filename(node['node'], node['port'], node['path'],
                                                         node['last_file_path'])
        logging.info("will save tgz for node {}, path {} to {}".format(node['node'], node['path'], filename))
        s = socket.socket()
        logging.info("about to connect to {}, {}".format(node['node'], node['port']))
        s.connect((node['node'], node['port']))
        s.sendall("{}:{}\n".format(node['path'],
                                   node['md5']).encode())
        res = self.recv_node_msg(s)
        logging.info("res: {}".format(res))
        logging.info("res decoded: {}".format(res))
        if res == "updates needed: y":
            with open(filename, 'wb') as f:
                data_received = s.recv(1024)
                while data_received:
                    f.write(data_received)
                    data_received = s.recv(1024)
            self.log_action("New backup saved from node {}, path {}. File name: {}".format(node['node'], node['path'], filename))
        else:
            self.log_action("no need for update from node {}, path {}".format(node['node'], node['path']))
        s.close()
        logging.info("requesting backup to node {}".format(node))

    def recv_node_msg(self, s):
        total_length = len("updates needed: y")
        msg = b""
        while len(msg) < total_length:
            msg += s.recv(total_length)
            logging.info("partially received msg from socket: {}".format(msg.decode()))
        msg = msg.decode()
        logging.info("received msg from socket: {}".format(msg))
        return msg

    def get_filename(self, node_name, port, path, last_file_path):
        if last_file_path:
            filepath_prefix = node_name + "-" + path.replace("/", "-")
            return filepath_prefix + str(self.get_number_of_backup(last_file_path, filepath_prefix)) + ".tgz"
        else:
            return node_name + "-" + path.replace("/", "-") + "0.tgz"

    def get_number_of_backup(self, last_file_path, prefix):
        return int(last_file_path.split(prefix)[1].split(".tgz")[0]) + 1

    def log_action(self, msg):
        logging.info("will log msg: {}".format(msg))
        self.logger_queue.put(msg)
