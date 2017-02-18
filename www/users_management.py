#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

import tornado
import tornado.gen

import secret_conf as sc
import application
from base_handler import BaseHandler, need_rights
from constants import *
from query import insert_user

MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 200
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 30

ERR_PASSWORD_LENGTH = 'Длина пароля должна быть не меньше {} '\
		      'символов и не больше {}'.format(MIN_PASSWORD_LENGTH,
		      				       MAX_PASSWORD_LENGTH)
ERR_PASSWORD_MATCH = 'Пароли не совпадают'
ERR_PASSWORD_ABSENSE = 'Не указан пароль'

ERR_RIGHTS_COMBINATION = 'Несовместимый набор прав пользователя'

ERR_NAME_LENGTH = 'Длина имени не должна превышать {} '\
		  'символов'.format(MAX_NAME_LENGTH)
ERR_NAME_FORMAT = 'Имя некорректно'
NAME_FORMAT = '^[a-zA-Z_а-яА-Я- .0-9]*$'

ERR_EMAIL_ABSENSE = 'Не указан адрес почты'
ERR_EMAIL_LENGTH = 'Длина адреса почты не должна превышать {} '\
		   'символов'.format(MAX_EMAIL_LENGTH)
ERR_EMAIL_FORMAT = 'Адрес почты некорректен'
EMAIL_FORMAT = '^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
email_validator = re.compile(EMAIL_FORMAT)
name_validator = re.compile(NAME_FORMAT)

users_management_params = {
	'max_name_len'       : MAX_NAME_LENGTH,
	'max_email_len'      : MAX_EMAIL_LENGTH,
	'min_password_len'   : MIN_PASSWORD_LENGTH,
	'max_password_len'   : MAX_PASSWORD_LENGTH,
	'email_len_err'      : ERR_EMAIL_LENGTH,
	'email_format_err'   : ERR_EMAIL_FORMAT,
	'email_format'       : EMAIL_FORMAT,
	'name_len_err'       : ERR_NAME_LENGTH,
	'name_format_err'    : ERR_NAME_FORMAT,
	'name_format'        : NAME_FORMAT,
	'password_len_err'   : ERR_PASSWORD_LENGTH,
	'password_match_err' : ERR_PASSWORD_MATCH
}

class UsersManagementHandler(BaseHandler):
	@tornado.gen.coroutine
	@need_rights(CAN_SEE_USERS)
	def get(self):
		self.render('users_management.html', **users_management_params)

	@tornado.gen.coroutine
	@need_rights(CAN_EDIT_USERS | CAN_SEE_USERS)
	def post(self):
		#
		# Check email correctness.
		#
		email = self.get_argument('email', None)
		if email is None:
			self.render_error(ERR_404, ERR_EMAIL_ABSENSE)
			return
		if len(email) > MAX_EMAIL_LENGTH:
			self.render_error(ERR_PARAMETERS, ERR_EMAIL_LENGTH)
			return
		if not email_validator.fullmatch(email):
			self.render_error(ERR_PARAMETERS, ERR_EMAIL_FORMAT)
			return
		#
		# Check name correctness.
		#
		name = self.get_argument('name', None)
		# If the name has zero length then store it as
		# NULL in the database and None in python.
		if not name:
			name = None
		if name and len(name) > MAX_NAME_LENGTH:
			self.render_error(ERR_PARAMETERS, ERR_NAME_LENGTH)
			return
		if name and not name_validator.fullmatch(name):
			self.render_error(ERR_PARAMETERS, ERR_NAME_FORMAT)
			return
		#
		# Check password correctness.
		#
		password = self.get_argument('password', None)
		if password is None:
			self.render_error(ERR_PARAMETERS, ERR_PASSWORD_ABSENSE)
			return
		if len(password) < MIN_PASSWORD_LENGTH or \
		   len(password) > MAX_PASSWORD_LENGTH:
			self.render_error(ERR_PARAMETERS, ERR_PASSWORD_LENGTH)
			return
		password_repeat = self.get_argument('password-repeat', '')
		if password != password_repeat:
			self.render_error(ERR_PARAMETERS, ERR_PASSWORD_MATCH)
			return
		salt, password_hash = sc.generate_password_hash(password)
		#
		# Check mask correctness.
		#
		rights_mask = 0
		if self.get_argument('see_reports', None):
			rights_mask |= CAN_SEE_REPORTS
		if self.get_argument('upload_reports', None):
			rights_mask |= CAN_UPLOAD_REPORTS
		if self.get_argument('delete_reports', None):
			rights_mask |= CAN_DELETE_REPORTS
		if self.get_argument('see_users', None):
			rights_mask |= CAN_SEE_USERS
		if self.get_argument('edit_users', None):
			rights_mask |= CAN_EDIT_USERS
		if rights_mask & CAN_EDIT_USERS and \
		   not (rights_mask & CAN_SEE_USERS):
			msg = ERR_RIGHTS_COMBINATION + ': для редактирования '\
			      'пользователей нужны права на их просмотр'
			self.render_error(ERR_PARAMETERS, msg)
			return
		if rights_mask & CAN_DELETE_REPORTS and \
		   not (rights_mask & CAN_SEE_REPORTS):
			msg = ERR_RIGHTS_COMBINATION + ': для удаления отчетов'\
			      ' нужны права на их просмотр'
			self.render_error(ERR_PARAMETERS, msg)
			return
		tx = None
		try:
			tx = yield application.begin()
			yield insert_user(tx, email, password_hash, salt, name,
					  rights_mask)
			self.render('users_management.html',
				    user_was_created=True,
				    **users_management_params)
			yield tx.commit()
		except Exception as e:
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				msg = 'Пользователь с таким адресом почты '\
				      'уже зарегистрирован'
				self.rollback_error(tx, e_hdr=ERR_INSERT,
						    e_msg=msg)
			else:
				logger.exception('Error with creating user')
				self.rollback_error(tx, e_hdr=ERR_500)
