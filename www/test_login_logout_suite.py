#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib

import tornado.testing
import tornado.gen
from tornado.httpclient import HTTPError

import application
import secret_conf
from constants import *
from query import *
from base_test_suite import BaseTestSuite, test_users

##
# Test that user can login and logout using his credentials.
#
class TestSuiteLoginLogout(BaseTestSuite):
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

		user_id = int(self.decode_cookie(response, 'user_id', 1))
		user_name = self.decode_cookie(response, 'user_name', 1)
		user_name = user_name.decode('utf-8')
		rights = int(self.decode_cookie(response, 'rights', 1))
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
	# Ensure that an unaurhorized user will be redirected to
	# /login from any page.
	#
	@tornado.gen.coroutine
	def check_login_redirect(self, url, **kwargs):
		client = self.get_client()
		try:
			response = yield client.fetch(url, **kwargs,
						      follow_redirects=False)
		except HTTPError as e:
			response = e.response
		if kwargs['method'] == 'GET':
			self.assertEqual(response.code, 302)
			location = response.headers.get_list('Location')[0]
			self.assertIn('/login', location)
		else:
			self.assertEqual(response.code, 403)

	@tornado.testing.gen_test
	def test1_redirect_anon(self):
		#
		# Check redirect to /login on any anauthorized
		# request.
		#
		yield self.check_login_redirect(url=self.get_url('/upload'),
						method='GET')
		yield self.check_login_redirect(url=self.get_url('/upload'),
						method='POST', body='bad_file')
		logger.info('ok - redirect on upload')

		yield self.check_login_redirect(url=self.get_url('/show_table'),
						method='GET')
		logger.info('ok - redirect on show table')

		yield self.check_login_redirect(url=self.get_url('/drop_report'),
						method='GET')
		logger.info('ok - redirect on drop')

		yield self.check_login_redirect(url=self.get_url('/water_consum'),
						method='GET')
		logger.info('ok - redirect on water consuming page')

		yield self.check_login_redirect(url=self.get_url('/year_plot'),
						method='GET')
		logger.info('ok - redirect on year plot')

		yield self.check_login_redirect(url=self.get_url('/get_year_parameter'),
						method='GET')
		logger.info('ok - redirect on getting year parameter')

		yield self.check_login_redirect(url=self.get_url('/temperature'),
						method='GET')
		logger.info('ok - redirect on month temperature')

		yield self.check_login_redirect(url=self.get_url('/get_month_parameter'),
						method='GET')
		logger.info('ok - redirect on getting month parameter')


	@tornado.testing.gen_test
	def test2_success_login(self):
		application.connect_db()
		#
		# Authorize users using correct passwords
		#
		for n, user in enumerate(test_users):
			logged = yield self.login_user(user['email'],
						       user['password'])
			self.assertEqual(logged['id'], n + 1)
			self.assertEqual(logged['name'], user['name'])
			self.assertEqual(logged['rights'], user['rights'])
			logger.info('ok - User {} login'.format(user['email']))

	@tornado.testing.gen_test
	def test3_fail_login(self):
		application.connect_db()
		user = test_users[0]

		#
		# Double login
		#
		logged = yield self.login_user(user['email'], user['password'])
		self.assertIn('name', logged)
		self.assertEqual(logged['name'], user['name'])

		double_logged =\
			yield self.login_user(user['email'], user['password'],
					      headers=logged['headers'])
		self.assertIn('error', double_logged)
		response = double_logged['response']
		body = response.body.decode('utf-8')
		self.assertIn(ERR_LOGIN, body)
		self.assertIn('Вы уже авторизованы', body)

		#
		# Doesn't specify email
		#
		logged = yield self.login_user(None, user['password'])
		self.assertIn('error', logged)
		response = logged['response']
		body = response.body.decode('utf-8')
		self.assertIn(ERR_LOGIN, body)
		self.assertIn('Не указан email', body)

		#
		# Doesn't specify password
		#
		logged = yield self.login_user(user['email'], None)
		self.assertIn('error', logged)
		response = logged['response']
		body = response.body.decode('utf-8')
		self.assertIn(ERR_LOGIN, body)
		self.assertIn('Не указан пароль', body)

		#
		# Not existing email
		#
		logged = yield self.login_user('not_existing@', 'pass')
		self.assertIn('error', logged)
		response = logged['response']
		body = response.body.decode('utf-8')
		self.assertIn(ERR_404, body)
		self.assertIn('не зарегистрирован', body)

		#
		# Incorrect password
		#
		logged = yield self.login_user(user['email'], 'pass')
		self.assertIn('error', logged)
		response = logged['response']
		body = response.body.decode('utf-8')
		self.assertIn(ERR_ACCESS, body)
		self.assertIn('Неправильный пароль', body)
