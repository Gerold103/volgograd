#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import re

import tornado
import tornado.web
import tornado.gen
from tornado.escape import to_unicode
import tormysql

import secret_conf
import application
from base_handler import BaseHandler, need_rights
from query import *
from constants import *

INVALID_NAME = 'Имя не удовлетворяет заданным ограничениям'
INVALID_EMAIL = 'Email не удовлетворяет заданным ограничениям'
SERVER_ERROR = 'На сервере произошла ошибка, обратитесь к администратору'
YOURSELF_REMOVING = 'Вы не можете удалить себя'
USER_NOT_EXISTS = 'Пользователь с таким id не зарегистрирован'
MISSING_NAME = 'Не указано имя пользователя'
MISSING_EMAIL = 'Не указана почта пользователя'
DUPLICATE_USER = 'Пользователь с таким email уже существует'
INVALID_PASSWORD = 'Неправильный пароль'
MISMATCH_PASSWORDS = 'Введенные пароли не совпадают'
MISSING_PASSWORD = 'Не указан пароль'
MISSING_C_PASSWORD = 'Не указано подтверждение пароля'
INSERT_ERROR = 'Ошибка при добавлении пользователя в базу данных'


# constraints
NAME_PATTERN = '^[A-Za-zА-Яа-яЁё0-9]+(?:[ ._-][A-Za-zА-Яа-яЁё0-9]+)*$'
EMAIL_PATTERN = '^[a-zA-Z0-9.!#$%&’*+/=?^_`{|}~-]+@[a-zA-Z0-9-]'\
				'+(?:\.[a-zA-Z0-9-]+)*$'
MAX_NAME_LENGTH = 65535
NUMBER_USERS_IN_PAGE = 8

# check the name on the length and pattern
def validate_user_name(user_name):
	if len(user_name) > MAX_NAME_LENGTH or \
	   not re.match(NAME_PATTERN, user_name):
		return False
	return True

# check the email on the pattern
def validate_user_email(user_email):
	if not re.match(EMAIL_PATTERN, user_email):
		return False
	return True


