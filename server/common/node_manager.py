import json
import logging
import os
import threading
import time
import threading
import hashlib
import tarfile


class NodeManager:
    def __init__(self, keep_server_running, admin_to_nodes_manager_msgs_queue,
                 new_backup_path_queue_from_backup_requester_to_nodes_manager,
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
        self.new_backup_path_queue_frm_backup_requester_to_nodes_manager = new_backup_path_queue_from_backup_requester_to_nodes_manager
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

    # def query_node(self, node_name: str, path: str):
    #     # TODO adaptar esto segun como se guarde el backup.
    #     # Seguramente sea un path al backup. Eso se le pasa desp.
    #     # al que maneje el envio, que ira leyendo y enviando el archivo.
    #     try:
    #         logging.info("received node {}, path {}".format(node_name, path))
    #         backup = self.nodes[(node_name, path)]
    #         logging.info("query successfully completed")
    #         return backup
    #     except:
    #         logging.error("an error occurred during node query")

    # def attend_backups_requester_requests(self):
    #     while True:
    #         # TODO implementar
    #         msg = self.pipe_to_backups_requester.recv()
    #         logging.info("received msg in attend_backups_requester_requests: {}".format(msg))
    #         if msg == "nodes_to_backup":
    #             self.pipe_to_backups_requester.send(self.get_nodes_to_backup())
    #         else:
    #             logging.warning("Unknown message received from Backup requester: {}".format(msg))
    def check_which_nodes_to_backup(self):
        """send nodes to backup to backup requester"""
        while True:
            for node in self.get_nodes_to_backup():
                self.node_to_backup_queue_from_node_manager_to_backup_requester.put(node)
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
            # print(node)
            key = (node['node'], node['path'])
            # print(key)
            self.nodes[key]["next_update_time"] = time.time() + self.nodes[key]["freq"]

    def delete_backups_for_node(self, nodes_key):
        """delete all backups for this node so there don't stay any dangling files."""
        # TODO impl
        pass

    # def get_last_md5_for_backup(self, filepath):
    #     try:
    #         return self.nodes[key]['paths_to_backups'][-1]['md5']
    #     except IndexError:
    #         return ""
    #     except:
    #         logging.info("error getting last md5 for backup")

    # def get_last_filepath(self, key):
    #     try:
    #         return self.nodes[key]['paths_to_backups'][-1]['path_to_backup']
    #     except IndexError:
    #         return ""
    #     except:
    #         logging.info("error getting last filepath for backup")

    # def receive_new_backup_path(self):
    #     node, path = self.new_backup_path_queue_from_backup_requester_to_nodes_manager.get()
    #     self.nodes_lock.acquire()
    #     self.nodes((node['node'],node['path']))['']
    #     self.nodes_lock.release()

    # def md5Checksum(self, filepath):
    #     # src: https://www.joelverhagen.com/blog/2011/02/md5-hash-of-file-in-python/
    #     logging.info("getting md5 for {}".format(filepath))
    #     if not filepath:
    #         return ""
    #     logging.info("checking md5")
    #     m = hashlib.md5()
    #     with open(filepath, 'rb') as fh:
    #         while True:
    #             data = fh.read(8192)
    #             if not data:
    #                 break
    #             m.update(data)
    #     return m.hexdigest()

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
    # def get_last_modified_time(self, filepath):
    #     if filepath:
    #         return os.path.getmtime(filepath)
    #     else:
    #         return 0
