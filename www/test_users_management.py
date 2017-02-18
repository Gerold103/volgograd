#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib

import tornado.testing
import tornado.gen

import application
from constants import *
from base_test_suite import BaseTestSuite, test_users
from users_management import *

test_error_users = [
#
# Email errors.
#
	{
		'name': 'John Doe',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456',
		'error': ERR_EMAIL_ABSENSE
	},
	{
		'email': 'email_incorrect',
		'name': 'John Doe',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456',
		'error': ERR_EMAIL_FORMAT
	},
	{
		'email': 'e' * MAX_EMAIL_LENGTH + 'mail_correct@mail.ru',
		'name': 'John Doe',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456',
		'error': ERR_EMAIL_LENGTH
	},
#
# Name errors.
#
	{
		'email': 'email@mail.ru',
		'name': 'John Do' + 'e' * MAX_NAME_LENGTH,
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456',
		'error': ERR_NAME_LENGTH
	},
	{
		'email': 'email@mail.ru',
		'name': 'John Doe <script>alert("error!");</script>',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456',
		'error': ERR_NAME_FORMAT
	},
#
# Password errors.
#
	{
		'email': 'email@mail.ru',
		'name': 'John Doe',
		'see_reports': 'on',
		'error': ERR_PASSWORD_ABSENSE,
	},
	{
		'email': 'email@mail.ru',
		'name': 'John Doe',
		'see_reports': 'on',
		'password': '123',
		'password-repeat': '123',
		'error': ERR_PASSWORD_LENGTH,
	},
	{
		'email': 'email@mail.ru',
		'name': 'John Doe',
		'see_reports': 'on',
		'password': '1' * (MAX_PASSWORD_LENGTH + 1),
		'password-repeat': '1' * (MAX_PASSWORD_LENGTH + 1),
		'error': ERR_PASSWORD_LENGTH,
	},
	{
		'email': 'email@mail.ru',
		'name': 'John Doe',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '1234567',
		'error': ERR_PASSWORD_MATCH,
	},
#
# Rights errors.
#
	{
		'email': 'email@mail.ru',
		'name': 'John Doe',
		'see_reports': 'on',
		'edit_users': 'on',
		'password': '123456',
		'password-repeat': '123456',
		'error': ERR_RIGHTS_COMBINATION,
	},
	{
		'email': 'email@mail.ru',
		'name': 'John Doe',
		'see_users': 'on',
		'delete_reports': 'on',
		'password': '123456',
		'password-repeat': '123456',
		'error': ERR_RIGHTS_COMBINATION,
	},
#
# Duplicate error
#
	{
		'email': test_users[0]['email'],
		'name': 'John Doe',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456',
		'error': ERR_INSERT
	}
]

test_normal_users = [
	{
		'email': 'email1@mail.ru',
		'name': 'John Doe 1',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456'
	},
	{
		'email': 'email2@yandex.ru',
		'name': 'John Doe 2',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456'
	},
	{
		'email': 'email3@vkh-vlg.ru',
		'name': 'John Doe 3',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456'
	},
	{
		'email': 'email4@gmail.com',
		'name': 'John Doe 4',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456'
	},
	{
		'email': 'email5@corp.mail.ru',
		'name': 'John Doe 5',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456'
	},
	{
		'email': 'email6@corp.mail.ru',
		'name': 'John D.-M. 59 Алексеев',
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456'
	},
	{
		'email': 'email7@corp.mail.ru',
		'name': '', # Zero length name is allowed.
		'see_reports': 'on',
		'password': '123456',
		'password-repeat': '123456'
	}
]

##
# Tests users management subsystem - creation, editing and
# deletion of users.
#
class TestSuiteUsersManagement(BaseTestSuite):
	def __init__(self, *args, **kwargs):
		super(TestSuiteUsersManagement, self).__init__(*args, **kwargs)
		self.logged = None

	@tornado.gen.coroutine
	def get_logged(self):
		if self.logged:
			return self.logged
		admin = test_users[-1]
		self.logged = yield self.login_user(admin['email'],
						    admin['password'])
		self.assertNotIn('error', self.logged)
		return self.logged

	##
	# Post one of the users from global dictionaries above:
	# test_error_users and test_normal_users.
	# @param user Dictionary with post parameters for the user
	#             creation.
	# @retval String with content of the result HTML page.
	#
	@tornado.gen.coroutine
	def post_user(self, user):
		logged = yield self.get_logged()
		client = self.get_client()
		body = urllib.parse.urlencode(user)
		headers = logged['headers']
		response = yield client.fetch(self.get_url('/users_management'),
					      method='POST', headers=headers,
					      body=body)
		self.assertEqual(response.code, 200)
		return response.body.decode('utf-8')

	@tornado.testing.gen_test
	def test1_error_users(self):
		application.connect_db()
		for user in test_error_users:
			response = yield self.post_user(user)
			self.assertIn(user['error'], response)
		logger.info('ok - reject invalid users')

	@tornado.testing.gen_test
	def test2_ok_users(self):
		application.connect_db()
		for user in test_normal_users:
			response = yield self.post_user(user)
			#
			# 'user_was_created' is the anchor,
			# that is rendered special for testing in
			# case of successfull user creation,
			# @sa users_management.html file.
			#
			self.assertIn('user_was_created', response)
		logger.info('ok - permit normal users')
