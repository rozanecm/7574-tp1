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
    def __init__(self, new_backup_path_queue_frm_backup_requester_to_nodes_manager, node_to_backup_queue_from_node_manager_to_backup_requester):

        self.new_backup_path_queue_from_backup_requester_to_nodes_manager = new_backup_path_queue_frm_backup_requester_to_nodes_manager
        self.node_to_backup_queue_from_node_manager_to_backup_requester = node_to_backup_queue_from_node_manager_to_backup_requester

        self.executor = ThreadPoolExecutor(5)

    def run(self):
        logging.info("now in dir: {}".format(os.getcwd()))
        while True:
            logging.info("requesting backups...")
            # TODO completar esto
            new_node_to_backup = self.node_to_backup_queue_from_node_manager_to_backup_requester.get()
            if new_node_to_backup == "shutdown":
                break
            self.request_backup_to_node(new_node_to_backup)
        logging.info("terminating backups requester...")

    # def get_nodes_to_backup(self):
    #     self.backup_requester_pipe_end.send("nodes_to_backup")
    #     nodes_to_backup = self.backup_requester_pipe_end.recv()
    #     logging.info("backuper received nodes to backup: {}".format(nodes_to_backup))
    #     return nodes_to_backup

    # def request_backup(self, nodes_to_backup):
    #     """
    #     Backups are requested concurrently making use of the thread pool.
    #     :param nodes_to_backup:
    #     :return:
    #     """
    #     for node in nodes_to_backup:
    #         self.executor.submit(self.request_backup_to_node, node)

    def request_backup_to_node(self, node):
        """
        Each individual backup will be requested here.
        :param node: is fully described by dict with keys 'node', 'port', 'path', 'md5'
        :return:
        """
        # TODO request backup and save it to file
        filename = os.getcwd() + "/" + self.get_filename(node['node'], node['port'], node['path'], node['last_file_path'])
        logging.info("will save tgz to {}".format(filename))
        s = socket.socket()
        logging.info("about to connect to {}, {}".format(node['node'], node['port']))
        s.connect((node['node'], node['port']))
        s.send("{}:{}\n".format(node['path'],
                                node['md5']).encode())
        res = s.recv(len("updates needed: y")).rstrip()
        logging.info("res: {}".format(res))
        res = res.decode()
        logging.info("res decoded: {}".format(res))
        if res == "updates needed: y":
            with open(filename, 'wb') as f:
                data_received = s.recv(1024)
                while data_received:
                    f.write(data_received)
                    data_received = s.recv(1024)
                self.log_action("file received")
            # self.new_backup_path_queue_from_backup_requester_to_nodes_manager.put((node, filename))
        else:
            self.log_action("no need for update")
        s.close()
        logging.info("requesting backup to node {}".format(node))

    def get_filename(self, node_name, port, path, last_file_path):
        if last_file_path:
            filepath_prefix = node_name + "-" + path.split("/")[0] + "-"
            return filepath_prefix + str(self.get_number_of_backup(last_file_path, filepath_prefix)) + ".tgz"
        else:
            return node_name + "-" + path.split("/")[0] + "-0.tgz"

    def get_number_of_backup(self, last_file_path, prefix):
        return int(last_file_path.split(prefix)[1].split(".tgz")[0])+1

    def log_action(self, msg):
        pass
#         TODO impl
