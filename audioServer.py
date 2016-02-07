# imports
import vlc
import os
import os.path
import socket
from threading import Thread
from enum import Enum
# end of imports

class PlayStatus(Enum):
	PLAY = 0
	PAUSE = 1
	STOP = 2
	PLAY_NEXT = 3

writing_file_id = 0
playing_file_id = -1
file_prefix = ".cache"
close_sockets = False #Flag used to stop all socket loops and to close them

'''
Player
'''
#variables declaration
playing_status = PlayStatus.STOP
vlc_instance = vlc.Instance()
vlc_player = vlc_instance.media_player_new()
#end of variables declaration

def play():
	global playing_status
	global playing_file_id
	
	if playing_status == PlayStatus.PAUSE:
		vlc_player.play()
	elif playing_status == PlayStatus.STOP:
		if next_temp_exists():
			playing_file_id += 1
			media = vlc_instance.media_new(file_prefix + str(playing_file_id))
			vlc_player.set_media(media)
	elif playing_status == PlayStatus.PLAY:
		return
	elif playing_status == PlayStatus.PLAY_NEXT:
		media = vlc_instance.media.new(file_prefix + str(playing_file_if))
	vlc_player.play()
	
	while not is_playing():
		1 == 1
	playing_status = PlayStatus.PLAY

def stop():
	global playing_status
	global playing_file_id
	global writing_file_id
	
	vlc_player.stop()
	#TODO: tell the data socket to empty the buffer and wait for the next start of file
	#shouldn't be necessary given that the connected peer follows the protocol
	playing_status = PlayStatus.STOP
	playing_file_id = -1
	writing_file_id = 0

def pause():
	global playing_status
	vlc_player.pause()
	playing_status = PlayStatus.PAUSE

def is_playing():
	return vlc_player.is_playing()

def set_volume(new_volume):
	vlc_player.audio_set_volume(int(new_volume))

def auto_track_selection_loop():
	global playing_file_id
	global playing_status
	while True:
		if playing_status == PlayStatus.PLAY and not is_playing() and next_temp_exists():
			playing_status = PlayStatus.STOP
			play()
			command_send_message(b'PN')
		if playing_status == PlayStatus.STOP and not is_playing() and not next_temp_exists():
			playing_status = PlayStatus.STOP

'''
End of player
'''

'''
Data socket
'''
#variables declaration
DATA_SOCKET_IP = "0.0.0.0"
DATA_SOCKET_PORT = 4444
global data_socket
#end of variables declaration

def initialize_data_socket():
	sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	sck.bind((DATA_SOCKET_IP, DATA_SOCKET_PORT))
	global data_socket
	sck.listen(1)
	data_socket, addr = sck.accept()
	print('[INFO] Data connection established ', addr)

def data_socket_loop():
        global writing_file_id
        connection_lost = False
        with data.makefile() as socket_file:
                while not connection_lost and not close_sockets:
                        try:
                                data = socket_file.readline()
                        except:
                                print('Connetion was lost')
                                connection_lost = True
                        if not data: break
                        elif data == 'SOF':
                                print('[DEBUG] Start of file flag received. Current file id: ' + str(writing_file_id))
                                create_new_temp()
                                continue
                        elif data == 'EOF':
                                writing_file_id += 1
                                print('[DEBUG] End of file flag received. Current file id: ' + str(writing_file_id))
                        
                        else:
                                write_data_to_temp(data)

			
'''
End of data socket
'''

'''
Command socket
'''
COMMAND_SOCKET_PORT = 4445
global command_socket

def initialize_command_socket():
	sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	sck.bind((DATA_SOCKET_IP, COMMAND_SOCKET_PORT))
	global command_socket
	sck.listen(1)
	command_socket, addr = sck.accept()

def command_socket_loop():
	connection_lost = False
	while not connection_lost and not close_sockets:
		try:
			data = command_socket.recv(1024)
		except:
			print('Data connection lost')
			connection_lost = True
		if not data: break
		elif data == b'PL':
			print('[INFO] Play command received')
			play()
		elif data == b'PA':
			print('[INFO] Pause command received')
			pause()
		elif data == b'ST':
			print('[INFO] Stop command received')
			stop()
		elif data == b'VL':
			data = command_socket.recv(1024)
			print('[INFO] Set volume command received ' + str(data))
			set_volume(data)

def command_send_message(message):
		command_socket.send(message + b'\n')

'''
End of command socket
'''

'''
File manager
'''
global current_file

def create_new_temp():
	global current_file
	current_file = open(file_prefix + str(writing_file_id), 'wb')
	current_file.close()
	current_file = open(file_prefix + str(writing_file_id), 'ab', 0)

def next_temp_exists():
	return os.path.isfile(file_prefix + str(playing_file_id + 1))

def remove_temp(temp_id):
	try:
		os.remove(file_prefix + str(temp_id))
	except:
		print('')

def remove_all_temps():
	for i in range (0, writing_file_id + 1):
		remove_temp(file_prefix + str(writing_file_id))

def write_data_to_temp(data):
	global current_file
	current_file.write(data)
	current_file.flush()
	os.fsync(current_file.fileno())

def close_current_file():
	global current_file
	current_file.close()

def clear_cache():
	done = False
	index = 0
	while not done:
		if os.path.isfile(file_prefix + str(index)):
			remove_temp(file_prefix + str(index))
		else:
			done = True
		index += 1

'''
End of file manager
'''


def main():
	clear_cache()
	initialize_data_socket()
	initialize_command_socket()
		
	data_loop_thread = Thread(target = data_socket_loop)
	data_loop_thread.setDaemon(True)
	data_loop_thread.start()
	
	command_loop_thread = Thread(target = command_socket_loop)
	command_loop_thread.setDaemon(True)
	command_loop_thread.start()
	
	track_selector_loop_thread = Thread(target = auto_track_selection_loop)
	track_selector_loop_thread.setDaemon(True)
	track_selector_loop_thread.start()
