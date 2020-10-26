import datetime


class Logger():
    def __init__(self, logger_queue, file_name):
        self.logger_queue = logger_queue
        self.file_name = file_name

    def run(self):
        """
        :param msg: msg to save to logger, which will be written in a new line in the logger file.
        :return: void
        """
        msg = self.logger_queue.get()
        with open(self.file_name, 'w') as opened_file:
            while msg != "shutdown":
                line_to_write = str(datetime.datetime.now()) + ": " + msg + "\n"
                opened_file.write(line_to_write)
                opened_file.flush()
                msg = self.logger_queue.get()
                print("logger got msg {}".format(msg))
