#!/usr/bin/python3

import logging
import time
import sys
import pychromecast
from pychromecast.controllers.spotify import SpotifyController
import spotify_token as st
import spotipy
import json

# Your chromecast name
CAST_NAME = ""

# Data obtained from cookie. Check: https://github.com/enriquegh/spotify-webplayer-token
# for optaining cookie valid for 1 year

SP_DC = ""
SP_KEY = ""

URI = "spotify:playlist:2K8yefvBUtiZNidagTIeca"  # Chillout_session

class Error(Exception):
    pass


class NoValidToken(Error):
    """Raised if no valid token is found"""
    pass


def get_token(sp_dc, sp_key, force=False):
    #  Check for file with token and time
    try:
        if force:
            raise NoValidToken
        with open('sp_token', 'r') as file:
            data_file = json.load(file)
            sp_access_token = data_file['access_token']
            sp_expires = data_file['expires']
            if sp_expires - time.time() < 5:  # If token expires within 5 min - go to generating of a new token
                raise NoValidToken
    # If token is out-of-date or no file found
    except (NoValidToken, FileNotFoundError):
        if force:
            logging.info("[TOKEN] Generating new token forced")
        else:
            logging.info("[TOKEN] Valid token not found. Generating new token.")
        data = st.start_session(sp_dc, sp_key)  # Get new token from Cookies
        sp_access_token = data[0]
        sp_expires = data[1]
        with open('sp_token', 'w') as file:  # Write new token and expiration time in file
            json.dump(
                {
                    "access_token": sp_access_token,
                    "expires": sp_expires
                }, file
            )
    logging.info(f"[TOKEN] New Spotify token valid till: {time.ctime(sp_expires)}")
    return sp_access_token, sp_expires


def progressbar(time_s, interval=40):
    period = time_s / interval
    for i in range(interval):
        if i == 0:
            sys.stdout.write('\r')
            text = '[' + '-' * interval + ']' + ' ' + '0.0%'
            sys.stdout.write(text)
            sys.stdout.flush()
        time.sleep(period)
        sys.stdout.write('\r')
        text = '[' + '#' * (i + 1) + '-' * ((interval - 1) - i) + ']' + ' ' + str(100 / interval * (i + 1)) + "%"
        sys.stdout.write(text)
        sys.stdout.flush()
    print()


