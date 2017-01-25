#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib
import mimetypes
import random

import tornado.testing
import tornado.web
from tornado.httputil import parse_cookie, HTTPHeaders
from tornado.web import decode_signed_value
from tornado.httpclient import AsyncHTTPClient, HTTPError

import secret_conf
import application
from constants import *
from query import *

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
		'rights': CAN_SEE_REPORTS 	 | CAN_UPLOAD_REPORTS |
			  	  CAN_DELETE_REPORTS | CAN_SEE_USERS 	  | CAN_EDIT_USERS,
		'password': '111111'
	}
]

test_error_users = [
	{
		'email': 'testmail8',
		'name': 'Name Error#',
		'rights': CAN_SEE_USERS,
		'password': ''
	},
	{
		'email': 'testmail8@mail.ru',
		'name': 'Blanks in the end   ',
		'rights': CAN_SEE_USERS,
		'password': 'qwe'
	},
	{
		'email': '    @mail.ru',
		'name': 'Emails blank',
		'rights': CAN_EDIT_USERS,
		'password': 'qweasdzxc'
	}
]

test_duplicate_users = [
	{
		'email': 'testmail8@mail.ru',
		'name': 'Mr.Duplicate1',
		'rights': CAN_SEE_USERS,
		'password': 'abcdef'
	},
	{
		'email': 'testmail8@mail.ru',
		'name': 'Mr.Duplicate2',
		'rights': CAN_SEE_USERS,
		'password': 'abcdef'
	}
]

test_edited_users = [
	{
		'email': 'testmail6@mail.ru',
		'name': 'Mr.Editer',
		'rights': CAN_SEE_USERS | CAN_EDIT_USERS,
		'password': '123456'
	},
	{
		'email': 'testmail7@mail.ru',
		'name': 'Mr.Deleter',
		'rights': CAN_EDIT_USERS,
		'password': '654321'
	},
]

test_new_edited_users = [
	{
		'email': 'newtestmail6@mail.ru',
		'name': 'Mr.Editer Jr',
		'rights': CAN_SEE_REPORTS | CAN_UPLOAD_REPORTS |
			  	  CAN_DELETE_REPORTS | CAN_SEE_USERS | 
			 	  CAN_EDIT_USERS,
		'password': '123456'
	},
	{
		'email': 'newtestmail7@mail.ru',
		'name': 'Mr.Deleter Jr',
		'rights': CAN_SEE_REPORTS | CAN_UPLOAD_REPORTS,
		'password': '654321'
	},
]


##
# Get the type of the file for encoding in a HTTP body.
# @param file Name of the file.
# @retval HTTP content type.
#
def get_file_http_type(filename):
	if type(filename) == bytes:
		filename = filename.decode('utf-8')
	return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

##
# Create a random boundary string for the HTTP request.
#
def generate_random_boundary():
	random_key = ''
	for i in range(5):
		random_key += str(random.random())
	boundary = '----------InitialBoundary%s$' % random_key
	return boundary

