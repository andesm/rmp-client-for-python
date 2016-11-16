# coding=utf-8

import sys
import json
import requests

SITE_URL = 'https://flg.jp/apps/'

args = sys.argv
io = open(args[1])
restore_json = json.load(io)

client = requests.session()
client.get(SITE_URL + 'rmp/api-auth/login/')
csrftoken = client.cookies['csrftoken']
payload = {'next': '/app/rmp/',
           'csrfmiddlewaretoken': csrftoken,
           'username': 'admin',
           'password': 'djangoadmin',
           'submit': 'Log in'}
client.post(SITE_URL + 'rmp/api-auth/login/', data=payload)
r = client.get(SITE_URL + 'rmp/music/')
if r.status_code != 200:
    raise Exception(r.text)

get_json = r.json()

restore_file = {}
for rmp in restore_json:
    restore_file[rmp['file']] = rmp

get_json_file = {}
for rmp in get_json:
    get_json_file[rmp['file']] = rmp
    
csrftoken = client.cookies['csrftoken']

for rmp in restore_json:
    if rmp['file'] not in get_json_file:
        url = SITE_URL + 'rmp/music/'
        data = json.dumps(rmp, ensure_ascii=False).encode("utf-8")
        print('post : ', rmp)
        r = client.post(url, data=data,
                       headers={'X-CSRFToken': csrftoken,
                                'content-type': 'application/json'})
        if r.status_code != 201:
            raise Exception(r.text)

for rmp in get_json:
    restore_rmp = restore_file[rmp['file']]
    if restore_rmp['file'] == rmp['file'] and  (rmp['count'] < restore_rmp['count'] or rmp['skip'] < restore_rmp['skip']):
        rmp['count'] = restore_rmp['count']
        rmp['skip'] = restore_rmp['skip']
        rmp['repeat'] = restore_rmp['repeat']
        rmp['score'] = restore_rmp['score']
        rmp['now'] = restore_rmp['now']
        url = SITE_URL + 'rmp/music/' + str(rmp['id']) + '/'
        data = json.dumps(rmp, ensure_ascii=False).encode("utf-8")
        print('put : ', rmp)
        r = client.put(url, data=data,
                       headers={'X-CSRFToken': csrftoken,
                                'content-type': 'application/json'})
        if r.status_code != 200:
            raise Exception(r.text)

            
