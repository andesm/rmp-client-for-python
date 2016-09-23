#!/usr/bin/python3
# coding=utf-8

import copy
import os
import random

import math
import select
import shutil
import signal
import sys
import termios

import json
import requests
from mutagen.mp4 import MP4
from mutagen.easyid3 import EasyID3


class RmpRank:
    def __init__(self, json_data, file):
        if json_data is None:
            self.file = file
            self.json_data = self._make_rmp_from_tag()
        else:
            self.file = json_data['file']
            self.json_data = json_data

        self.id = self.json_data['id']
        self.now = self.json_data['now']
        self.skip = self.json_data['skip']
        self.count = self.json_data['count']
        self.repeat = self.json_data['repeat']
        self.score = self.json_data['score']

    def set_id(self, json_data):
        self.json_data = json_data
        self.id = json_data['id']

    def _make_rmp_from_tag(self):
        if self.file.endswith(".m4a"):
            return self._make_rmp_from_mp4()
        elif self.file.endswith(".mp3"):
            return self._make_rmp_from_mp3()
        else:
            print(self.get_music_path())
            exit(1)

    def _make_rmp_from_mp3(self):
        tags = ('composer', 'genre', 'tracknumber', 'album', 'artist', 'date', 'title')

        audio = EasyID3(self.get_music_path())

        for tag in tags:
            if tag not in audio or not audio[tag][0]:
                if tag == 'tracknumber':
                    audio[tag] = ['0']
                else:
                    audio[tag] = ['none']

        file_url = self.file.replace(' ', '%20')

        return {'title': audio['title'][0][:100],
                'album': audio['album'][0],
                'artist': audio['artist'][0],
                'genre': audio['genre'][0],
                'file': self.file,
                'source': file_url,
                'image': 'none',
                'trackNumber': int(audio['tracknumber'][0]),
                'totalTrackCount': 0,
                'duration': 0,
                'site': 'http://kotetu.flg.jp/~andesm/music/',
                'now': 0,
                'skip': 0,
                'count': 0,
                'repeat': 0,
                'score': 0,
                'id': 0}

    def _make_rmp_from_mp4(self):
        tags = ('\xa9nam', '\xa9alb', '\xa9ART', '\xa9gen', 'trkn')

        audio = MP4(self.get_music_path())

        for tag in tags:
            if tag not in audio:
                if tag == 'trkn':
                    audio[tag] = [(0, 0)]
                else:
                    audio[tag] = ['none']
        file_url = self.file.replace(' ', '%20')
        genre_mi = audio['\xa9gen'][0].replace('/', ',')

        return {'title': audio['\xa9nam'][0],
                'album': audio['\xa9alb'][0],
                'artist': audio['\xa9ART'][0],
                'genre': genre_mi,
                'file': self.file,
                'source': file_url,
                'image': 'none',
                'trackNumber': audio['trkn'][0][0],
                'totalTrackCount': audio['trkn'][0][1],
                'duration': 0,
                'site': 'http://kotetu.flg.jp/~andesm/music/',
                'now': 0,
                'skip': 0,
                'count': 0,
                'repeat': 0,
                'score': 0,
                'id': 0}

    def get_music_path(self):
        return 'Music/' + self.file

    def play_now(self):
        if self.now == 0:
            return True
        else:
            self.now -= 1
            return False

    def play_back(self):
        self.repeat += 1
        self.score = self.count + self.repeat - (self.now + self.skip)

    def play_skip(self):
        self.now += self.skip + 1
        # 0 -> 1 -> 3 -> 6 -> 10 -> 15 -> 21 -> 28 -> 36
        n = (1 + math.sqrt(1 + 8 * self.skip)) / 2 + 1
        self.skip = int(((n - 1) * n) / 2)
        if 0 < self.repeat:
            self.repeat -= 1
        self.score = self.count + self.repeat - (self.now + self.skip)

    def play_normal(self):
        self.now += 1
        self.count += 1
        self.skip = int(self.skip / 2)
        self.score = self.count + self.repeat - (self.now + self.skip)

    def to_post_json(self):
        return json.dumps(self.json_data, ensure_ascii=False).encode("utf-8")

    def to_put_json(self):
        self.json_data['now'] = self.now
        self.json_data['skip'] = self.skip
        self.json_data['count'] = self.count
        self.json_data['repeat'] = self.repeat
        self.json_data['score'] = self.score
        return json.dumps(self.json_data, ensure_ascii=False).encode("utf-8")


