#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tormysql
import tornado.gen

#
# Pool of connections to the database.
#
pool = None
#
# Global tornado application server.
#
app = None

#
# Arguments to creation of a new tornado application server.
# @sa class BaseTestSuite.
#
handlers_list = []
template_path = ''
static_path = ''
login_url = ''

def connect_db(**kwargs):
	global pool
	pool = tormysql.helpers.ConnectionPool(**kwargs)

def begin():
	assert(pool)
	return pool.begin()
