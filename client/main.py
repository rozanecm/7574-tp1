#!/usr/bin/env python3

import os
import time
import logging
from ctypes import c_bool

from common.client import Client
from multiprocessing import Value

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
        config_params["port"] = int(os.environ["PORT"])
        config_params["name"] = os.environ["NAME"]
        config_params["listen_backlog"] = int(os.environ["BACKLOG"])
    except KeyError as e:
        raise KeyError("Key was not found. Error: {} .Aborting client".format(e))
    except ValueError as e:
        raise ValueError("Key could not be parsed. Error: {}. Aborting client".format(e))

    return config_params


def main():
    initialize_log()
    config_params = parse_config_params()

    keep_client_running = Value(c_bool, True)

    try:
        os.mkdir("datavolume1/client")
    except FileExistsError:
        logging.info("path client/ already exists")
    try:
        os.mkdir(os.path.join("datavolume1/client", config_params['name']))
    except FileExistsError:
        logging.info("path client/[name] already exists")
    os.chdir(os.path.join("datavolume1/client", config_params['name']))

    # Initialize client and start server loop
    server = Client(config_params["port"], config_params['name'], config_params["listen_backlog"], keep_client_running)
    server.run()
    logging.info("terminating client {}".format(config_params["name"]))

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
