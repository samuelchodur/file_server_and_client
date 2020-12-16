#!/usr/bin/python3
"""
This code is based on the example TCP server (threaded) given in the Python
docs:
https://docs.python.org/3.6/library/socketserver.html#module-socketserver

Features were added to meet project requirements summarized below:
- Client writes received data (binary and text) to a file identified by the 
    client
- Server prints out debugging messages if global variable DEBUG is set to True
    Default for DEBUG global is set to False
- Before, during and after transfering a file, the following is printed on 
    the server:
    Before Starting:
    % Sending <filename> to <client's-IP-address>
    During:
    % Sent 10% of <filename>
    % Sent 20% of <filename>
    ...
    % Sent 100% of <filename>
    When Completed:
    % Finished sending <filename> to <client's-IP-address>
- Client has arguments to specify an inclusive byte range for files 
    downloaded from the server.
- Error detection which is reported back to the client when a requested file
    does not exist.
- client has a flag "-w" to specify if they want to write a file to the server
    instead of downloading it.
- A help message is displayed if the user of the client program uses the
    interface incorrectly.
"""
import argparse
import logging

import threading

import socket
import socketserver

from pathlib import Path

# Set to True if you want to enable debugging messages for the server
DEBUG = False

FILE_DIR = './hosted-files/'
SEP = "<SEPARATOR>" # Used to separate portions of request messages
BUFFER_SIZE = 4096  # How much data is sent each iteration

