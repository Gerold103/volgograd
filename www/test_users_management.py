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
	{# No any rights.
		'email': 'email@mail.ru',
		'name': 'John Doe',
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
		user = dict(user)
		user['action'] = 'create'
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

	@tornado.testing.gen_test
	def test3_test_users_show(self):
		application.connect_db()
		#
		# First, we test the users management page under
		# the admin account.
		#
		logged = yield self.get_logged()
		client = self.get_client()
		headers = logged['headers']
		response = yield client.fetch(self.get_url('/users_management'),
					      headers=headers, method='GET')
		body = response.body.decode('utf-8')
		#
		# The user with right on users edit must see the
		# following labels on the page.
		#
		self.assertIn('Управление пользователями', body)
		self.assertNotIn('user_was_created', body)
		self.assertNotIn('user_was_deleted', body)
		self.assertNotIn('user_was_edited', body)
		self.assertIn('Добавить пользователя', body)
		self.assertIn('modal fade user-modal-window', body)
		self.assertIn('Вперед <span aria-hidden="true">&rarr;</span>',
			      body)
		self.assertNotIn('<span aria-hidden="true">&larr;</span> Назад',
				 body)
		logger.info('ok - header of users page, if the current user '\
			    'can edit')
		# Check that on the page the correct list of users
		# is showed.
		#
		all_inserted = list(test_normal_users)
		all_inserted.extend(test_users)
		self.assertEqual(len(all_inserted), 12)
		key = lambda x: (not x['name'], x['name'], x['email'])
		all_inserted = sorted(all_inserted, key=key)
		for i, user in enumerate(all_inserted):
			if i >= USERS_ON_PAGE:
				break;
			self.assertIn('<td>%s</td>' % user['email'], body)
		logger.info('ok - first page of users list')
		#
		# Try to get the second page.
		#
		url = '%s?page=2' % self.get_url('/users_management')
		response = yield client.fetch(url, headers=headers,
					      method='GET')
		body = response.body.decode('utf-8')
		self.assertNotIn('Вперед <span aria-hidden="true">&rarr;</span>',
				 body)
		self.assertIn('<span aria-hidden="true">&larr;</span> Назад',
			      body)
		for i, user in enumerate(all_inserted):
			if i < USERS_ON_PAGE:
				continue
			if i >= USERS_ON_PAGE * 2:
				break;
			self.assertIn('<td>%s</td>' % user['email'], body)
		logger.info('ok - second page of users list')
		#
		# Get incorrect page.
		#
		url = self.get_url('/users_management')
		urls = [ '%s?page=-1' % url, '%s?page=abc' % url,
			 '%s?page=1000' % url ]
		for url in urls:
			response = yield client.fetch(url, headers=headers,
						      method='GET')
			body = response.body.decode('utf-8')
			self.assertIn(ERR_PAGE_NUMBER, body)
		logger.info('ok - incorrect page numbers')
		#
		# Make incorrect action.
		#
		url = self.get_url('/users_management')
		urls = [ '%s?action=del' % url, '%s?action=create' % url,
			 '%s?action=edit' % url, '%s?action=^' % url,
			 '%s?action=123' % url ]
		for url in urls:
			response = yield client.fetch(url, headers=headers,
						      method='GET')
			body = response.body.decode('utf-8')
			self.assertIn(ERR_ACTION, body)
		logger.info('ok - incorrect actions')

	@tornado.testing.gen_test
	def test4_delete_user(self):
		application.connect_db()
		logged = yield self.get_logged()
		client = self.get_client()
		headers = logged['headers']
		user = test_normal_users[0]
		tx = yield application.begin()
		id = yield get_user_by_email(tx, ['id', ], user['email'])
		id = id['id']
		url = '{}?id={}&action=delete'\
		      .format(self.get_url('/users_management'), id)
		response = yield client.fetch(url, headers=headers,
					      method='GET')
		body = response.body.decode('utf-8')
		self.assertIn('user_was_deleted', body)
		self.assertNotIn(user['email'], body)
		yield tx.commit()
		logger.info('ok - user was deleted')
		#
		# Recreate the deleted user.
		#
		yield self.post_user(user)

	@tornado.testing.gen_test
	def test5_edit_user(self):
		application.connect_db()
		logged = yield self.get_logged()
		client = self.get_client()
		headers = logged['headers']
		user = test_normal_users[0]
		self.assertEqual(user['name'], 'John Doe 1')
		self.assertEqual(user['email'], 'email1@mail.ru')
		post = dict(user)
		#
		# Edit email
		#
		tx = yield application.begin()
		id = yield get_user_by_email(tx, ['id', ], user['email'])
		yield tx.commit()
		id = id['id']
		post['email'] = 'email1_new@mail.ru'
		post['action'] = 'edit'
		post['id'] = id
		post['password'] = ''
		post['password-repeat'] = ''
		body = urllib.parse.urlencode(post)
		response = yield client.fetch(self.get_url('/users_management'),
					      headers=headers, method='POST',
					      body=body)
		body = response.body.decode('utf-8')
		self.assertIn('user_was_edited', body)
		self.assertIn(post['email'], body)
		logger.info("ok - user's email is edited")
		user['email'] = post['email']
		#
		# Change email to the existing email. Also we try
		# to change the password, but is must not happen,
		# since the duplicate error occures.
		#
		self.assertGreaterEqual(len(test_normal_users), 1)
		another_user = test_normal_users[1]
		post['email'] = another_user['email']
		post['password'] = 'new_password'
		post['password-repeat'] = 'new_password'
		body = urllib.parse.urlencode(post)
		response = yield client.fetch(self.get_url('/users_management'),
					      headers=headers, method='POST',
					      body=body)
		body = response.body.decode('utf-8')
		self.assertNotIn('user_was_edited', body)
		self.assertIn(ERR_INSERT, body)
		#
		# The user still can login with the old password.
		#
		response = yield self.login_user(user['email'],
						 user['password'])
		self.assertNotIn('error', response)
		self.assertIn('headers', response)
		logger.info("ok - it is forbidden to choose the existing email"\
			    " during an user editing")
		#
		# Send the old password as edited.
		#
		post = dict(user)
		post['action'] = 'edit'
		post['id'] = id
		body = urllib.parse.urlencode(post)
		response = yield client.fetch(self.get_url('/users_management'),
					      headers=headers, method='POST',
					      body=body)
		body = response.body.decode('utf-8')
		self.assertIn('user_was_edited', body)
		self.assertIn(post['email'], body)
		#
		# The user still can login.
		#
		response = yield self.login_user(user['email'],
						 user['password'])
		self.assertNotIn('error', response)
		self.assertIn('headers', response)
		logger.info('ok - an user can keep the old password')
		#
		# Try to set incorrect passwords.
		#
		post['password'] = '' # password-repeat remains.
		body = urllib.parse.urlencode(post)
		response = yield client.fetch(self.get_url('/users_management'),
					      headers=headers, method='POST',
					      body=body)
		body = response.body.decode('utf-8')
		self.assertNotIn('user_was_edited', body)
		self.assertIn(ERR_PASSWORD_ABSENSE, body)

		post['password'] = '123' # too short password.
		post['password-repeat'] = '123'
		body = urllib.parse.urlencode(post)
		response = yield client.fetch(self.get_url('/users_management'),
					      headers=headers, method='POST',
					      body=body)
		body = response.body.decode('utf-8')
		self.assertNotIn('user_was_edited', body)
		self.assertIn(ERR_PASSWORD_LENGTH, body)

		# Password differs from password-repeat.
		post['password'] = '123456'
		post['password-repeat'] = '1234567'
		body = urllib.parse.urlencode(post)
		response = yield client.fetch(self.get_url('/users_management'),
					      headers=headers, method='POST',
					      body=body)
		body = response.body.decode('utf-8')
		self.assertNotIn('user_was_edited', body)
		self.assertIn(ERR_PASSWORD_MATCH, body)
		logger.info('ok - new password can not be invalid')
		#
		# Edit the current user.
		#
		post = {}
		post['email'] = logged['email']
		post['action'] = 'edit'
		post['id'] = logged['id']
		post['see_reports'] = 'on'
		post['upload_reports'] = 'on'
		post['delete_reports'] = 'on'
		post['see_users'] = 'on'
		post['edit_users'] = 'on'
		self.assertNotEqual('Great Admin', logged['name'])
		post['name'] = 'Great Admin'
		body = urllib.parse.urlencode(post)
		response = yield client.fetch(self.get_url('/users_management'),
					      headers=headers, method='POST',
					      body=body)
		body = response.body.decode('utf-8')
		self.assertIn('user_was_edited', body)
		self.assertIn('Вы вошли как <b>%s</b>' % post['name'], body)
		logger.info('ok - edit the current user')