##
# Encode files and key-value pairs in HTTP body.
# The feature of the function is that it encodes files slightly
# another way than simple key-values, so these files can be
# correctrly processed by Tornado.
# @param fields Dictionary of parameters.
# @param files  Sequence of (parameter_name, filename,
#               file_content) elements.
# @retval Tuple with HTTP content type and binary body of a HTTP
#         request.
#
def encode_multipart_formdata(fields, files):
	boundary = generate_random_boundary()
	is_unique = False
	#
	# Check that boundary is unique.
	#
	while not is_unique:
		is_unique = True
		for key, value in fields.items():
			if boundary in key or boundary in value:
				is_unique = False
				break
		if not is_unique:
			boundary = generate_random_boundary()
			continue
		for (parameter_name, filename, file_content) in files:
			if boundary in parameter_name or boundary in filename\
			   or boundary.encode('utf-8') in file_content:
				is_unique = False
				break
		if not is_unique:
			boundary = generate_random_boundary()
			continue
	body = []
	#
	# For details @sa HTTP documentation.
	#
	for key, value in fields.items():
		body.append('--' + boundary)
		body.append('Content-Disposition: form-data; name="%s"' % key)
		body.append('')
		body.append(value)
	for (parameter_name, filename, file_content) in files:
		body.append('--' + boundary)
		body.append('Content-Disposition: form-data; name="%s"; '\
			    'filename="%s"' % (parameter_name, filename))
		body.append('Content-Type: %s' % get_file_http_type(filename))
		body.append('')
		body.append(file_content)
	body.append('--' + boundary + '--')
	body.append('')
	bytes_body = []
	for line in body:
		if type(line) == str:
			line = line.encode('utf-8')
		bytes_body.append(line)
	#
	# Carriage Return and Line Feed.
	#
	crlf = b'\r\n'
	body = crlf.join(bytes_body)
	content_type = 'multipart/form-data; boundary=%s' % boundary
	return content_type, body

##
# Decodes the specified cookie from the HTTPResponse.
# @param response HTTPResponse object.
# @param name     Name of the cookie to find.
# @param max_age  Maximal age of the searched cookie.
#
# @retval     None Cookie not found.
# @retval not None Success.
#
def decode_cookie(response, name, max_age):
	cookies = response.headers.get_list('Set-Cookie')
	for cookie in cookies:
		parsed = parse_cookie(cookie)
		if name not in parsed:
			continue
		result = decode_signed_value(secret_conf.cookie_secret, name,
					     parsed[name], max_age)
		return result
	return None

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

	##
	# Login user using the specified email and password.
	# @param email    Email address, string.
	# @param password User password, string.
	# @param kwargs   Additional arguments for client.fetch().
	#                 @sa AsyncHTTPClient.fetch()
	# @retval 'error' in answer - Error during the request.
	# @retval Dictionary with cookie 'headers' key,
	#         'id' - user identifier, 'name' - user name,
	#         'rights' - mask of the user rights.
	#
	@tornado.gen.coroutine
	def login_user(self, email, password, **kwargs):
		client = self.get_client()
		#
		# Post the credentials to the login url.
		#
		post_data = {}
		if email is not None:
			post_data['email'] = email
		if password is not None:
			post_data['password'] = password
		body = urllib.parse.urlencode(post_data)
		response = None
		try:
			url = self.get_url('/login')
			response = yield client.fetch(url, method="POST",
						      body=body,
						      follow_redirects=False,
						      **kwargs)
		except HTTPError as e:
			#
			# Catch redirect to the main page.
			# @sa class LoginHandler which
			# makes redirect in case of
			# success login.
			#
			response = e.response
		if response.code != 302:
			return { 'error': 'Failed to login',
				 'response': response }
		#
		# Parse cookies.
		#
		user_id = None
		user_name = None
		rights = None

		user_id = int(decode_cookie(response, 'user_id', 1))
		user_name = decode_cookie(response, 'user_name', 1)
		user_name = user_name.decode('utf-8')
		rights = int(decode_cookie(response, 'rights', 1))
		#
		# Follow the redirect url.
		#
		headers = self.build_cookie_headers(response)
		location = response.headers.get_list('Location')[0]
		url = self.get_url(location)
		response = yield client.fetch(url, method="GET",
						  headers=headers)
		#
		# Check that the page contains the link to
		# logout - it is the sign that login was
		# succesfull.
		#
		body = response.body.decode('utf-8')
		self.assertIn('logout', body)
		return { 'headers': headers, 'id': user_id, 'name': user_name,
			 'rights': rights }

	##
	# Insert users for testing
	#
	@tornado.gen.coroutine
	def insert_users(self, tx, users):
		for user in users:
			passwd = user['password']
			salt, pass_hash = \
				secret_conf.generate_password_hash(passwd)
			yield insert_user(tx, user['email'], pass_hash, salt,
					  user['name'], user['rights'])
