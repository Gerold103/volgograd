#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import tornado.testing
import tornado.gen
from tornado.httpclient import HTTPError

import application
import secret_conf as sc
from constants import *
from query import *
from base_test_suite import BaseTestSuite, test_users, encode_multipart_formdata

##
# Unittest module uses alphabetic order of tests execution. So to
# implement some 'prepare' test we name it like AAA*.
# The test prepare consists from creating test users with
# different rights.
#
# All test cases uses one global Application object.
#
class AAA_TestSuitePrepare(BaseTestSuite):
	@tornado.testing.gen_test
	def test1_create_users(self):
		application.connect_db()

		tx = yield application.begin()
		yield prepare_tests(tx, sc.db_name, sc.test_db_name)
		#
		# Insert users to testing and ensure the
		# correctness of the insert.
		#
		for user in test_users:
			passwd = user['password']
			salt, pass_hash = sc.generate_password_hash(passwd)
			yield insert_user(tx, user['email'], pass_hash, salt,
					  user['name'], user['rights'])

		for i, user in enumerate(test_users):
			db_user = yield get_user_by_email(tx, ['id', 'email',
							       'name', 'rights'],
							  user['email'])
			id = db_user[0]
			email = db_user[1]
			name = db_user[2]
			rights = db_user[3]
			self.assertEqual(id, i + 1)
			self.assertEqual(email, user['email'])
			self.assertEqual(name, user['name'])
			self.assertEqual(rights, user['rights'])

		tx.commit()

	@tornado.gen.coroutine
	def post_file(self, user, file_name):
		with open(file_name, 'rb') as f:
			data = f.read()
			files = [('xls-table', file_name, data), ]
		content_type, body = encode_multipart_formdata({}, files)
		client = self.get_client()
		headers = dict(user['headers'])
		headers['Content-Type'] = content_type
		headers['Content-Length'] = str(len(body))
		try:
			response = yield client.fetch(self.get_url('/upload'),
						      headers=headers,
						      follow_redirects=False,
						      body=body, method='POST')
		except HTTPError as e:
			response = e.response
		self.assertEqual(response.code, 302)
		self.assertIn('show_table',
			      response.headers.get_list('Location')[0])

	@tornado.testing.gen_test(timeout=60)
	def test2_insert_reports(self):
		application.connect_db()

		tx = yield application.begin()

		user = test_users[-1]
		logged = yield self.login_user(user['email'], user['password'])
		self.assertEqual(logged['name'], user['name'])
		for path, dirs_list, files_list in os.walk('../test_reports'):
			for f_name in files_list:
				if not '.xl' in f_name:
					continue
				file_path = os.path.join(path, f_name)
				yield self.post_file(logged, file_path)