def current_track(sp_client):
    sp_play = sp_client.current_playback()
    print()
    print("is playing: ", sp_play['is_playing'])
    if "playlist" in sp_play['context']['uri']:
        print("Playlist: ", sp_client.playlist(sp_play['context']['uri'], fields='name')['name'])
    print("Artists: ", end='')
    for i in range(len(sp_play['item']['artists'])):
        print(sp_play['item']['artists'][i]['name'], end='')
        if i == len(sp_play['item']['artists']) - 1:
            print()
        else:
            print(',', end=' ')
    print("Title: ", sp_play['item']['name'])
    print("progress: ", time.strftime('%H:%M:%S', time.gmtime(sp_play['progress_ms'] // 1000)))
    print("duration: ", time.strftime('%H:%M:%S', time.gmtime(sp_play['item']['duration_ms'] // 1000)))
    print("time_left: ", time.strftime('%H:%M:%S', time.gmtime(
        (int(sp_play['item']['duration_ms']) - int(sp_play['progress_ms'])) // 1000)))
    print("repeat state: ", sp_play['repeat_state'])
    print("shuffle state: ", sp_play['shuffle_state'])
    print()


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', datefmt='%b %d %H:%M:%S', level=logging.INFO)

chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=[CAST_NAME])
cast = None
for _cast in chromecasts:
    if _cast.name == CAST_NAME:
        cast = _cast
        break

if not cast:
    logging.info(f'No chromecast with name "{CAST_NAME}" discovered')
    sys.exit(1)

# Wait for connection to the chromecast
cast.wait()
cast.set_volume(1)  # Set volume to 100%
cast.quit_app()  # Quit current app on chromecast
time.sleep(1)  # Wait for app to quit

spotify_device_id = None

# Get token from Cookies
access_token, expires = get_token(SP_DC, SP_KEY)

# Create a spotify client
client = spotipy.Spotify(auth=access_token)

# Launch the spotify app on the cast we want to cast to
sp = SpotifyController(access_token, expires)
cast.register_handler(sp)
sp.launch_app()

if not sp.is_launched and not sp.credential_error:
    logging.info("[SPOTI] Failed to launch spotify controller due to timeout")
    cast.disconnect()
    sys.exit(1)
if not sp.is_launched and sp.credential_error:
    logging.info("[SPOTI] Failed to launch spotify controller due to credential error")
    cast.disconnect()
    sys.exit(1)

# Query spotify for active devices
devices_available = client.devices()

# Match active spotify devices with the spotify controller's device id
for device in devices_available["devices"]:
    if device["id"] == sp.device:
        spotify_device_id = device["id"]
        break

if not spotify_device_id:
    logging.info(f'[SPOTI] No device with id "{sp.device}" known by Spotify')
    logging.info(f'[SPOTI] Known devices: {devices_available["devices"]}')
    cast.disconnect()
    sys.exit(1)

# Start playback
client.start_playback(device_id=spotify_device_id, context_uri=URI)
time.sleep(1)
client.repeat('context')  # Repeat whole playlist

# Shut down discovery
pychromecast.discovery.stop_discovery(browser)

while True:
    token_refresh_interval = ((expires - time.time()) - 600)  # 600sec before token expires
    # if token_refresh_interval < 10:
    #     token_refresh_interval = 0
    logging.info(f"[TOKEN] Waiting until {time.ctime(time.time() + token_refresh_interval)} to refresh token")
    progressbar(token_refresh_interval)
    # Checking chromecast status
    if cast.status is not None:
        logging.info(f"[SPOTI] Active app ID on Chromecast: {cast.status.app_id}")
        if cast.status.app_id is None:
            logging.info("[SPOTI] No app connected to Chromecast. Exiting")
            cast.disconnect()
            sys.exit()
        elif cast.status.app_id != 'CC32E753':
            logging.info("[SPOTI] Another app connected to Chromecast. Exiting")
            cast.disconnect()
            sys.exit()
    else:
        logging.info("[SPOTI] No connection to Chromecast. Exiting")
        sys.exit()
    # Getting new token
    logging.info("[TOKEN] Generating new Spotify token")
    access_token, expires = get_token(SP_DC, SP_KEY, force=True)
    # logging.info(f"[TOKEN] New Spotify token valid till: {time.ctime(expires)}")
    # Recreating Spotify client with a new token
    client = spotipy.Spotify(auth=access_token)
    # Getting current playback status
    play = client.current_playback()
    # Checking player status
    if play:
        if play['device']['name'] != CAST_NAME:
            logging.info(f"[SPOTI] Spotify app is not connected to Chromecast {CAST_NAME}. Exiting")
            cast.disconnect()
            sys.exit()
    else:
        logging.info("[SPOTI] No player found. Exiting")
        cast.disconnect()
        sys.exit()
    # Checking current playback status
    time_left = (int(play['item']['duration_ms']) - int(play['progress_ms'])) / 1000
    if time_left < 595 and play['is_playing'] is True:  # Track ends within 595sec and is not paused
        logging.info(f"[SPOTI] Waiting till current track ends: {time_left} sec")
        time.sleep(time_left + 0.5)  # Sleep till track ends

    # Getting current player status
    play = client.current_playback()

    # Quitting current app on Chromecast
    logging.info("[SPOTI] Quitting current app on Chromecast")
    cast.quit_app()
    time.sleep(1)  # Waiting till app stops
    logging.info(f"[SPOTI] App status on Chromecast: {cast.status.app_id}")

    # Launch the spotify app on the cast we want to cast to
    logging.info("[SPOTI] Starting Spotify app on Chromecast")
    sp = SpotifyController(access_token, expires)
    cast.register_handler(sp)
    sp.launch_app()
    cast.wait()
    logging.info(f"[SPOTI] Current app on chromecast: {cast.status.app_id}")

    if not sp.is_launched and not sp.credential_error:
        logging.info("[SPOTI] Failed to launch spotify controller due to timeout")
        cast.disconnect()
        sys.exit(1)
    if not sp.is_launched and sp.credential_error:
        logging.info("[SPOTI] Failed to launch spotify controller due to credential error")
        cast.disconnect()
        sys.exit(1)

    # Query spotify for active devices
    devices_available = client.devices()

    # Match active spotify devices with the spotify controller's device id
    for device in devices_available["devices"]:
        if device["id"] == sp.device:
            spotify_device_id = device["id"]
            break

    if not spotify_device_id:
        logging.info(f'[SPOTI] No device with id "{sp.device}" known by Spotify')
        logging.info(f'[SPOTI] Known devices: {devices_available["devices"]}')
        cast.disconnect()
        sys.exit(1)

    # Transfer of current playback to app on Chromecast
    if not play['is_playing']:  # If track is paused
        client.transfer_playback(device_id=spotify_device_id, force_play=False)  # transfer as paused
    else:
        client.transfer_playback(device_id=spotify_device_id)  # transfer and force playback
    current_track(client)

