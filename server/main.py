#!/usr/bin/env python3

import os
import time
import logging
from ctypes import c_bool

from common.server import Server
from common.backup_requester import BackupRequester
from common.node_manager import NodeManager
from multiprocessing import Process, Manager, Value, Queue, Pipe



def parse_config_params():
    """ Parse env variables to find program config params

    Function that search and parse program configuration parameters in the
    program environment variables. If at least one of the config parameters
    is not found a KeyError exception is thrown. If a parameter could not
    be parsed, a ValueError is thrown. If parsing succeeded, the function
    returns a map with the env variables
    """
    config_params = {}
    try:
        config_params["port"] = int(os.environ["SERVER_PORT"])
        config_params["listen_backlog"] = int(os.environ["SERVER_LISTEN_BACKLOG"])
    except KeyError as e:
        raise KeyError("Key was not found. Error: {} .Aborting server".format(e))
    except ValueError as e:
        raise ValueError("Key could not be parsed. Error: {}. Aborting server".format(e))

    return config_params


def main():
    initialize_log()
    config_params = parse_config_params()

    # docs de manager.dict(): https://docs.python.org/3/library/multiprocessing.html#sharing-state-between-processes
    manager = Manager()
    # the following variable will be set to False by the server when a termination msg is received.
    # The backup requester will run as long as this bool indicates the server should be kept running.
    keep_server_running = Value(c_bool, True)

    # this queue is used to send msgs to the node manger.
    # The Node manager should not use it to send msgs in the other direction,
    # since nobody will be listening.
    node_manager_queue = Queue()

    # the pipe will be used for bi-directional
    # communication between node and backup manager.
    # The backup manager will request the nodes to backup,
    # and the node manager will provide the list with them.
    node_manager_pipe_end, backup_requester_pipe_end = Pipe()

    # Initialize server and start server loop
    server = Server(config_params["port"], config_params["listen_backlog"], keep_server_running, node_manager_queue)
    node_manager = NodeManager(keep_server_running, node_manager_queue, node_manager_pipe_end)
    backup_requester = BackupRequester(keep_server_running, node_manager_queue, backup_requester_pipe_end)

    p1 = Process(target=server.run)
    p2 = Process(target=backup_requester.run)
    p3 = Process(target=node_manager.run)

    p1.start()
    p2.start()
    p3.start()

    p1.join()
    p2.join()
    p3.join()


def initialize_log():
    """
    Python custom logging initialization

    Current timestamp is added to be able to identify in docker
    compose logs the date when the log has arrived
    """
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
    )


if __name__ == "__main__":
    main()
