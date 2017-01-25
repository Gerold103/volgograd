#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import urllib
from copy import deepcopy

import tornado.testing
import tornado.gen
from tornado.httpclient import HTTPError

import application
import secret_conf as sc
from constants import *
from query import *
from base_test_suite import BaseTestSuite, test_error_users, \
			    test_duplicate_users, test_edited_users, \
			    test_new_edited_users, test_users
from users_management import validate_user_name, validate_user_email, \
			     MISSING_NAME, MISSING_EMAIL, MISSING_PASSWORD, \
			     MISSING_C_PASSWORD, INVALID_PASSWORD, \
			     MISMATCH_PASSWORDS, INVALID_NAME, INVALID_EMAIL, \
			     DUPLICATE_USER


##
# Tests validate user's name, email, password and other errors.
#
class TestSuiteAddEditDeleteUsers(BaseTestSuite):
	##
	# Validate user's name, email and password 
	# on erroneous sample
	#
	@tornado.testing.gen_test
	def test1_error_users(self):
		for user in test_error_users:
			val_user = validate_user_name(user['name']) and \
				   validate_user_email(user['email']) and \
				   bool(user['password'])
			self.assertFalse(val_user)
		logger.info('ok - validation users')

	##
	# An attempt to insert a users with the duplicate email
	#
	@tornado.testing.gen_test
	def test2_duplicate_user(self):
		application.connect_db()

		tx = yield application.begin()
		#yield prepare_tests(tx, sc.db_name, sc.test_db_name)

		for user in test_duplicate_users:
			psw = user['password']
			salt, pass_hash = sc.generate_password_hash(psw)
			try:
				yield insert_user(tx, user['email'], pass_hash,
						  salt, user['name'],
						  user['rights'])
			except Exception as e:
				if len(e.args) > 0 and \
				   e.args[0] == DUPLICATE_ERROR:
					self.assertTrue(True)
				else:
					self.assertTrue(False)
		tx.commit()
		logger.info('ok - duplication users')

	##
	# Test users editing
	#
	@tornado.testing.gen_test
	def test3_user_editing(self):
		application.connect_db()
		tx = yield application.begin()
		
		yield self.insert_users(tx, test_edited_users)

		copy_users = deepcopy(test_new_edited_users)
		for i, user in enumerate(test_edited_users):
			user_id = yield get_user_by_email(tx, ['id'], 
							  user['email'])

			psw = copy_users[i]['password']
			salt, psw_hash = sc.generate_password_hash(psw)
			copy_users[i]['password'] = psw_hash
			copy_users[i]['salt'] = salt

			yield update_user_by_id(tx, copy_users[i], user_id)

		cols = ['name', 'email', 'rights', 'password', 'salt']
		for i, user in enumerate(copy_users):
			new_user = yield get_user_by_email(tx, cols, \
							   user['email'])
			name = new_user[0]
			email = new_user[1]
			rights = new_user[2]
			password = new_user[3]
			salt = new_user[4]
			self.assertEqual(name, user['name'])
			self.assertEqual(email, user['email'])
			self.assertEqual(rights, user['rights'])
			self.assertEqual(password, user['password'])
			self.assertEqual(salt, user['salt'])

		tx.commit()
		logger.info('ok - user editing')

	##
	# Test users deleting
	#
	@tornado.testing.gen_test
	def test4_user_deleting(self):
		application.connect_db()
		tx = yield application.begin()
		
		user_email = test_new_edited_users[1]['email']
		user_id = yield get_user_by_email(tx, ['id'], user_email)
		yield delete_user_by_id(tx, user_id)
		
		user_id = yield get_user_by_email(tx, ['id'], user_email)
		self.assertFalse(user_id)

		tx.commit()
		logger.info('ok - user deleting')
	
	##
	# Send post request to /users_management with a bad 
	# data (name, email and etc) when do 'action' with users
	#
	@tornado.gen.coroutine
	def post_input_form(self, logged, new_user, action, fields):
		client = self.get_client()
		post_data = {}
		post_data['action'] = action
		for field in fields:
			post_data[field] = new_user[field]
		body = urllib.parse.urlencode(post_data)

		headers = logged['headers']
		headers['Content-Type'] = 'application/x-www-form-urlencoded;\
					   charset=utf-8'
		headers['Content-Length'] = str(len(body))
		response = None
		try:
			url = self.get_url('/users_management')
			response = yield client.fetch(url, method='POST',
						      headers=headers,
						      body=body,
						      follow_redirects=False)
		except HTTPError as e:
			response = e.response

		return response.body.decode('utf-8')

	##
	# Test error messages when add a user
	#
	@tornado.testing.gen_test
	def test5_error_messages_add(self):
		admin = test_users[-1]
		logged = yield self.login_user(admin['email'], \
					       admin['password'])

		new_user = test_edited_users[-1]

		#
		# Doesn't specify email
		#
		cols = []
		body = yield self.post_input_form(logged, new_user, \
					    	   'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(MISSING_EMAIL, body)

		#
		# Doesn't specify password
		#
		cols = ['email']
		body = yield self.post_input_form(logged, new_user, \
					    	   'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(MISSING_PASSWORD, body)

		#
		# Doesn't specify confirm password
		#
		new_user['new_password'] = new_user['password']
		cols = ['email', 'new_password']
		body = yield self.post_input_form(logged, new_user, \
					    	   'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(MISSING_C_PASSWORD, body)
		new_user.pop('new_password')

		#
		# Doesn't specify name
		#
		new_user['confirm_password'] = new_user['password']
		new_user['new_password'] = new_user['password']
		cols = ['email', 'new_password', 'confirm_password']
		body = yield self.post_input_form(logged, new_user, \
					    	   'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(MISSING_NAME, body)

		#
		# Invalid email
		#
		error_user = dict(new_user)
		error_user['email'] = 'error_dog_sign_email'
		cols = ['name', 'email', 'new_password', 'confirm_password']
		body = yield self.post_input_form(logged, error_user, \
					    	  'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(INVALID_EMAIL, body)

		#
		# Invalid name
		#
		error_user['name'] = '#error#name '
		cols = ['name', 'email', 'new_password', 'confirm_password']
		body = yield self.post_input_form(logged, error_user, \
					    	  'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(INVALID_NAME, body)
		new_user.pop('confirm_password')
		new_user.pop('new_password')

		#
		# Empty confirm password
		#
		copy_user = dict(new_user)
		copy_user['confirm_password'] = ''
		copy_user['new_password'] = 'not empty'
		cols = ['name', 'email', 'confirm_password', 'new_password']
		body = yield self.post_input_form(logged, copy_user, \
					    	   'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(MISSING_C_PASSWORD, body)

		#
		# Empty password
		#
		copy_user['new_password'] = ''
		cols = ['name', 'email', 'new_password', 'confirm_password']
		body = yield self.post_input_form(logged, copy_user, \
					    	   'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(MISSING_PASSWORD, body)

		#
		# Mismatch passwords
		#
		copy_user['new_password'] = 'password1'
		copy_user['confirm_password'] = 'password2'
		cols = ['name', 'email', 'new_password', 'confirm_password']
		body = yield self.post_input_form(logged, copy_user, \
					    	   'add', cols)
		self.assertIn(ERR_INSERT, body)
		self.assertIn(MISMATCH_PASSWORDS, body)

		logger.info('ok - error messages when add a user')

	##
	# Test error messages when edit a user
	#
	@tornado.testing.gen_test
	def test5_error_messages_edit(self):
		application.connect_db()
		tx = yield application.begin()
		
		admin = test_users[0]
		logged = yield self.login_user(admin['email'], \
					       admin['password'])

		new_user = dict(test_new_edited_users[0])
		user_id = yield get_user_by_email(tx, ['id'], \
						  new_user['email'])

		#
		# User doesn't exist
		#
		self.assertNotEqual(user_id, None)
		new_user['id'] = user_id[0]

		#
		# Doesn't specify name
		#
		cols = ['id']
		body = yield self.post_input_form(logged, new_user, \
					    	  'edit', cols)
		self.assertIn(ERR_EDIT, body)
		self.assertIn(MISSING_NAME, body)

		#
		# Doesn't specify email
		#
		cols = ['id', 'name']
		body = yield self.post_input_form(logged, new_user, \
					    	  'edit', cols)
		self.assertIn(ERR_EDIT, body)
		self.assertIn(MISSING_EMAIL, body)

		#
		# Invalid email
		#
		error_user = dict(new_user)
		error_user['email'] = 'error_dog_sign_email'
		cols = ['id', 'name', 'email']
		body = yield self.post_input_form(logged, error_user, \
					    	  'edit', cols)
		self.assertIn(ERR_EDIT, body)
		self.assertIn(INVALID_EMAIL, body)

		#
		# Invalid name
		#
		error_user['name'] = '#error#name '
		cols = ['id', 'name', 'email']
		body = yield self.post_input_form(logged, error_user, \
					    	  'edit', cols)
		self.assertIn(ERR_EDIT, body)
		self.assertIn(INVALID_NAME, body)

		#
		# Wrong password
		#
		copy_user = dict(new_user)
		copy_user['password'] = '{0}{0}'.format(copy_user['password'])
		cols = ['id', 'name', 'email', 'rights', 'password']
		body = yield self.post_input_form(logged, copy_user, \
					    	  'edit', cols)
		self.assertIn(ERR_EDIT, body)
		self.assertIn(INVALID_PASSWORD, body)

		#
		# Specify password, new_password, confirm_password
		# but new_password != confirm_password
		#
		new_user['new_password'] = \
				'{0}{0}'.format(new_user['password'])
		new_user['confirm_password'] = \
				'{0}{0}{0}'.format(new_user['password'])
		cols = ['id', 'name', 'email', 'rights', 'password', \
			'new_password', 'confirm_password']
		body = yield self.post_input_form(logged, new_user, \
					    	  'edit', cols)
		self.assertIn(ERR_EDIT, body)
		self.assertIn(MISMATCH_PASSWORDS, body)

		#
		# Doesn't specify password but specify
		# new password or confirm_password
		#
		new_user['confirm_password'] = new_user['password']
		new_user['new_password'] = new_user['password']
		cols = ['id', 'name', 'email', 'rights', \
			'new_password', 'confirm_password']
		body = yield self.post_input_form(logged, new_user, \
					    	  'edit', cols)
		self.assertIn(ERR_EDIT, body)
		self.assertIn(MISSING_PASSWORD, body)

		#
		# Doesn't specify password, 
		# new password, confirm_password
		#
		cols = ['id', 'name', 'email', 'rights']
		body = yield self.post_input_form(logged, new_user, \
					    	  'edit', cols)
		self.assertNotIn(ERR_EDIT, body)

		tx.commit()
		logger.info('ok - error messages when edit a user')