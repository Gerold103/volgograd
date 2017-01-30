#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tormysql

pool = None

def connect(**kwargs):
	global pool
	pool = tormysql.helpers.ConnectionPool(**kwargs)

def begin():
	assert(pool)
	return pool.begin()
