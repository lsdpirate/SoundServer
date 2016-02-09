'''
The structure of this application is buggy and bad thinked.
I will have to rewrite this with a clue of which features to include and with
a bit of order mainly relative to funcitonality of the code.
'''
import socket
import vlc
from threading import Thread
import os
import time

#IP and port constants
TCP_IP = "0.0.0.0"
TCP_PORT = 4444
# By convention the command port should always be the data port value + 1
TCP_COMMAND_PORT = 4445
#Data frame constant
CHUNK = 1024

sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cmd_sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
cmd_sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

stop_reading_buffer = False
close_sockets = False

sck.bind((TCP_IP, TCP_PORT))
cmd_sck.bind((TCP_IP, TCP_COMMAND_PORT))


# Vlc player variables
vlc_instance = vlc.Instance()
vlc_player = vlc_instance.media_player_new()
#media = vlc_instance.media_new('tmp')
#vlc_player.set_media(media)

requested_playing_status = 'STOP'

'''
When a media file is received it is cached in the mass storage of
the device this service is running on.
All created files will follow a prefix and suffix ruling where
the prefix is constant (.asCache) and the suffix is an incrementing id
that grows as a file has been received.
The same rule applies to the player that will follow this progressive order
for playing files.
'''
file_prefix = ".asCache"
writing_file_id = 0
playing_file_id = 0
notify_song_skipped_flag = False

#######

def play():
    global media
    global requested_playing_status

    if isPlaying():
        return

    if requested_playing_status == 'PAUSE':
        vlc_player.play()
        return

    if requested_playing_status == 'STOP':
        media = vlc_instance.media_new(file_prefix + str(playing_file_id))

    #Unsafe, should check if the file exists and is not empty
    vlc_player.set_media(media)
    vlc_player.play()
    while not isPlaying():
        1 == 1
    print('[DEBUG] Player playing status: ' + str(isPlaying()))
    
    requested_playing_status = 'PLAY'
    


def stop():
    global requested_playing_status
    global playing_file_id
    
    requested_playing_status = 'STOP'
    vlc_player.stop()
    playing_file_id = 0
    #clearLocalBuffer()


def pause():
    global requested_playing_status
    requested_playing_status = 'PAUSE'
    vlc_player.pause()


def isPlaying():
    return vlc_player.is_playing()


def startDataLoop(conn, addr):
    global writing_file ###
    global stop_reading_buffer
    global writing_file_id
    
    connection_lost = False
    while not connection_lost and not close_sockets:
        while not stop_reading_buffer:
            try:
                data = conn.recv(CHUNK)
                #print(data)
            except:
                print('Connection was lost')
                stop()
                connection_lost = True
                break
            if not data: break
            if data == b'SOF':
                print('[DEBUG] Start of file received. Current id: ' + str(writing_file_id))
                #create a new file with the currend fileID
                createNewTemp(str(writing_file_id))
                continue
            if data == b'EOF':
                print('[DEBUG] End of file received. Current id: ' + str(writing_file_id))
                #close the just written file and increase the fileID
                writing_file.close()
                writing_file_id += 1
            #    stop_reading_buffer = True
                break
            writing_file.write(data)
    conn.close()


def commandLoop(conn, addr):
    connection_lost = False
    global stop_reading_buffer
    global notify_song_skipped_flag
    while not connection_lost and not close_sockets:
        try:
            data = conn.recv(CHUNK)
        except:
            print('Command connection was lost')
            connection_lost = True
            break
        if data == b'PL':
            print('[INFO] Play command received')
            play()
        elif data == b'PS':
            pause()
            print('[INFO] Pause command received')
        elif data == b'ST':
            conn.send(b'SSC')
            print(isPlaying())
            stop()
            print('[INFO] Stop command received')
        elif data == b'VL':
            print('[INFO] Volume set command received')
            data = conn.recv(CHUNK)
            str_vol = data.decode("utf-8")
            int_vol = int(str_vol)
            set_volume(int_vol)
            print('[INFO] Volume is now set to: ' + str_vol)
        elif data == b'ID':
            stop_reading_buffer = False

        if notify_song_skipped_flag:
            print('Sending PN...')
            conn.send(b'PN')
            notify_song_skipped_flag = False

    conn.send(b'SC')
    conn.close()

def auto_track_select():
    global requested_playing_status
    global playing_file_id
    global notify_song_skipped_flag
    while True:
        if requested_playing_status == 'PLAY' and not isPlaying():
            if next_temp_exists():
                stop()
                playing_file_id += 1
                print('[DEBUG] Playing file ID: ' + str(playing_file_id))
                play()
                print('[DEBUG] Setting next media')
                notify_song_skipped_flag = True            

def emptyCacheOnStop():
    global cacheCleared
    global paused
    global requested_playing_status
    global playing_file_id
    while True:
        if requested_playing_status == 'PLAY' and not isPlaying():
            try:
                print('[INFO]Clearing cache...')
                stop()  # Called to assure that the player actually stops
                       # this is necessary in the case the player gets to
                       # the end of the file.
                if next_temp_exists():
                    ++playing_file_id
                    print('Playing file ID: ' + str(playing_file_id))
                    remove_temp(playing_file_id - 1)
                    play()
                else:
                    requested_playing_status = 'STOP'
                
            except os.error:
                print('Could not empty cache, it is in use!')


def startServer():
    #
    # Starts the server, listens for connections and writes received data to the local buffer
    #

    sck.listen(1)
    cmd_sck.listen(1)

    conn, addr = sck.accept()
    cconn, caddr = cmd_sck.accept()

    print(
    'Connection established: Data connection {0} \t Command connection {1}',
    addr,
     caddr)

    global stop_reading_buffer
    stop_reading_buffer = False

    clearLocalBuffer()

    server_loop_thread = Thread(target=startDataLoop, args=(conn, addr,))
    server_loop_thread.setDaemon(True)
    server_loop_thread.start()
    
    selector_thread = Thread(target=auto_track_select)
    selector_thread.setDaemon(True)
    selector_thread.start()
    
    command_loop_thread = Thread(target=commandLoop, args=(cconn, caddr))
    command_loop_thread.setDaemon(True)
    command_loop_thread.start()


def appendToFile(data):
    global writing_file
    writing_file = open(file_prefix + str(writing_file_id), 'ab')
    file.write(data)
    file.close()


def clearLocalBuffer():
    global writing_file_id
    for i in range(0, writing_file_id + 1):
        try:
            file_str = file_prefix + str(i)
            os.remove(file_str)
        except FileNotFoundError:
            print('[DEBUG]', file_str, ' was not found')
    writing_file_id = 0


def unbind():
    global stop_reading_buffer
    global close_sockets
    close_sockets = True
    stop_reading_buffer = True
    sck.close()
    cmd_sck.close()

def getTmpSize():
    try:
        res = os.path.getsize('tmp')
    except os.error:
        res = 0
    return res


def start():
    startServer()
    while getTmpSize() < 409600:
        continue
    play()


def set_volume(vol):
    global vlc_player
    vlc_player.audio_set_volume(vol)

def createNewTemp(suffix_id):
    global writing_file
    print ('[INFO] Creating new temp with index:' + suffix_id)
    writing_file = open(file_prefix + suffix_id, 'wb')
    writing_file.close()
    writing_file = open(file_prefix + suffix_id, 'ab')
    
def remove_temp(suffix_id):
    os.remove(file_prefix + str(suffix_id))

def next_temp_exists():
    return os.path.isfile(file_prefix + str(playing_file_id + 1))
