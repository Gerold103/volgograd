#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

import tornado
import tornado.gen

import secret_conf as sc
import application
from base_handler import BaseHandler, need_rights
from constants import *
from query import *

ERR_PAGE_NUMBER = 'Ошибка в указании номера страницы.'
ERR_USER_ACTION_ID = 'Ошибка в указании идентификатора пользователя. '\
		     'Идентификатор должен быть целым неотрицательным числом'
ERR_ACTION = 'Ошибка при выборе действия'

USERS_ON_PAGE = 10
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

##
# Handler to show the site users, its rights, names, emails.
# Also you can create new users, delete and edit existing.
#
class UsersManagementHandler(BaseHandler):
	##
	# Render the page with the list of users, fetched from the
	# database, and commit the transaction.
	# @param tx     Current transaction.
	# @param kwargs What actions was made on the previous
	#               page. For example, if an user was deleted,
	#               then on next page we need to show message
	#               about deletion status and remained users.
	#
	@tornado.gen.coroutine
	@need_rights(CAN_EDIT_USERS | CAN_SEE_USERS)
	def render_page_and_commit(self, tx, **kwargs):
		page = self.get_argument('page', 1)
		try:
			page = int(page)
			if page <= 0:
				raise ValueError('Page must be positive '\
						 'number.')
		except:
			self.rollback_error(tx, ERR_PARAMETERS, ERR_PAGE_NUMBER)
			return
		try:
			#
			# Fetch one more user than need, to check
			# if we are showing the last page.
			#
			limit = USERS_ON_PAGE + 1
			offset = (page - 1) * USERS_ON_PAGE
			columns = ['id', 'email', 'name', 'rights']
			users = yield get_users_range(tx, limit, offset,
						      columns)
			count = len(users)
			if count == 0 and 'user_was_deleted' not in kwargs:
				self.rollback_error(tx, ERR_PARAMETERS,
						    ERR_PAGE_NUMBER)
				return
			if count == limit:
				users = users[:-1]
			self.render('users_management.html', page=page,
				    **users_management_params, users=users,
				    is_last_page=(count < limit),
				    get_val=get_html_val, **kwargs,
				    CONFIRM_DELETE=CONFIRM_DELETE)
			yield tx.commit()
		except:
			logger.exception('Error during getting users')
			self.rollback_error(tx, e_hdr=ERR_500)
			return

	@tornado.gen.coroutine
	@need_rights(CAN_EDIT_USERS | CAN_SEE_USERS)
	def get(self):
		action = self.get_argument('action', None)
		id = self.get_argument('id', None)
		if action:
			if not self.check_rights(CAN_EDIT_USERS):
				return
			#
			# It is not allowed to create or edit an
			# user via GET request.
			#
			if action != 'delete':
				self.render_error(ERR_PARAMETERS, ERR_ACTION)
				return
			if id is None:
				self.render_error(ERR_PARAMETERS,
						  ERR_USER_ACTION_ID)
				return
			try:
				id = int(id)
				if id < 0:
					raise ValueError(ERR_USER_ACTION_ID)
			except:
				self.render_error(ERR_PARAMETERS,
						  ERR_USER_ACTION_ID)
				return
		try:
			tx = yield application.begin()
		except:
			logger.exception('Error during getting users')
			self.rollback_error(tx, e_hdr=ERR_500)
			return
		kwargs = { 'user_was_created': False, 'user_was_edited': False,
			   'user_was_deleted': False }
		if not action:
			yield self.render_page_and_commit(tx, **kwargs)
			return
		assert(action == 'delete')
		try:
			yield delete_user_by_id(tx, id)
			#
			# If the user deleted himself, then logout
			# him by clearing all his cookies.
			#
			if id == self.current_user['user_id']:
				self.clear_all_cookies()
			kwargs['user_was_deleted'] = True
		except:
			logger.exception('Error during deletion of the user '\
					 'with id: %s' % id)
			self.rollback_error(tx, e_hdr=ERR_500)
			return
		yield self.render_page_and_commit(tx, **kwargs)

	@tornado.gen.coroutine
	@need_rights(CAN_EDIT_USERS | CAN_SEE_USERS)
	def post(self):
		action = self.get_argument('action', None)
		id = self.get_argument('id', None)
		#
		# It is not allowed to delete an user via POST
		# request.
		#
		if action not in ['create', 'edit']:
			self.render_error(ERR_PARAMETERS, ERR_ACTION)
			return
		if action == 'edit':
			if not self.check_rights(CAN_EDIT_USERS):
				return
			try:
				id = int(id)
				if id < 0:
					raise ValueError(ERR_USER_ACTION_ID)
			except:
				self.render_error(ERR_PARAMETERS, ERR_USER_ACTION_ID)
				return
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
		password = self.get_argument('password', '')
		password_repeat = self.get_argument('password-repeat', '')
		pass_len = len(password)
		need_password = action != 'edit' or pass_len > 0 or \
				len(password_repeat) > 0
		if pass_len == 0 and need_password:
			self.render_error(ERR_PARAMETERS, ERR_PASSWORD_ABSENSE)
			return
		if (pass_len < MIN_PASSWORD_LENGTH or \
		    pass_len > MAX_PASSWORD_LENGTH) and need_password:
			self.render_error(ERR_PARAMETERS, ERR_PASSWORD_LENGTH)
			return
		if password != password_repeat:
			self.render_error(ERR_PARAMETERS, ERR_PASSWORD_MATCH)
			return
		if need_password:
			salt, password_hash =\
				sc.generate_password_hash(password)
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
		kwargs = { 'user_was_created': False, 'user_was_edited': False,
			   'user_was_deleted': False }
		try:
			tx = yield application.begin()
			if action == 'create':
				yield insert_user(tx, email, password_hash,
						  salt, name, rights_mask)
				kwargs['user_was_created'] = True
			else:
				assert(action == 'edit')
				if need_password:
					yield update_user(tx, id, email,
							  password_hash, salt,
							  name, rights_mask)
				else:
					yield update_user(tx, id, email, None,
							  None, name,
							  rights_mask)
				kwargs['user_was_edited'] = True
				#
				# If the user edited himself, then
				# update his cookies.
				#
				if id == self.current_user['user_id']:
					self.update_cookies(rights_mask, name)
			yield self.render_page_and_commit(tx, **kwargs)
		except Exception as e:
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				msg = 'Пользователь с таким адресом почты '\
				      'уже зарегистрирован'
				self.rollback_error(tx, e_hdr=ERR_INSERT,
						    e_msg=msg)
			else:
				logger.exception('Error with creating user')
				self.rollback_error(tx, e_hdr=ERR_500)
