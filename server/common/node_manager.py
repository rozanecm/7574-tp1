import json
import logging
import os
import threading
import time
import threading
import hashlib
import tarfile

MAX_NUM_OF_BACKUPS_TO_KEEP = 10


class NodeManager:
    def __init__(self, keep_server_running, admin_to_nodes_manager_msgs_queue,
                 node_to_backup_queue_from_node_manager_to_backup_requester):
        # Nodes:
        #       K: (node_name, path)
        #       V: dict with Keys:
        #                       - port: int
        #                       - next_update_time
        #                       - freq: int
        #                       - paths_to_backups: [{'path_to_backup':, 'md5':}] -> LO VOLARIA
        # Remember the "node_name" serves as the "name" of the ip,
        # which gets resolved by the docker DNS directly.
        self.nodes = {}
        self.nodes_lock = threading.Lock()
        # ipc
        self.admin_to_nodes_manager_msgs_queue = admin_to_nodes_manager_msgs_queue
        self.node_to_backup_queue_from_node_manager_to_backup_requester = node_to_backup_queue_from_node_manager_to_backup_requester
        # other
        self.keep_server_running = keep_server_running

    def run(self):
        # os.chdir("datavolume1")
        t1 = threading.Thread(target=self.attend_requests)
        t2 = threading.Thread(target=self.check_which_nodes_to_backup, daemon=True)
        # t3 = threading.Thread(target=self.receive_new_backup_path, daemon=True)

        t1.start()
        t2.start()
        # t3.start()

        # join just the thread that receives the shutdown message from the requests manager.
        # The second thread is listening (blockingly) to the pipe
        # to attend nodes_to_backup requests from the Backup requester,
        # so it is set to be a daemon thread which will be terminated
        # when the main program holding it does so.
        t1.join()

        logging.info("terminating node manager...")

    def attend_requests(self):
        while True:
            logging.info("node manager running...")
            msg = self.admin_to_nodes_manager_msgs_queue.get()
            if msg == "shutdown":
                self.node_to_backup_queue_from_node_manager_to_backup_requester.put("shutdown")
                break
            elif msg == "reg":
                msg = self.admin_to_nodes_manager_msgs_queue.get()
                # split_msg = msg.split()
                # split msg:
                #       - 0: node_name
                #       - 1: port
                #       - 2: path
                #       - 3: freq
                self.register_node(msg[0], int(msg[1]), msg[2], int(msg[3]))
            elif msg == "unreg":
                msg = self.admin_to_nodes_manager_msgs_queue.recv()
                logging.info("unreg msg: {}".format(msg))
                msg = msg.split()
                # split msg:
                #       - 0: node
                #       - 1: path
                self.unregister_node(msg[0], msg[1])
            else:
                logging.error("Unknown command received in node manager:", msg)

    def register_node(self, node_name: str, port: int, path: str, freq: int):
        try:
            logging.info("received node {}, port {}, path {}, freq {}".format(node_name, port, path, freq))
            # freq. is expressed in minutes. time.time() gives time in seconds.
            # TODO volver a freq en minutos!
            next_update_time = time.time() + freq
            # next_update_time = time.time() + freq * 60
            self.nodes_lock.acquire()
            self.nodes[(node_name, path)] = {'port': port,
                                             'next_update_time': next_update_time,
                                             'freq': freq,
                                             'paths_to_backups': []}
            self.nodes_lock.release()
            logging.info("registration successfully completed")
        except:
            logging.error("an error occurred during node registration")

    def unregister_node(self, node_name: str, path: str):
        try:
            logging.info("received node {}, path {}".format(node_name, path))
            self.delete_backups_for_node((node_name, path))
            self.nodes_lock.acquire()
            del self.nodes[(node_name, path)]
            self.nodes_lock.release()
            logging.info("unregistration successfully completed")
        except:
            logging.error("an error occurred during node unregistration")

    def check_which_nodes_to_backup(self):
        """send nodes to backup to backup requester"""
        while True:
            for node in self.get_nodes_to_backup():
                self.node_to_backup_queue_from_node_manager_to_backup_requester.put(node)
                self.remove_old_backups_for_node(node)
            time.sleep(1)

    def get_nodes_to_backup(self):
        """
        Checks which nodes should send backup.
        The reason to not send via socket here is minimize the time holding the lock on the nodes dict.
        :return: Dict with necessary info for each node having to execute backup.
        """
        self.nodes_lock.acquire()
        nodes_to_backup = []
        for i in self.nodes.keys():
            if time.time() > self.nodes[i]["next_update_time"]:
                filepath_last_backup = self.get_filepath_last_backup(i[0], i[1])
                nodes_to_backup.append({'node': i[0],
                                        'port': self.nodes[i]['port'],
                                        'path': i[1],
                                        'md5': self.md5Checksum(filepath_last_backup),
                                        'last_file_path': filepath_last_backup
                                        })
        self.update_next_backup_time(nodes_to_backup)
        self.nodes_lock.release()
        return nodes_to_backup

    def update_next_backup_time(self, nodes_to_backup):
        for node in nodes_to_backup:
            key = (node['node'], node['path'])
            self.nodes[key]["next_update_time"] = time.time() + self.nodes[key]["freq"]

    def delete_backups_for_node(self, nodes_key):
        """delete all backups for this node so there don't stay any dangling files."""
        files_for_this_backup = self.get_filenames_for_node(nodes_key[0], nodes_key[1])
        logging.info("files_for_this_backup: {}".format(files_for_this_backup))
        for file in files_for_this_backup:
            os.remove(file)
            logging.info("removed file: {}".format(file))

    def remove_old_backups_for_node(self, node):
        """delete old backups for this node to maintain the requested max number of backups."""
        if not node:
            return
        logging.info("remove_old_backups_for_node. node: {}".format(node))
        files_for_this_backup = self.get_filenames_for_node(node['node'], node['path'])
        while len(files_for_this_backup) > MAX_NUM_OF_BACKUPS_TO_KEEP:
            earliest_from_paths = self.get_earliest_from_paths(files_for_this_backup)
            os.remove(earliest_from_paths)
            files_for_this_backup.remove(earliest_from_paths)
            logging.info("removed earliest path: {}".format(earliest_from_paths))

    def get_filepath_last_backup(self, node_name, path):
        files_for_this_backup = self.get_filenames_for_node(node_name, path)
        if files_for_this_backup:
            filepath_last_backup = self.get_latest_from_paths(files_for_this_backup)
            logging.info("filepath last backup: {}".format(filepath_last_backup))
            return filepath_last_backup
        else:
            return ""

    def get_filenames_for_node(self, node_name, path):
        filename_to_match = node_name + "-" + path.replace("/", "-")
        logging.info("partial filename_to_match: {}".format(filename_to_match))
        files_for_this_backup = []
        logging.info("ls: {}".format(os.listdir()))
        for element in os.listdir():
            if element[:len(filename_to_match)] == filename_to_match:
                files_for_this_backup.append(element)
        logging.info("all files for this node, path: {}".format(files_for_this_backup))
        return files_for_this_backup

    def get_latest_from_paths(self, paths):
        largest_path = ""
        largest_number = 0
        for path in paths:
            if int(''.join(filter(str.isdigit, path))) > largest_number:
                largest_number = int(''.join(filter(str.isdigit, path)))
                largest_path = path
        return largest_path

    def get_earliest_from_paths(self, paths):
        smallest_path = ""
        smallest_number = 1e100
        for path in paths:
            if int(''.join(filter(str.isdigit, path))) < smallest_number:
                smallest_number = int(''.join(filter(str.isdigit, path)))
                smallest_path = path
        return smallest_path

    def md5Checksum(self, filepath):
        if not filepath:
            return ""
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
