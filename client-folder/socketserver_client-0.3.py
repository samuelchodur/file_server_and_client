#!/usr/bin/python3
"""A simple file server client

This code is based on the example TCP client given in the Python docs:
https://docs.python.org/3.6/library/socketserver.html#module-socketserver
"""
import argparse

import socket
import sys

import logging

from pathlib import Path

# Provided example file hardcoded PORT, so we will too
PORT = 2345

FILE_DIR = './'  # Just use the current directory
FN_LIMIT = 255  # Number of chars that can be in a filename

SEP = "<SEPARATOR>" # Used to separate request commands
BUFFER_SIZE = 4096  # How much data is sent each iteration

def parse_args():
    '''
    Usage: client [-s StartBlock] [-e LastBlock] server-name [-w] file-name
    
    '''
    # Create an argument parser and customize the usage string
    parser = argparse.ArgumentParser(prog='client', 
    usage='%(prog)s [-s StartBlock] [-e LastBlock] server-name [-w] file-name')
    
    parser.add_argument('server_name', action='store', metavar='server-name', 
            type=str, help='server hostname or IP (required)')
    parser.add_argument('-s', metavar='StartBlock', type=int,
            help='specify the StartBlock')
    parser.add_argument('-e', metavar='EndBlock', type=int,
        help='specify the LastBlock')
    parser.add_argument('-w', action='store_true', help='write file to server')
    parser.add_argument('file_name', action='store', metavar='file-name', 
            type=str, help='filename to transfer (required)')
    parser.add_argument('--debug', action='store_true',
            help='enable debugging messages')
                
    args = parser.parse_args()
    
    return args


def construct_client_request(start_b, end_b, write, fn):
    '''
    This function decides what we should send to the server. What we initially
    send will decide whether we want to upload or download a file.
    '''
    logging.debug('Constructing Initial Request with following:')
    logging.debug('start_b: {} | end_b: {} | write: {} | fn: {}'
                    .format(start_b, end_b, write, fn))
                    
    if write:
        logging.debug('User is requesting to upload {}'.format(fn)) 
        p = Path('{}{}'.format(FILE_DIR, fn))
        if p.is_file():
            # Check if the file actually exists in the current directory
            logging.debug('File exists and is not a directory')
            file_size = p.stat().st_size
            logging.debug('File size: {} Bytes'.format(file_size))
        else:
            # File specified doesn't exist
            logging.debug('File does not exist or is it a directory')
            print('USER ERROR: The file {} does not exist'.format(p))
            print('When using \'-w\' flag, you are sending to the server.')
            print('Please input a filename that exists and try again.')
            return False
        # we want to download file from the server
        # w means client wants to write. Use a seperator for easy way to
        # distinguish between separate parts of our message to server.
        request = f'w{SEP}{fn}{SEP}{file_size}'
        logging.debug('Request: {}'.format(request))
        return request
    else:
        logging.debug('User is requesting to download {}'.format(fn))
        # s<SEP>fn<SEP>sb<SEP>eb
        request = 'g{}{}{}{}{}{}'.format(SEP, fn, SEP, start_b, SEP, end_b)
        logging.debug('Request: {}'.format(request))
        return request
    
    return False


def process_request(request):
    r"""
    Process the request with the server that the client wants based on their
    command line input.
    """
    if request[0] == 'w':
        logging.debug('Processing Write to Server request')
        
    logging.debug('Finished Processing Request.')
    return
        

if __name__ == '__main__':
    # Parse command line arguments
    args = parse_args()
    
    if args.debug:
        # User wants to display debugging messages
        logging.basicConfig(format='%(levelname)s: %(message)s', 
                level=logging.DEBUG)
        logging.debug('Debugging messages will be displayed')
    
    logging.debug('Parsed Arguments are: {}'.format(vars(args)))
    
    HOST = args.server_name
    logging.debug('Server Host set to: {}'.format(HOST))
    logging.debug('Server Port set to: {}'.format(PORT))
    
    logging.debug('Figuring out what client wants to do by looking at args.')
    request = construct_client_request(args.s, args.e, args.w, args.file_name)
    
    if not request:
        # construct_client_request returns False if there was something wrong
        logging.debug('No valid request able to be generated from arguments.')
        quit()
        
    process_request(request)

    # Create a socket (SOCK_STREAM means a TCP socket)
    logging.debug('Attempting to create a socket')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        logging.debug('Created a socket.')
        
        logging.debug('Attempting connection to {}:{}'.format(HOST, PORT))
        sock.connect((HOST, PORT))
        logging.debug('Connection established.')
        
        logging.debug('Sending Request.')
        sock.sendall(bytes(request + "\n", "utf-8"))
        logging.debug('Request sent. Waiting for response from server')

        
        received = str(sock.recv(1024), "ascii").split(SEP)
        logging.debug('Received data back from server.')
        if received[0] == 's':
            # Server wants us to send the file
            logging.debug(f'Packaging {FILE_DIR}{args.file_name} to send')
            with open(f'{FILE_DIR}{args.file_name}', 'rb') as f:
                bytes_read = f.read(BUFFER_SIZE)
                while bytes_read:
                    sock.sendall(bytes_read)
                    bytes_read = f.read(BUFFER_SIZE)
                print(f'Successfully sent {args.file_name} to server.')
                logging.debug('Done sending all bytes')
            sock.close()
        elif received[0] == 'g':
            # Server wants to send us a file (g for get)
            file_size = int(received[1])
            print('File is {} Bytes'.format(file_size))
            with open(f'{FILE_DIR}{args.file_name}', 'wb') as f:
                if BUFFER_SIZE >= file_size:
                    # Don't want to read too much into the file.
                    bytes_read = sock.recv(file_size)
                    bytes_left = 0
                else:
                    bytes_read = sock.recv(BUFFER_SIZE)
                    bytes_left = file_size - BUFFER_SIZE
                while bytes_read:
                    f.write(bytes_read)
                    if bytes_left < BUFFER_SIZE:
                        bytes_read = sock.recv(bytes_left)
                        bytes_left = 0
                    else:
                        bytes_read = sock.recv(BUFFER_SIZE)
                        bytes_left = bytes_left - BUFFER_SIZE
                f.close()
            logging.debug('Done receiving all bytes')
            sock.close()   
        elif received[0] == 'e':
            logging.debug('Error sent from server.')
            print("Error Message: {}".format(received[1]))
            logging.debug('Closing TCP connection due to error')
            sock.close()
        elif received[0] == 'd':
            logging.debug('Server says they are done with us.')
            print('Closing TCP Connection at request of server.')
            sock.close()
        else:
            print('Unknown response from server.')
            print(f'Server Message: {received}')
        sock.close()
