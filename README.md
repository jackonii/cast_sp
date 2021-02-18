Spotify app cast to Chromecast with simple token refresh mechanism.
=

It is nothing sophisticated, but it works. SP Token is valid for 1h. Ten minutes earlier token is being refreshed. Current app on Chromecast is being replaced by new one with valid token. Script is waiting with app replacing till current track is over (unless track will not end within 595 sec).

You have to add:

    CAST_NAME =""   # Your chromecast name

and

    SP_DC = ""  # Data to be obtained from cookies

    SP_KEY = ""  # Check https://github.com/enriquegh/spotify-webplayer-token/ for how to obtain it.


Dependencies:
=


    pip3 install spotify_token

    pip3 install spotipy

    pip3 install pychromecast


Tested with python 3.7.3 on Raspbian

