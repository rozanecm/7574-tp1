import logging
import threading
import time


class NodeManager:
    def __init__(self, keep_server_running, requests_queue, pipe_to_backups_requester):
        # Nodes:
        #       K: (node, path)
        #       V: dict with Keys:
        #                       - port
        #                       - next_update_time
        #                       - freq
        self.nodes = {}
        # ipc
        self.requests_queue = requests_queue
        self.pipe_to_backups_requester = pipe_to_backups_requester
        # other
        self.keep_server_running = keep_server_running

    def run(self):
        t1 = threading.Thread(target=self.attend_admin_requests)
        t2 = threading.Thread(target=self.attend_backups_requester_requests, daemon=True)

        t1.start()
        t2.start()

        # join just the thread that receives the shutdown message from the requests manager.
        # The second thread is listening (blockingly) to the pipe
        # to attend nodes_to_backup requests from the Backup requester,
        # so it is set to be a daemon thread which will be terminated
        # when the main program holding it does so.
        t1.join()


        # self.executor.submit(self.attend_admin_requests)
        # self.executor.submit(self.attend_backups_requester_requests)
        # while True:
        #     logging.info("node manager running...")
        #     msg = self.requests_queue.get()
        #     if msg == "shutdown":
        #         break
        #     elif msg == "reg":
        #         msg = self.requests_queue.get()
        #         split_msg = msg.split()
        #         # split msg:
        #         #       - 0: reg
        #         #       - 1: node
        #         #       - 2: port
        #         #       - 3: path
        #         #       - 4: freq
        #         self.register_node(split_msg[1], int(split_msg[2]), split_msg[3], int(split_msg[4]))
        #     elif msg == "unreg":
        #         msg = self.requests_queue.recv()
        #         logging.info("unreg msg: {}".format(msg))
        #         split_msg = msg.split()
        #         # split msg:
        #         #       - 0: unreg
        #         #       - 1: node
        #         #       - 2: path
        #         self.unregister_node(split_msg[1], split_msg[2])
        #     else:
        #         logging.error("Unknown command received in node manager:", msg)




            # self.attend_admin_requests()
        logging.info("terminating node manager...")

    def attend_admin_requests(self):
        while True:
            logging.info("node manager running...")
            msg = self.requests_queue.get()
            if msg == "shutdown":
                break
            elif msg == "reg":
                msg = self.requests_queue.get()
                split_msg = msg.split()
                # split msg:
                #       - 0: reg
                #       - 1: node
                #       - 2: port
                #       - 3: path
                #       - 4: freq
                self.register_node(split_msg[1], int(split_msg[2]), split_msg[3], int(split_msg[4]))
            elif msg == "unreg":
                msg = self.requests_queue.recv()
                logging.info("unreg msg: {}".format(msg))
                split_msg = msg.split()
                # split msg:
                #       - 0: unreg
                #       - 1: node
                #       - 2: path
                self.unregister_node(split_msg[1], split_msg[2])
            else:
                logging.error("Unknown command received in node manager:", msg)

    def register_node(self, node:str, port:int, path:str, freq:int):
        try:
            logging.info("received node {}, port {}, path {}, freq {}".format(node, port, path, freq))
            # freq. is expressed in minutes. time.time() gives time in seconds.
            # TODO volver a freq en minutos!
            next_update_time = time.time() + freq
            # next_update_time = time.time() + freq * 60
            self.nodes[(node, path)] = {'port': port,
                                        'next_update_time': next_update_time,
                                        'freq': freq}
            logging.info("registration successfully completed")
        except:
            logging.error("an error occurred during node registration")

    def unregister_node(self, node: str, path: str):
        try:
            logging.info("received node {}, path {}".format(node, path))
            # TODO borrar los backups para que no quede dangling.
            del self.nodes[(node, path)]
            logging.info("unregistration successfully completed")
        except:
            logging.error("an error occurred during node unregistration")

    def query_node(self, node: str, path: str):
        # TODO adaptar esto segun como se guarde el backup.
        # Seguramente sea un path al backup. Eso se le pasa desp.
        # al que maneje el envio, que ira leyendo y enviando el archivo.
        try:
            logging.info("received node {}, path {}".format(node, path))
            backup = self.nodes[(node, path)]
            logging.info("query successfully completed")
            return backup
        except:
            logging.error("an error occurred during node query")

    def attend_backups_requester_requests(self):
        while True:
            # TODO implementar
            msg = self.pipe_to_backups_requester.recv()
            logging.info("received msg in attend_backups_requester_requests: {}".format(msg))
            if msg == "nodes_to_backup":
                self.pipe_to_backups_requester.send(self.get_nodes_to_backup())
            else:
                logging.warning("Unknown message received from Backup requester: {}".format(msg))

    def get_nodes_to_backup(self):
        nodes_to_backup = []
        for i in self.nodes.keys():
            if time.time() > self.nodes[i]["next_update_time"]:
                nodes_to_backup.append(i)
        self.update_next_backup_time(nodes_to_backup)
        return nodes_to_backup

    def update_next_backup_time(self, nodes_to_backup):
        for node in nodes_to_backup:
            self.nodes[node]["next_update_time"] = time.time() + self.nodes[node]["freq"]
