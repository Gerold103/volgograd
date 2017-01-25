#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from io import BytesIO
from datetime import datetime
from zipfile import BadZipFile

import tornado
import tornado.web
import tornado.gen
from tornado.escape import to_unicode


import tormysql

import db
from xml_parser import parse_xls
from base_handler import BaseHandler
from query import *
from constants import *

import secret_conf
import math

import re

class UsersHandler(BaseHandler):
	@tornado.gen.coroutine
	def delete_user(self, user_id):
		tx = yield db.begin()
		try:
			# forbidden to delete itself
			current_user = self.get_current_user()
			if user_id == current_user['user_id'].decode('utf-8'):
				self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='Вы не можете удалить себя')
				return False

			# delete the user by id
			yield delete_user_by_id(tx, user_id)
		except Exception:
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return False

		tx.commit()
		return True

	@tornado.gen.coroutine
	def edit_user(self, user_id):
		# dict with fields that have changed and will be updated
		# key - name of field in db
		# value - new value of field
		updated_cols = {}

		tx = yield db.begin()
		try:
			# get all user's data by id
			user = yield get_user_by_id(tx, 'email, password, '\
			       'salt, rights, name',
			       user_id)
			if not user:
				self.rollback_error(tx, e_hdr=ERR_404,
						    e_msg='Пользователь с '\
						    	  'таким id не '\
						    	  'зарегистрирован')
				return False

			# get changed name of user
			name = self.get_argument('name', None)
			if not name:
				# user's name was changed to an empty string
				self.render_error(e_hdr=ERR_EDIT,
							  	  e_msg='Не указано имя пользователя')
				return False

			# if user's name was changed
			if user[4] != name:
				# then update
				updated_cols['name'] = name

			# get changed email of user
			email = self.get_argument('email', None)
			if not email:
				# user's email was changed to an empty string
				self.render_error(e_hdr=ERR_EDIT,
							  	  e_msg='Не указана почта пользователя')
				return False

			# validate name of user
			if len(name) > MAX_NAME_LENGTH or \
					not re.match(NAME_PATTERN, name):
				self.render_error(e_hdr=ERR_INSERT,
							  e_msg='Имя не удовлетворяет заданным ограничениям')
				return False

			# validate email of user
			if not re.match(EMAIL_PATTERN, email):
				self.render_error(e_hdr=ERR_INSERT,
							  e_msg='Email не удовлетворяет заданным ограничениям')
				return False

			# checking that the user with that email already exists in the db
			duplicate_user = yield get_user_by_email(tx, ['id'], email)
			if duplicate_user and int(user_id) != duplicate_user[0]:
				self.render_error(e_hdr=ERR_INSERT,\
				e_msg='Пользователь с таким email уже существует')
				return False

			# if user's email was changed
			if user[0] != email:
				# then update
				updated_cols['email'] = email

			# get a int rights by list<bool>
			user_perm_int = 0
			for key in permissions:
				bvalue = (self.get_argument(key, None) == 'True')
				if bvalue:
					user_perm_int |= permissions[key][0]

			# if user's rights was changed
			if user[3] != user_perm_int:
				# then update
				updated_cols['rights'] = user_perm_int

			# if user wants to change the password
			psw = self.get_argument('old_password', None)
			if psw:
				# then check whether it is properly introduced 
				# old (current) password
				true_psw = user[1]
				salt = user[2]
				if not secret_conf.check_password(psw, salt, true_psw):
					# no, it is not! password wrong, render error page
					self.rollback_error(tx, e_hdr=ERR_EDIT,
						    e_msg='Неправильный пароль')
					return False
				# yes, it is! password is correct

				# validate that the password and confirm_password match
				new_psw = self.get_argument('password', None)
				confirm_new_psw = self.get_argument('confirm_password', None)

				# if the user input new password or confirm_password
				if new_psw or confirm_new_psw:
					# but only one of them or
					# they are not matching
					if not new_psw or \
					   not confirm_new_psw or \
					   new_psw != confirm_new_psw:
						# then render error page
						self.rollback_error(tx, e_hdr=ERR_EDIT,
									  		e_msg='Введенные \
									  		пароли не совпадают')
						return False
					# if they are matching

					# generate new hash password and salt
					secret_conf.parse_config()
					(salt, psw_hash) = secret_conf.\
						generate_password_hash(new_psw)
					# and update
					updated_cols['password'] = psw_hash
					updated_cols['salt'] = salt


			# if the user changed something
			if len(updated_cols):
				# then update user data
				yield update_user_by_id(tx, updated_cols, user_id)

				# if the current user has changed himself
				current_user = self.get_current_user()
				if (user_id == current_user['user_id'].decode('utf-8')):
					# update cookies for the current user
					self.set_secure_cookie('user_id', str(user_id),
							       expires_days=1)
					self.set_secure_cookie('rights', str(user_perm_int),
							       expires_days=1)
					if user[4]:
						self.set_secure_cookie('user_name', name,
								       expires_days=1)
			# else nothing

		except Exception as e:
			print(e)
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return False

		tx.commit()
		return True

	@tornado.gen.coroutine
	def add_user(self):
		user_data = {}

		# dict<name_of_field_in_the_form, error_message> - the responsing data
		args_name = {'email': 'Не указан email для добавляемого пользователя',\
			'password': 'Не указан пароль для добавляемого пользователя',\
			'confirm_password': 'Не указано подтверждение пароля для добавляемого пользователя',\
			'name': 'Не указано имя для добавляемого пользователя'}
		# for each field
		for key in args_name:
			# get the responsing data by key
			# the second argument - not trimming space in begin and end of string
			user_data[key] = self.get_arguments(key, False)

			# if the required field does not have a value
			if not len(user_data[key]):
				# then rendering an error page
				self.render_error(e_hdr=ERR_INSERT,
						  e_msg=args_name[key])
				return False
			# else take first value (and the only)
			user_data[key] = user_data[key][0]
		
		# validate name of user
		if len(user_data['name']) > MAX_NAME_LENGTH or \
				not re.match(NAME_PATTERN, user_data['name']):
			self.render_error(e_hdr=ERR_INSERT,
						  e_msg='Имя не удовлетворяет заданным ограничениям')
			return False

		# validate email of user
		if not re.match(EMAIL_PATTERN, user_data['email']):
			self.render_error(e_hdr=ERR_INSERT,
						  e_msg='Email не удовлетворяет заданным ограничениям')
			return False

		# generate int rights by list of a True/False
		user_perm_int = 0
		for key in permissions:
			# get right
			bvalue = (self.get_argument(key, None) == 'True')
			# if true
			if bvalue:
				# then add to user_perm_int
				user_perm_int |= permissions[key][0]
			# else skip

		# set to user_data
		user_data['rights'] = user_perm_int

		# password cannot be empty
		if not user_data['password'] or \
		   not user_data['confirm_password']:
			self.render_error(e_hdr=ERR_INSERT,
						  e_msg='Пароль не может быть пустым')
			return False

		# validate that the passwords match
		if user_data['password'] != user_data['confirm_password']:
			self.render_error(e_hdr=ERR_INSERT,
						  e_msg='Пароли не совпадают')
			return False

		# confirm password is no longer needed
		user_data.pop('confirm_password', None)
		# generate hash password and salt by password
		psw = user_data['password']
		secret_conf.parse_config()
		(salt, psw_hash) = secret_conf.generate_password_hash(psw)
		user_data['password'] = psw_hash
		user_data['salt'] = salt

		tx = yield db.begin()
		try:
			# checking that the user with that email already exists in the db
			duplicate_user = yield get_user_by_email(tx, ['id'], user_data['email'])
			if duplicate_user:
				self.render_error(e_hdr=ERR_INSERT,\
				e_msg='Пользователь с таким email уже существует')
				return False

			# insert the user into db
			yield insert_full_user(tx, user_data)
		except Exception as e:
			print(e)
			self.rollback_error(tx, e_hdr=ERR_INSERT,\
				e_msg='Ошибка при добавлении пользователя в базу данных')
		else:
			yield tx.commit()

		return True

	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		# user doesn't have access rights to view a list of users
		if not self.check_rights(CAN_SEE_USERS):
			return

		# enable_edit - true, if user has access to edit users
		# enable_edit - false, if user doesn't have access to edit users
		# enable_edit is used  in the file management.html to display 
		# add/edit/delete buttons
		user = self.get_current_user()
		enable_edit = user['rights'] & CAN_EDIT_USERS

		tx = yield db.begin()
		users = []
		try:
			# get a list of all users from db
			users = yield get_all_users(tx, 'id, name, email, rights')
		except Exception:
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return
		else:
			yield tx.commit()

		for i in range(len(users)):
			# users[i] = (name, email, rights)
			# where rights is int
			users[i].append([])
			# users[i] = (name, email, rights, perms)
			# where perms is list of bool

			# checking in the loop that a user has right PERMISSIONS[KEY]
			pers_value = {}
			for key in permissions:
				perm = int(users[i][3]) & \
									  permissions[key][0]

				# if user has PERMISSIONS[KEY]
				if perm:
					# then add to list of the rights
					users[i][4].append(permissions[key][1])

		# the number of pages
		num_of_pages = math.ceil(len(users)/NUMBER_USERS_IN_PAGE)
		# the currently displayed page
		page = int(self.get_argument('page', 1))
		self.render('users_management/management.html',
					enable_edit = enable_edit,
					users = users,
					page = page,
					num_in_page = NUMBER_USERS_IN_PAGE,
					num_of_pages = num_of_pages,
					pers = permissions,
					pers_value = pers_value)

	@tornado.gen.coroutine
	@tornado.web.authenticated
	def post(self):
		action = self.get_argument('action', None)
		if not action:
			return

		user_id = self.get_argument('id', None)
		if not user_id and action in ['del', 'edit']:
			return

		succes = False
		if action == 'del':
			succes = yield self.delete_user(user_id)
		elif action == 'edit':
			succes = yield self.edit_user(user_id)
		elif action == 'add':
			succes = yield self.add_user()

		if succes:
			self.redirect("/users_management")