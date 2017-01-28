#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tornado.testing
import tornado.web
from tornado.httputil import parse_cookie, HTTPHeaders
from tornado.web import decode_signed_value
from tornado.httpclient import AsyncHTTPClient

import secret_conf
import application
from constants import *

test_users = [
	{
		'email': 'testmail1@mail.ru',
		'name': 'Mr.Uploader',
		'rights': CAN_UPLOAD_REPORTS,
		'password': '123456'
	},
	{
		'email': 'testmail2@mail.ru',
		'name': 'Mr.Observer',
		'rights': CAN_SEE_REPORTS,
		'password': '654321'
	},
	{
		'email': 'testmail3@mail.ru',
		'name': 'Mr.Deleter',
		'rights': CAN_DELETE_REPORTS,
		'password': '123321'
	},
	{
		'email': 'testmail4@mail.ru',
		'name': 'Mr.Worker',
		'rights': CAN_SEE_REPORTS | CAN_UPLOAD_REPORTS,
		'password': '321123'
	},
	{
		'email': 'testmail5@mail.ru',
		'name': 'Mr.Admin',
		'rights': CAN_SEE_REPORTS | CAN_UPLOAD_REPORTS |
			  CAN_DELETE_REPORTS,
		'password': '111111'
	}
]

##
# Base class for testing suites.
# It provides methods to work with secure cookies and to setting
# up each test suite.
#
class BaseTestSuite(tornado.testing.AsyncHTTPTestCase):
	def __init__(self, *args, **kwargs):
		self.client = None
		super(BaseTestSuite, self).__init__(*args, **kwargs)

	def get_client(self):
		if self.client is None:
			self.client = AsyncHTTPClient(self.io_loop)
		return self.client

	def get_app(self):
		return tornado.web.Application(
			handlers=application.handlers_list,
			template_path=application.template_path,
			static_path=application.static_path,
			cookie_secret=secret_conf.cookie_secret,
			login_url=application.login_url
		)

	##
	# Decodes the specified cookie from the HTTPResponse.
	# @param response HTTPResponse object.
	# @param name     Name of the cookie to find.
	# @param max_age  Maximal age of the searched cookie.
	#
	# @retval     None Cookie not found.
	# @retval not None Success.
	#
	def decode_cookie(self, response, name, max_age):
		cookies = response.headers.get_list('Set-Cookie')
		for cookie in cookies:
			parsed = parse_cookie(cookie)
			if name not in parsed:
				continue
			result = decode_signed_value(secret_conf.cookie_secret,
						     name, parsed[name],
						     max_age)
			return result
		return None

	##
	# Returns a dictionary with one HTTPHeader: Cookie.
	# It simple copies cookies from response into the
	# request headers.
	# @param response HTTPResponse object.
	# @retval Dictionary with one key: 'Cookie'.
	#
	def build_cookie_headers(self, response):
		cookies = response.headers.get_list('Set-Cookie')
		#
		# ';' - is used in HTTP syntax to divide the
		#       parameters.
		#
		result_cookie = '; '.join(cookies)
		return { 'Cookie': result_cookie }