##
# Get all users from db and show its in a table.
# And ability to delete, edit and add users.
#
class UsersHandler(BaseHandler):
	# generate int rights by list of a True/False
	def rights_bool_to_int(self):
		user_perm_int = 0
		for key in permissions:
			# get right
			bvalue = (self.get_argument(key, None) == 'True')
			# if true
			if bvalue:
				# then add to user_perm_int
				user_perm_int |= permissions[key][0]
		return user_perm_int


	##
	# post method to delete a user
	#
	@tornado.gen.coroutine
	def delete_user(self, user_id):
		tx = None
		try:
			tx = yield application.begin()

			# forbidden to delete itself
			current_user = self.get_current_user()
			if user_id == current_user['user_id'].decode('utf-8'):
				self.rollback_error(tx, e_hdr=ERR_500, 
						    e_msg=YOURSELF_REMOVING)
				return False

			# delete the user by id
			yield delete_user_by_id(tx, user_id)
			yield tx.commit()
		except Exception as e:
			logger.exception(e)
			self.rollback_error(tx, e_hdr=ERR_500, 
					    e_msg=SERVER_ERROR)
			return False

		return True

	# post method to edit a user
	@tornado.gen.coroutine
	def edit_user(self, user_id):
		# dict with fields that have changed and will be updated
		# key - name of field in db
		# value - new value of field
		updated_cols = {}
		try:
			tx = yield application.begin()

			# get all user's data by id
			cols = ['email', 'password', 'salt', 'rights', 'name']
			user = yield get_user_by_id(tx, cols, user_id)
			if not user:
				self.rollback_error(tx, e_hdr=ERR_404, 
						    e_msg=USER_NOT_EXISTS)
				return False

			name = self.get_argument('name', None)
			if not name:
				self.render_error(e_hdr=ERR_EDIT, 
						  e_msg=MISSING_NAME)
				return False

			email = self.get_argument('email', None)
			if not email:
				self.render_error(e_hdr=ERR_EDIT, 
						  e_msg=MISSING_EMAIL)
				return False

			if not validate_user_name(name):
				self.render_error(e_hdr=ERR_EDIT, 
						  e_msg=INVALID_NAME)
				return False

			if not validate_user_email(email):
				self.render_error(e_hdr=ERR_EDIT, 
						  e_msg=INVALID_EMAIL)
				return False
			# if user's name was changed
			if user[4] != name:
				# then update
				updated_cols['name'] = name

			# if user's name was changed
			if user[4] != name:
				# then update
				updated_cols['name'] = name

			# if user's email was changed
			if user[0] != email:
				# then update
				updated_cols['email'] = email

			# get a int rights by list<bool>
			user_perm_int = self.rights_bool_to_int()

			# if user's rights was changed
			if user[3] != user_perm_int:
				# then update
				updated_cols['rights'] = user_perm_int

			# if user wants to change the password
			psw = self.get_argument('password', None)
			new_psw = self.get_argument('new_password', None)
			confirm_psw = \
				self.get_argument('confirm_password', None)
			if psw:
				# then check whether it is properly introduced 
				# old (current) password
				true_psw = user[1]
				salt = user[2]
				if not secret_conf.check_password(psw, salt, true_psw):
					# password wrong, render error page
					self.rollback_error(tx, e_hdr=ERR_EDIT, 
							    e_msg=INVALID_PASSWORD)
					return False
				# password is correct

				# validate that the passwords match

				# if the user inputs passwords
				if new_psw or confirm_psw:
					# but only one of them or
					# they are not matching
					if not new_psw or not confirm_psw or \
					   new_psw != confirm_psw:
						# then render error page
						self.rollback_error(tx, e_hdr=ERR_EDIT, 
								    e_msg=MISMATCH_PASSWORDS)
						return False
					# they are matching

					# generate new hash password and salt
					salt, psw_hash = secret_conf.\
						generate_password_hash(new_psw)
					# and update
					updated_cols['password'] = psw_hash
					updated_cols['salt'] = salt
			else:
				if new_psw or confirm_psw:
					self.rollback_error(tx, e_hdr=ERR_EDIT, 
							    e_msg=MISSING_PASSWORD)
					return False

			# if the user changed something
			if len(updated_cols):
				# then update user data
				yield update_user_by_id(tx, updated_cols, user_id)

				# if the current user has changed himself
				current_user = self.get_current_user()
				if (user_id == current_user['user_id'].decode('utf-8')):
					# update cookies for the current user
					self.set_secure_cookie('user_id', 
							       str(user_id),
							       expires_days=1)
					self.set_secure_cookie('rights', 
							       str(user_perm_int),
							       expires_days=1)
					if user[4]:
						self.set_secure_cookie('user_name', 
								       name,
								       expires_days=1)

			yield tx.commit()
		except Exception as e:
			logger.exception(e)
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				print('!!!!!!!!!!!!!!!!!!!!!!!!!')
				self.rollback_error(tx, e_hdr=ERR_EDIT,
						    e_msg=DUPLICATE_USER)
			else:
				self.rollback_error(tx, e_hdr=ERR_500, 
						    e_msg=SERVER_ERROR)
			return False
		return True

	# post method to add a user
	@tornado.gen.coroutine
	def add_user(self):
		user_data = {}

		# dict<name_of_field_in_the_form, error_message>
		args_name = {
			'email': MISSING_EMAIL,
			'new_password': MISSING_PASSWORD,
			'confirm_password': MISSING_C_PASSWORD,
			'name': MISSING_NAME
		}
		# for each field
		for key in args_name:
			# get the responsing data by key
			# the second argument - not trimming spaces
			user_data[key] = self.get_arguments(key, False)

			# if the required field does not have a value
			if not len(user_data[key]):
				# then rendering an error page
				self.render_error(e_hdr=ERR_INSERT,
						  e_msg=args_name[key])
				return False
			# else take first value (and the only)
			user_data[key] = user_data[key][0]

		if not validate_user_name(user_data['name']):
			self.render_error(e_hdr=ERR_INSERT, e_msg=INVALID_NAME)
			return False

		if not validate_user_email(user_data['email']):
			self.render_error(e_hdr=ERR_INSERT, e_msg=INVALID_EMAIL)
			return False

		# set int right to user_data
		user_data['rights'] = self.rights_bool_to_int()

		# passwords cannot be empty
		if not user_data['new_password']:
			self.render_error(e_hdr=ERR_INSERT, 
					  e_msg=MISSING_PASSWORD)
			return False

		if not user_data['confirm_password']:
			self.render_error(e_hdr=ERR_INSERT, 
					  e_msg=MISSING_C_PASSWORD)
			return False

		# validate that the passwords match
		if user_data['new_password'] != user_data['confirm_password']:
			self.render_error(e_hdr=ERR_INSERT, 
					  e_msg=MISMATCH_PASSWORDS)
			return False

		# confirm password is no longer needed
		user_data.pop('confirm_password', None)
		# generate hash password and salt by password
		psw = user_data['new_password']
		salt, psw_hash = secret_conf.generate_password_hash(psw)
		user_data['new_password'] = psw_hash
		user_data['salt'] = salt

		tx = None
		try:
			tx = yield application.begin()

			# insert the user into db
			cols = ['email', 'password', 'salt', 'name', 'rights']
			yield insert_full_user(tx, cols, user_data)
			yield tx.commit()
		except Exception as e:
			logger.exception(e)
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				self.rollback_error(tx, e_hdr=ERR_INSERT,
						    e_msg=DUPLICATE_USER)
			else:
				self.rollback_error(tx, e_hdr=ERR_INSERT, 
						    e_msg=INSERT_ERROR)
			return False

		return True

	@tornado.gen.coroutine
	@need_rights(CAN_SEE_USERS)
	def get(self):
		# the currently displayed page
		page = int(self.get_argument('page', 1))

		users = []
		tx = None
		try:
			tx = yield application.begin()

			count_users = yield get_count_users(tx)

			# the number of pages
			num_of_pages = math.ceil(count_users/NUMBER_USERS_IN_PAGE)

			limit = min(NUMBER_USERS_IN_PAGE, count_users)
			offset = NUMBER_USERS_IN_PAGE * (page-1)
			# get a list of all users from db
			cols = ['id', 'name', 'email', 'rights']
			users = yield get_all_users(tx, cols, limit, offset)
			yield tx.commit()
		except Exception as e:
			logger.exception(e)
			self.rollback_error(tx, e_hdr=ERR_500, e_msg=SERVER_ERROR)
			return

		# get last action
		action = self.get_argument('action', None)

		self.render('users_management/management.html',
					users = users,
					page = page,
					num_of_pages = num_of_pages,
					pers = permissions,
					suc_msg = action,
					num_in_page = NUMBER_USERS_IN_PAGE,
					max_name_length = MAX_NAME_LENGTH)

	@tornado.web.authenticated
	@tornado.gen.coroutine
	def post(self):
		action = self.get_argument('action', None)
		if not action:
			return

		user_id = self.get_argument('id', None)
		if not user_id and action in ['del', 'edit']:
			return

		page = int(self.get_argument('page', 1))

		success = False
		if action == 'del':
			success = yield self.delete_user(user_id)
		elif action == 'edit':
			success = yield self.edit_user(user_id)
		elif action == 'add':
			success = yield self.add_user()

		if success:
			self.redirect("/users_management?action={}&page={}"
				.format(action, page))
