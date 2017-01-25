#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tornado.testing

import application
import secret_conf as sc
from constants import *
from query import *
from base_test_suite import BaseTestSuite, test_users

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
	def test_create_users(self):
		tx = yield application.begin()
		yield prepare_tests(tx, sc.db_name, 'test_volgograd')
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