class MusicProvider:
    SITE_URL = 'http://192.168.1.168/app/'

    def __init__(self):
        self.rmp_data_list = []
        self.all = 0
        self.next = 0
        self.count = 0
        self.new = 0
        self.now_music = None

        self.client = requests.session()
        self.client.get(MusicProvider.SITE_URL + 'rmp/api-auth/login/')
        csrftoken = self.client.cookies['csrftoken']
        payload = {'next': '/app/rmp/',
                   'csrfmiddlewaretoken': csrftoken,
                   'username': 'andesm',
                   'password': 'AkdiJ352o',
                   'submit': 'Log in'}
        self.client.post(MusicProvider.SITE_URL + 'rmp/api-auth/login/',
                         data=payload)
        r = self.client.get(MusicProvider.SITE_URL + 'rmp/music/')
        rmp_json = r.json()

        music_file = {}
        for data in rmp_json:
            rmp = RmpRank(data, None)
            self.rmp_data_list.append(rmp)
            music_file[rmp.file] = rmp
            self.all += 1
            if rmp.now == 0:
                self.next += 1
            if self.count < rmp.count:
                self.count = rmp.count

        for root, _, files in os.walk("./Music"):
            for file in files:
                if file.endswith(".m4a") or file.endswith(".mp3"):
                    file = os.path.join(root, file)[8:]
                    if file not in music_file:
                        rmp_data = RmpRank(None, file)
                        self._post_rmp_data(rmp_data)
                        self.rmp_data_list.append(rmp_data)
                        self.new += 1

        sorted_rmp_data_list = sorted(self.rmp_data_list,
                                      key=lambda rmp: rmp.score,
                                      reverse=True)
        random.shuffle(self.rmp_data_list)
        self.rmp_data_iterator = iter(self.rmp_data_list)
        self._set_next_now_music()

        #i = 0
        #shutil.rmtree('portable')
        #os.mkdir('portable')
        #for rmp in sorted_rmp_data_list:
        #    os.symlink('../music/' + rmp.file, 'portable/' + str(i) + '.m4a')
        #    i += 1
        #    if i == 300:
        #        break

    def _post_rmp_data(self, rmp_data):
        url = MusicProvider.SITE_URL + 'rmp/music/'
        csrftoken = self.client.cookies['csrftoken']
        r = self.client.post(url,
                             data=rmp_data.to_post_json(),
                             headers={'X-CSRFToken': csrftoken,
                                      'content-type': 'application/json'})
        print(rmp_data.json_data)
        print(r.text)
        rmp_data.set_id(r.json())

    def _put_rmp_data(self):
        url = MusicProvider.SITE_URL + 'rmp/music/' + str(self.now_music.id) + '/'
        csrftoken = self.client.cookies['csrftoken']
        self.client.put(url,
                        data=self.now_music.to_put_json(),
                        headers={'X-CSRFToken': csrftoken,
                                 'content-type': 'application/json'})

    def _set_next_now_music(self):
        while True:
            self.now_music = next(self.rmp_data_iterator, None)
            if self.now_music is None:
                self.rmp_data_iterator = iter(self.rmp_data_list)
                self.now_music = next(self.rmp_data_iterator, None)
            if self.now_music.play_now():
                break

    def handle_completion(self):
        self.now_music.play_normal()
        self._put_rmp_data()
        self._set_next_now_music()

    def handle_skip_to_next(self):
        self.now_music.play_skip()
        self._put_rmp_data()
        self._set_next_now_music()

    def handle_skip_to_previous(self):
        self.now_music.play_back()


class Playback:
    def __init__(self, music_provider):
        self.music_provider = music_provider
        self.pid = 0

    def play(self):
        self.pid = os.fork()
        if self.pid == 0:
            os.execl('/usr/bin/mplayer',
                     'mplayer',
                     '-novideo',
                     '-really-quiet',
                     '-slave',
                     self.music_provider.now_music.get_music_path())

    def stop(self):
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)

    def is_play(self):
        zpid, _ = os.waitpid(self.pid, os.WNOHANG)
        if 0 < zpid:
            return True
        else:
            return False


class TerminalView:
    command_disp = {'b': 'repeat', 's': 'skip  ', 'n': '      '}

    def __init__(self, music_provider, playback):
        self.music_provider = music_provider
        self.playback = playback

    def print_statistics(self):
        print("Next  : %4d" % self.music_provider.next)
        print("New   : %4d" % self.music_provider.new)
        print("Count : %4d" % self.music_provider.count)
        print("All   : %4d" % self.music_provider.all)

    def wait_command(self):
        while True:
            self._print_header()
            self.playback.play()

            command = self._get_command()

            if command == 'q':
                exit(0)

            self._print_command_before(command)

            if command == 'b':
                self.music_provider.handle_skip_to_previous()
            elif command == 's':
                self.music_provider.handle_skip_to_next()
            elif command == 'n':
                self.music_provider.handle_completion()

            self._print_command_after()

            if command == 'b':
                continue
            elif command == 's' or command == 'n':
                break

    @staticmethod
    def _getch():
        fd = sys.stdin.fileno()
        new = termios.tcgetattr(fd)
        old = copy.copy(new)
        new[3] = new[3] & ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(fd, termios.TCSANOW, new)

        ch = None
        rlist, _, _ = select.select([fd], [], [], 1)
        if rlist:
            ch = sys.stdin.read(1)
        termios.tcsetattr(fd, termios.TCSANOW, old)
        return ch

    def _get_command(self):
        command = ''
        while True:
            command = self._getch()
            if command == 's' or command == 'q' or command == 'b':
                self.playback.stop()
                break
            else:
                if self.playback.is_play():
                    command = 'n'
                    break

        return command

    def _print_header(self):
        print("- %s [sc: %d, sk: %d, co: %d, re: %d]"
              % (self.music_provider.now_music.file,
                 self.music_provider.now_music.score,
                 self.music_provider.now_music.skip,
                 self.music_provider.now_music.count,
                 self.music_provider.now_music.repeat))

    def _print_command_before(self, command):
        print("    %s [sc: %d, sk: %d, co: %d, re: %d] -> "
              % (TerminalView.command_disp[command],
                 self.music_provider.now_music.score,
                 self.music_provider.now_music.skip,
                 self.music_provider.now_music.count,
                 self.music_provider.now_music.repeat), end='')

    def _print_command_after(self):
        print("[sc: %d, sk: %d, co: %d, re: %d]"
              % (self.music_provider.now_music.score,
                 self.music_provider.now_music.skip,
                 self.music_provider.now_music.count,
                 self.music_provider.now_music.repeat))


if __name__ == "__main__":

    music_provider = MusicProvider()
    playback = Playback(music_provider)
    terminal_view = TerminalView(music_provider, playback)

    terminal_view.print_statistics()

    while True:
        terminal_view.wait_command()