class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):
    """
    The request handler class for our server.

    An alternative request handler class that makes use of streams 
    (file-like objects that simplify communication by providing the standard
    file interface):
    """
    def handle(self):
        logging.debug('Received a new TCP request.')
        logging.debug('Client IP: {}'.format(self.client_address[0]))
        self.processed_init_cmd = False    # Initial Command not set
        # Get the initial command from the client.
        self.init_cmd = self.get_init_cmd()
        
        if self.init_cmd:
            logging.debug('Received a valid initial command')
            # Ready to process initial command
            if self.process_init_cmd():
                final_resp = bytes(f'd{SEP}PROCESS COMPLETE', 'ascii')
            else:
                final_resp = bytes(f'e{SEP}Something went wrong.', 'ascii')
        else:
            logging.debug('Received invalid initial command')
            final_resp = bytes(f'e{SEP}Unknown Initial Command', 'ascii')
        
        logging.debug('Sending Final Response')
        self.request.sendall(final_resp)
        
        logging.debug('Closing TCP Request.')
        self.request.close()
        logging.debug('Request Closed.')


    def process_init_cmd(self):
        """
        Kick off what needs to be done in accordance from the initial
        command that was received from the client.
        """
        logging.debug('Processing initial client command.')
        init_cmd = self.init_cmd[0]
        
        if init_cmd == 'w':
            self.fn = self.init_cmd[1]
            self.file_size = int(self.init_cmd[2])
            logging.debug('Beginning process to write file to server.')
            logging.debug('Name: {} | Size: {}'.format(self.fn, 
                self.file_size))
            receive_ready, resp = self.receive_ready_check(self.fn, 
                self.file_size)
            if receive_ready:
                logging.debug('We are ready to receive a file.')
                logging.debug('Sending Client CMD to send file')
                self.request.sendall(resp)
                self.receive_file()
                # Reception was successful
                process_status = True
            else:
                logging.debug('We are NOT ready to receive a file.')
                resp = bytes(f'e{SEP}FILE EXISTS ON SERVER. RENAME FILE.', 
                    'ascii')
                self.request.sendall(resp)
                process_status = False
        if init_cmd == 'g':
            self.fn = self.init_cmd[1]
            try:
                self.start_byte = int(self.init_cmd[2])
            except ValueError:
                # must be set to None?
                self.start_byte = 0
            try:
                self.end_byte = int(self.init_cmd[3])
            except ValueError:
                # Must be set to None? Use -1 as last byte for
                self.end_byte = -1
            logging.debug('Beginning process of sending a file to client.')
            logging.debug('Name: {} | Start Byte: {} | End Byte {}'.format(
                self.fn, self.start_byte, self.end_byte))
            send_ready, resp = self.send_ready_check()
            if send_ready:
                logging.debug('We are ready to send a file.')
                self.request.sendall(resp)
                logging.debug('Sent Client CMD to send file')
                self.send_file()
                process_status = True
            else:
                logging.debug('We are NOT ready to send a file.')
                #resp = bytes(f'e{SEP}FILE DOES NOT EXIST', 'ascii')
                self.request.sendall(resp)
                process_status = False
        
        logging.debug('Successfully processed initial command')
        return process_status

    def send_file(self):
        r"""
        Send a file to a client. Bunch of extra stuff in here to display
        what % of file has been sent.
        """
        self.successful_send = False
        print(f'Sending {self.fn} to {self.client_address[0]}')
        logging.debug('Start Byte: {} | End Byte {}'.format(self.start_byte, 
            self.end_byte))
        
        ### For the progress
        tot_bytes_sent = 0
        bytes_left = self.file_size
        try:
            percent_sent = tot_bytes_sent / bytes_left * 100
        except ZeroDivisionError:
            # User might be requesting an empty file
            percent_sent = 0
        percent_printed = 0
        ### Begin opening and sending bytes
        with open(f'{FILE_DIR}{self.fn}', 'rb') as f:
            f.seek(self.start_byte) # Start reading file at start byte
            logging.debug(f'Opened file at byte: {f.tell()}')
            if BUFFER_SIZE >= bytes_left:
                bytes_read = f.read(bytes_left)
                bytes_left = 0
            else:
                bytes_read = f.read(BUFFER_SIZE)
                bytes_left = bytes_left - BUFFER_SIZE
            while bytes_read: 
                self.request.sendall(bytes_read)
                if self.file_size < BUFFER_SIZE:
                    # More stuff for progress percentage.
                    tot_bytes_sent += self.file_size
                else:
                    tot_bytes_sent += BUFFER_SIZE
                try:
                    percent_sent = tot_bytes_sent / self.file_size * 100
                    percent_sent = percent_sent - (percent_sent % 10)
                except ZeroDivisionError:
                    # We are sending an empty file
                    percent_sent = 100 # automatically 100 percent sent
                if (percent_sent > percent_printed):
                    while percent_printed < percent_sent:
                        print(f'Sent {percent_printed}% of {self.fn}')
                        percent_printed += 10
                if bytes_left >= BUFFER_SIZE:
                    bytes_read = f.read(BUFFER_SIZE)
                    bytes_left -= BUFFER_SIZE
                else:
                    bytes_read = f.read(bytes_left)
                    bytes_left = 0
                
        percent_sent = 100  # Just do this in case of empty file.
        if (percent_sent > percent_printed):
            # If we send an empty file still display progress
            while percent_printed < percent_sent:
                print(f'Sent {percent_printed}% of {self.fn}')
                percent_printed += 10
        print(f'Sent 100% of {self.fn}')
                
        self.successful_send = True
        print(f'Finished sending {self.fn} to {self.client_address[0]}')
        response = bytes('Finished sending your file.', 'ascii')
        return


    def send_ready_check(self):
        r"""
        Check that we are ready to fulfill client request to receive a file.
        Also generate the response to send to client so they initiate
        reception.
        """
        fn = self.fn
        if self.file_exists():
            # File must exist to send it...
            logging.debug(f'The file {fn} exists in our directory')
            self.file_size = self.p.stat().st_size
            if self.end_byte == 'EOF':
                self.end_byte = self.file_size 
            logging.debug(f'File Size: {self.file_size}')
            if not self.byte_bound_check():
                # Byte bound check failed. Cannot send file.
                response = bytes(f'e{SEP}Provided byte bounds are illogical', 
                    'ascii')
                return False, response
            else:
                # Ready to send
                # Filesize changes based on start and end bytes
                self.calc_send_filesize()
                response = bytes(f'g{SEP}{self.file_size}{SEP}', 
                    'ascii')
                return True, response
        else:
            # File does not exist
            logging.debug(f'The file {fn} does not exist on server.')
            response = bytes(f'e{SEP}{fn} Does not exist on server.', 'ascii')
            return False, response
            
        logging.debug('Should never reach here. [receive_ready_check()]')
        return


    def calc_send_filesize(self):
        r"""
        Calculate how large of a file we are sending based on startbyte
        and endbyte and original filesize
        """
        to_subtract = 0     # How much to subtract from filesize
        logging.debug(f'Start Byte: {self.start_byte}')
        to_subtract += self.start_byte
        if self.end_byte > self.start_byte:
            to_subtract += (self.file_size - self.end_byte)
        logging.debug(f'Subtracting {to_subtract} from original file size')
        self.file_size = self.file_size - to_subtract

        return


    def receive_file(self):
        r"""
        Receive a file from the client.
        """
        self.successful_receive = False
        # What if client never ends up sending the file?
        with open(f'{FILE_DIR}{self.fn}', 'wb') as f:
            bytes_read = self.request.recv(BUFFER_SIZE)
            while bytes_read:
                f.write(bytes_read)
                bytes_read = self.request.recv(BUFFER_SIZE)
            f.close()
        self.successful_receive = True
        response = bytes('Finished receiving your file.', 'ascii')
        return

       
    def get_init_cmd(self):
        r"""
        Process the initial command from the client and decide
        what to do from there.
        """
        init_receive = str(self.request.recv(BUFFER_SIZE), 'ascii').split(SEP)
        init_cmd = init_receive[0]
        
        if init_cmd[0] == 'w':
            logging.debug('Client wants to write a file to the server.')
            return init_receive
            # Kick off receive
        elif init_cmd[0] == 'g':
            logging.debug('Client wants to get a file from the server.')
            return init_receive
        else:
            logging.debug('Unknown command from client.')
            
        return False
        
       
    def receive_ready_check(self, fn, file_size):      
        logging.debug(f'Attempting to receive {fn}')
        
        if self.file_exists():
            # We cannot accept the file if the name already exists
            logging.debug(f'The file {fn} exists in our directory')
            response = bytes(f'e{SEP}FILE EXISTS. RENAME FILE.', 'ascii')
            return False, response
        else:
            # We are ready to receive the file now
            logging.debug('Asking the client to send the file')
            response = bytes(f's{SEP}{self.fn}{SEP}{self.file_size}', 'ascii')
            return True, response
            
        logging.debug('Should never reach here. [receive_ready_check()]')
        return
 
            
    def file_exists(self):
        """
        Check if a file exists or not
        """
        fn = self.fn
        
        logging.debug('Checking if the file exists: {}'.format(fn))
        
        p = Path('{}{}'.format(FILE_DIR, fn))
        logging.debug('Path object created: {}'.format(p))
        
        if p.is_file():
            logging.debug('File exists and is not a directory')
            self.p = p  # Other functions may want to use this now.
            return True
        else:
            logging.debug('File does not exist nor is it a directory')
            return False
        

    def byte_bound_check(self):
        r"""
        Check the start byte and end byte supplied by client to make sure it
        makes sense for the file. if file size is 100 bytes, and end byte
        is 102, send error to client. same for start byte.
        """
        byte_bound_status = True   # Assume good for now
        if self.start_byte > self.file_size:
            # Start byte can't be after the last byte...
            logging.debug('Provided start byte is illogical. Return error.')
            byte_bound_status = False
        elif self.end_byte > self.file_size:
            logging.debug('Provided end byte is illogical. Return error.')
            byte_bound_status = False
        elif self.start_byte < 0:
            logging.debug('Provided end byte is illogical. Return error.')
            byte_bound_status = False
            '''
            End byte can be specified as negative value just like Python
            list slices
            elif self.end_byte < 0:
                logging.debug('Provided end byte is illogical. Return error.')
                byte_bound_status = False
            '''
        elif (self.end_byte < self.start_byte) and (self.end_byte != -1):
            logging.debug('Provided end byte is illogical. Return error.')
            byte_bound_status = False
        else:
            logging.debug('Byte bound check successful')
            byte_bound_status = True
        
        return byte_bound_status


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


if __name__ == "__main__":
    HOST, PORT = "localhost", 2345
    if DEBUG:
        logging.basicConfig(level=logging.DEBUG, 
            format='%(asctime)s - %(levelname)s - %(message)s')
        logging.debug('DEBUGGING Messages Enabled.')
    
    # Create the server, binding to localhost on port 2345
    try:
        with ThreadedTCPServer((HOST, PORT), 
                ThreadedTCPRequestHandler) as server:
            ip, port = server.server_address
            logging.debug('TCP Server activated at {}:{}'.format(ip, port))
            
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.start()
            logging.debug('Server Thread Started')
            server_thread.join()
            
            logging.debug('Server Thread Joined') # This never happens
            server.shutdown()
    except OSError:
        print(f'Port {PORT} is current in use by the operating system.')
        print('Change the port or wait until it is free.')

    logging.debug(f'End of function {__name__}')
