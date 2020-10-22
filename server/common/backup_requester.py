import socket
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor


class BackupRequester:
    def __init__(self, keep_server_running, node_manager_queue, backup_requester_pipe_end):
        self.keep_server_running = keep_server_running
        self.node_manager_queue = node_manager_queue
        self.backup_requester_pipe_end = backup_requester_pipe_end
        self.executor = ThreadPoolExecutor(5)

    def run(self, time_interval=6.0):
        while self.keep_server_running.value:
            logging.info("requesting backups...")
            # TODO completar esto
            nodes_to_backup = self.get_nodes_to_backup()
            self.request_backups(nodes_to_backup)
            time.sleep(time_interval)
        logging.info("terminating backups requester...")

    def get_nodes_to_backup(self):
        self.backup_requester_pipe_end.send("nodes_to_backup")
        nodes_to_backup = self.backup_requester_pipe_end.recv()
        logging.info("backuper received nodes to backup: {}".format(nodes_to_backup))
        return nodes_to_backup

    def request_backups(self, nodes_to_backup):
        """
        Backups are requested concurrently making use of the thread pool.
        :param nodes_to_backup:
        :return:
        """
        for node in nodes_to_backup:
            self.executor.submit(self.request_backup_to_node, node)

    def request_backup_to_node(self, node):
        """
        Each individual backup will be requested here.
        :param node:
        :return:
        """
        logging.info("requesting backup to node {}".format(node))