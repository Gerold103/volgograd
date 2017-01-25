#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from pbkdf2 import crypt
from pbkdf2 import _makesalt as makesalt

db_host = None
db_user = None
db_passwd = None
db_name = "volgograd"
cookie_secret = None
max_db_connections = 20
db_idle_seconds = 7200
db_connection_timeout = 3
db_charset = 'utf8'

pepper = None

def generate_password_hash(password):
	global pepper
	salt = makesalt()
	return (salt, crypt(password + pepper, salt))

def check_password(password, salt, hashed_true):
	global pepper
	hashed = crypt(password + pepper, salt)
	return hashed_true == hashed

def parse_config():
	with open('secret_conf.json') as data:
		conf = json.load(data)
		global db_host
		global db_user
		global db_passwd
		global cookie_secret
		global pepper
		db_host = conf['db_host']
		db_user = conf['db_user']
		db_passwd = conf['db_passwd']
		cookie_secret = conf['cookie_secret']
		pepper = conf['pepper']
		if 'max_db_connections' in conf:
			max_db_connections = conf['max_db_connections']
		if 'db_idle_seconds' in conf:
			db_idle_seconds = conf['db_idle_seconds']
		if 'db_connection_timeout' in conf:
			db_connection_timeout = conf['db_connection_timeout']
		if 'db_charset' in conf:
			db_charset = conf['db_charset']
