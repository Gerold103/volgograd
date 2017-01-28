#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tormysql
import tornado.gen

#
# Pool of connections to the database.
#
pool = None
#
# connect_db_args is a hook for tests. Tornado gen.test closes
# ioloop after each test together with db connection so in begin
# of each test we call connect_db().
# But arguments for the connection are initiaized in the main().
#
connect_db_args = {}
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

def connect_db():
	global pool
	pool = tormysql.helpers.ConnectionPool(**connect_db_args)

def begin():
	assert(pool)
	return pool.begin()
