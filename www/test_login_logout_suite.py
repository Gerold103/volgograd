#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib

import tornado.testing
from tornado.httpclient import AsyncHTTPClient, HTTPError

import application
import secret_conf
from constants import *
from query import *
from base_test_suite import BaseTestSuite, test_users

##
# Test that user can login and logout using his credentials.
#
class TestSuiteLoginLogout(BaseTestSuite):
	@tornado.testing.gen_test
	def test1_success_login(self):
		#
		# Authorize users using correct passwords
		#
		for n, user in enumerate(test_users):
			email = user['email']
			password = user['password']
			#
			# Post the credentials to the login url.
			#
			post_data = { 'email': email, 'password': password }
			body = urllib.parse.urlencode(post_data)
			client = AsyncHTTPClient(self.io_loop)
			response = None
			try:
				url = self.get_url('/login')
				response = yield client.fetch(url, method="POST",
							      body=body,
							      follow_redirects=False)
			except HTTPError as e:
				#
				# Catch redirect to the main page.
				# @sa class LoginHandler which
				# makes redirect in case of
				# success login.
				#
				response = e.response
			self.assertEqual(response.code, 302)
			#
			# Parse cookies.
			#
			user_id = None
			user_name = None
			rights = None

			user_id = self.decode_cookie(response, 'user_id', 1)
			user_id = int(user_id)
			self.assertEqual(user_id, n + 1)

			user_name = self.decode_cookie(response, 'user_name', 1)
			user_name = user_name.decode('utf-8')
			self.assertEqual(user_name, user['name'])

			rights = self.decode_cookie(response, 'rights', 1)
			rights = int(rights)
			self.assertEqual(rights, user['rights'])
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
			logger.info('ok - User {} login'.format(email))
