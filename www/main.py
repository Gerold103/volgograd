#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
import logging
import unittest

import tornado
import tornado.ioloop
import tornado.web
import tornado.gen

import secret_conf

import application
from base_handler         import BaseHandler, need_rights
import db
from base_handler         import BaseHandler
from upload_handler       import UploadHandler
from show_handler         import ShowHandler
from water_consum_handler import WaterConsumHandler
from year_plot_handler    import YearPlotHandler
from temperature_handler  import TemperatureHandler
from users_management 	  import UsersHandler
from query import *
from constants import *

from tests_prepare_suite     import AAA_TestSuitePrepare
from test_login_logout_suite import TestSuiteLoginLogout

##
# Main page render.
#
class MainHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("index.html")

##
# Login a not authorized user.
#
class LoginHandler(BaseHandler):
	##
	# Show login page, if the current user is not already authorized.
	#
	def get(self):
		if self.get_current_user():
			self.render_error(e_hdr=ERR_LOGIN,
					  e_msg='Вы уже авторизованы')
			return
		self.render('login.html')

	@tornado.gen.coroutine
	def post(self):
		if self.get_current_user():
			self.render_error(e_hdr=ERR_LOGIN,
					  e_msg='Вы уже авторизованы')
			return
		email = self.get_argument('email', None)
		if not email:
			self.render_error(e_hdr=ERR_LOGIN,
					  e_msg='Не указан email')
			return
		password = self.get_argument('password', None)
		if not password:
			self.render_error(e_hdr=ERR_LOGIN,
					  e_msg='Не указан пароль')
			return
		tx = None
		try:
			tx = yield application.begin()
			#
			# Try to find the user by specified email.
			#
			columns = [ 'id', 'password', 'salt', 'rights', 'name',
				    'email' ]
			user = yield get_user_by_email(tx, columns, email)
			if not user:
				self.rollback_error(tx, e_hdr=ERR_404,
						    e_msg='Пользователь с '\
						    	  'таким email не '\
						    	  'зарегистрирован')
				return
			true_password = user[1]
			salt = user[2]
			#
			# Check that the password is correct.
			#
			if not secret_conf.check_password(password, salt,
							  true_password):
				self.rollback_error(tx, e_hdr=ERR_ACCESS,
						    e_msg='Неправильный пароль')
				return
			user_id = user[0]
			rights = user[3]
			user_name = user[4]
			#
			# Set cookies for the current user for one day.
			#
			self.set_secure_cookie('user_id', str(user_id),
					       expires_days=1)
			#
			# Rights specifies which actions the user can execute.
			#
			self.set_secure_cookie('rights', str(rights),
					       expires_days=1)
			if user_name:
				self.set_secure_cookie('user_name', user_name,
						       expires_days=1)
			yield tx.commit()
		except Exception as e:
			logger.exception('Error during login')
			self.rollback_error(tx, e_hdr=ERR_500)
			return
		self.redirect('/')
##
# Logout current user and delete all its cookies.
#
class LogoutHandler(BaseHandler):
	def get(self):
		self.clear_all_cookies()
		self.redirect('/')

##
# Handle drop of the report.
#
class DropHandler(BaseHandler):
	@tornado.gen.coroutine
	@need_rights(CAN_DELETE_REPORTS)
	def get(self):
		date = self.get_argument('date', None)
		if date is None:
			self.render_error(e_hdr=ERR_404,
					  e_msg='Не указана дата отчета')
			return
		tx = None
		try:
			tx = yield application.begin()
			yield delete_report_by_date(tx, date)
			tx.commit()
		except Exception:
			logger.exception("Error with deleting report by date")
			self.rollback_error(tx, e_hdr=ERR_500)
			return
		self.redirect('/')

##
# Get and return in the JSON format the parameter of the specified
# boiler along the specified year.
#
class GetYearParameterHandler(BaseHandler):
	##
	# Need to pass patameters boiler id, parameter id and
	# year.
	#
	@tornado.gen.coroutine
	@tornado.web.authenticated
	def get(self):
		if not self.check_rights(CAN_SEE_REPORTS, render=False):
			self.render_json_error('У вас нет прав на это действие')
			return
		boiler_id = self.get_argument('boiler_id', None)
		if boiler_id is None:
			self.render_json_error('Не указан идентификатор '\
					       'бойлерной')
			return
		param_name = self.get_argument('param_name', None)
		if param_name is None:
			self.render_json_error('Не указан идентификатор '\
					       'параметра')
			return
		year = self.get_argument('year', None)
		if year is None:
			self.render_json_error('Не указан год')
			return
		tx = None
		try:
			tx = yield application.begin()
			report = yield get_boiler_year_report(tx, boiler_id,
							      year,
							      [param_name, ])
			self.render_json(report)
			tx.commit()
		except:
			logger.exception('Error with getting parameter')
			if tx:
				tx.rollback()
			self.render_json_error('На сервере произошла ошибка, '\
					       'обратитесь к администратору')
			return

##
# Get values of the specified parameter from all boilers along the
# specified month.
#
class GetMonthParameterHandler(BaseHandler):
	available_columns = [ 'all_day_real_temp1', 'all_day_expected_temp1',
			      'all_day_real_temp2', 'all_day_expected_temp2',
			      'all_night_real_temp1',
			      'all_night_expected_temp1',
			      'all_night_real_temp2',
			      'all_night_expected_temp2',
			      'make_up_water_consum_real_ph',
			      'make_up_water_consum_expected_ph']

	@tornado.gen.coroutine
	@tornado.web.authenticated
	def get(self):
		if not self.check_rights(CAN_SEE_REPORTS, render=False):
			self.render_json_error('У вас нет прав на это действие')
			return
		year = self.get_argument('year', None)
		if year is None:
			self.render_json_error('Не указан год')
			return
		month = self.get_argument('month', None)
		if month is None:
			self.render_json_error('Не указан месяц')
			return
		columns_bin = self.request.arguments.get('columns[]', None)
		if columns_bin is None:
			self.render_json_error('Не указаны колонки')
			return
		columns = []
		for col in columns_bin:
			#
			# Need to decode, because it is handler for AJAX
			# that sends binary values.
			#
			col = col.decode('utf-8')
			#
			# Protect from SQL injection
			#
			if col not in GetMonthParameterHandler.available_columns:
				self.render_json_error('Нельзя получать '\
						       'столбец {}'.format(col))
				return
			columns.append(col)
		tx = None
		try:
			tx = yield application.begin()
			boilers = yield get_boilers_month_values(tx, year,
								 month, columns)
			self.render_json(boilers)
			tx.commit()
		except:
			logger.exception('Error with getting month parameter')
			if tx:
				tx.rollback()
			self.render_json_error('На сервере произошла ошибка, '\
					       'обратитесь к администратору')
			return


class BaseUsers(BaseHandler):

	current_user_id = None	


##
#	Users management (adding, editing, deleting a user)
#
class UsersHandler(BaseUsers):

	#	Message about success action (add, edit or delete)
	def get_success_action_message(self, suc_add, suc_del, suc_ed):
		if suc_add:
			return 'Пользователь успешно добавлен!'
		elif suc_del:
			return 'Пользователь успешно удален!'
		elif suc_ed:
			return 'Пользователь успешно отредактирован!'
		else: 
			return ''

	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		# user doesn't have access rights to view a list of users
		if not self.check_rights(CAN_SEE_USERS):
			return

		# when the user selected in the table
		# post request sends the email of the selected user
		email = self.get_argument('email', None)
		# if the user selected
		if email and email != 'null':
			# then set BaseUsers.current_user_id
			tx = yield pool.begin()
			try:
				user_id = yield get_user_by_email(tx, 'id', email)
				BaseUsers.current_user_id = int(user_id[0])
			except Exception:
				self.rollback_error(tx, e_hdr=ERR_500,
						    e_msg='На сервере произошла '\
							  'ошибка, обратитесь к '\
							  'администратору')
				return
			else:
				yield tx.commit()
		else:
			BaseUsers.current_user_id = None

		# enable_edit - true, if user has access to edit users
		# enable_edit - false, if user doesn't have access to edit users
		# enable_edit is used  in the file management.html to display 
		# add/edit/delete buttons
		user = self.get_current_user()
		enable_edit = user['rights'] & CAN_EDIT_USERS

		tx = yield pool.begin()
		users = []
		try:
			# get a list of all users from db
			users = yield get_all_users(tx, 'name, email, rights')
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
			users[i] = users[i] + ([],)
			# users[i] = (name, email, rights, perms)
			# where perms is list of bool

			# checking in the loop that a user has right PERMISSIONS[KEY]
			for key in permissions:
				perm = int(users[i][2]) & permissions[key][0]

				# if user has PERMISSIONS[KEY]
				if perm  == permissions[key][0]:
					# then add to list of rights
					users[i][3].append(permissions[key][1])

		# get a variable if was success adding, editing or deleteing user
		success_adding = bool(self.get_argument('suc_add', False))
		success_delete = bool(self.get_argument('suc_del', False))
		success_edit = bool(self.get_argument('suc_ed', False))
		# get a text of message
		success_action_message = self.get_success_action_message(\
			success_adding, success_delete, success_edit)

		# the number of pages
		num_of_pages = math.ceil(len(users)/NUMBER_USERS_IN_PAGE)
		# the currently displayed page
		page = int(self.get_argument('page', num_of_pages if success_adding else 1))

		# render page
		# bool enable_edit - to display adding, editing, deleting buttons
		# list<(name, email, int rights, list<bool> perms)> users - a list of all users
		# string success_action_message - succes action message if needed
		# int page - the currently displayed page
		# int num_in_page - the number of users on a one page
		# int num_of_pages - the number of pages
		self.render('users_management/management.html', \
			enable_edit = enable_edit,
			users = users,
			success_action_message = success_action_message,
			page = page,
			num_in_page = NUMBER_USERS_IN_PAGE,
			num_of_pages = num_of_pages)

##
#	Adding a user
#
class UsersAddHandler(BaseUsers):
	@tornado.web.authenticated
	def get(self):
		# render page, form of adding a user
		self.render('users_management/add_user.html', \
			pers = permissions)

	@tornado.gen.coroutine
	def post(self):
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
				return
			# else take first value (and the only)
			user_data[key] = user_data[key][0]
		
		# validate name of user
		if len(user_data['name']) > MAX_NAME_LENGTH or \
				not re.match(NAME_PATTERN, user_data['name']):
			self.render_error(e_hdr=ERR_INSERT,
						  e_msg='Имя не удовлетворяет заданным ограничениям')
			return

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

		# validate that the passwords match
		if user_data['password'] != user_data['confirm_password']:
			self.render_error(e_hdr=ERR_INSERT,
						  e_msg='Пароли не совпадают')
			return

		# confirm password is no longer needed
		user_data.pop('confirm_password', None)
		# generate hash password and salt by password
		psw = user_data['password']
		secret_conf.parse_config()
		(salt, psw_hash) = secret_conf.generate_password_hash(psw)
		user_data['password'] = psw_hash
		user_data['salt'] = salt

		tx = yield pool.begin()
		try:
			# checking that the user with that email already exists in the db
			duplicate_user = yield get_user_by_email(tx, 'id', user_data['email'])
			if duplicate_user:
				self.render_error(e_hdr=ERR_INSERT,\
				e_msg='Пользователь с таким email уже существует')
				return

			# insert the user into db
			yield insert_full_user(tx, user_data)
		except Exception as e:
			self.rollback_error(tx, e_hdr=ERR_INSERT,\
				e_msg='Ошибка при добавлении пользователя в базу данных')
		else:
			yield tx.commit()

		# redirect to users_management.html with the sucess adding flag
		self.redirect('/users_management?suc_add=True')

##
#	Editing a user
#
class UsersEditHandler(BaseUsers):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		# user doesn't have access rights to edit a users
		if not self.check_rights(CAN_EDIT_USERS):
			return

		# get the id of the person who editing
		user_id = BaseUsers.current_user_id
		if not user_id:
			self.render_error(e_hdr=ERR_EDIT,
					  e_msg='Не выбран пользователь')
			return

		# get all user's field which are editing by id
		tx = yield pool.begin()
		try:
			user = yield get_user_by_id(tx, 'email, name, rights', \
				user_id)
			if not user:
				self.rollback_error(tx, e_hdr=ERR_404,
						    e_msg='Пользователь с '\
						    	  'таким id не '\
						    	  'зарегистрирован')
				return
		except Exception:
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return
		tx.commit()

		# get user rights
		pers_value = {}
		for index, key in enumerate(permissions):
			pers_value[key] = bool(user[2] & permissions[key][0])

		# render page, form of editing a user:
		# string name - name of a user
		# string email - email of a user
		# dict pers - all rights
		# list<bool> pers_value - current rights of a user
		self.render('users_management/edit_user.html',
			email = user[0],
			name = user[1],
			pers = permissions,
			pers_value = pers_value)

	@tornado.gen.coroutine
	def post(self):
		#TODO: reduce this function

		# dict with fields that have changed and will be updated
		# key - name of field in db
		# value - new value of field
		updated_cols = {}

		# get the id of the person who editing
		user_id = BaseUsers.current_user_id
		if not user_id:
			self.render_error(e_hdr=ERR_EDIT,
					  e_msg='Не выбран пользователь')
			return

		tx = yield pool.begin()
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
				return

			# get changed name of user
			name = self.get_argument('name', None)
			if not name:
				# user's name was changed to an empty string
				self.render_error(e_hdr=ERR_EDIT,
							  	  e_msg='Не указано имя пользователя')
				return

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
				return

			# checking that the user with that email already exists in the db
			duplicate_user = yield get_user_by_email(tx, 'id', email)
			if duplicate_user and user_id != duplicate_user[0]:
				self.render_error(e_hdr=ERR_INSERT,\
				e_msg='Пользователь с таким email уже существует')
				return

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
					self.render_error(e_hdr=ERR_EDIT,
						    e_msg='Неправильный пароль')
					return
				# yes, it is! password is correct

				# validate that the password and confirm_password match
				new_psw = self.get_argument('password', None)
				confirm_new_psw = self.get_argument('confirm_password', None)
				# if the user input new password and confirm_password
				# but they are not matching
				if new_psw and confirm_new_psw:
					if new_psw != confirm_new_psw:
						# then render error page
						self.render_error(e_hdr=ERR_EDIT,
									  e_msg='Пароли не совпадают')
						return
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
				if (str(user_id) == current_user['user_id'].decode('utf-8')):
					# update cookies for the current user
					self.set_secure_cookie('user_id', str(user_id),
							       expires_days=1)
					self.set_secure_cookie('rights', str(user_perm_int),
							       expires_days=1)
					if user[4]:
						self.set_secure_cookie('user_name', name,
								       expires_days=1)
			# else nothing

		except Exception:
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return
		tx.commit()

		# redirect to users_management.html with the sucess editing flag
		self.redirect('/users_management?suc_ed=True')


##
#	Deleting a user
#
class UsersDeleteHandler(BaseUsers):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		# user doesn't have access rights to delete a users
		if not self.check_rights(CAN_EDIT_USERS):
			return

		# get the id of the person who deleting
		user_id = BaseUsers.current_user_id
		if not user_id:
			self.render_error(e_hdr=ERR_DELETE,
					  e_msg='Не выбран пользователь')
			return

		tx = yield pool.begin()
		try:
			# forbidden to delete itself
			current_user = self.get_current_user()
			if str(user_id) == current_user['user_id'].decode('utf-8'):
				self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='Вы не можете удалить себя')
				return

			# delete the user by id
			yield delete_user_by_id(tx, user_id)
		except Exception:
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return
		tx.commit()

		# redirect to users_management.html with the sucess deleting flag
		self.redirect('/users_management?suc_del=True')


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='VolComHoz')
	parser.add_argument('--port', '-p', type=int, required=True,
			    help='Port for the server running')
	parser.add_argument('--test', action='store_true', default=False)
	parser.add_argument('--test_args', nargs='*')
	args = parser.parse_args()
	secret_conf.parse_config()
	
	max_conn = secret_conf.max_db_connections
	idle = secret_conf.db_idle_seconds
	conn_timeout = secret_conf.db_connection_timeout
	db_name = secret_conf.db_name
	if args.test:
		db_name = 'test_volgograd'
	application.connect_db_args = {
		'max_connections': max_conn,
		'idle_seconds': idle,
		'wait_connection_timeout': conn_timeout,
		'host': secret_conf.db_host,
		'user': secret_conf.db_user,
		'passwd': secret_conf.db_passwd,
		'db': db_name,
		'charset': secret_conf.db_charset
	}
	application.connect_db()
	application.handlers_list = [
		(r'/', MainHandler),
		(r'/upload', UploadHandler),
		(r'/show_table', ShowHandler),
		(r'/login', LoginHandler),
		(r'/logout', LogoutHandler),
		(r'/drop_report', DropHandler),
		(r'/water_consum', WaterConsumHandler),
		(r'/year_plot', YearPlotHandler),
		(r'/get_year_parameter', GetYearParameterHandler),
		(r'/temperature', TemperatureHandler),
		(r'/get_month_parameter', GetMonthParameterHandler),
		(r'/users_management', UsersHandler)
	]
	application.template_path = 'templates/'
	application.static_path = 'static/'
	application.login_url = '/login'

	logger.setLevel(logging.DEBUG)
	formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	sh = logging.StreamHandler()
	sh.setFormatter(formatter)
	logger.addHandler(sh)
	logger.debug("Server is started on %s" % args.port)
	if args.test:
		argv = [sys.argv[0], ]
		if args.test_args:
			argv.extend(args.test_args)
		sys.argv = argv
		unittest.main()
	else:
		application.app = tornado.web.Application(
			handlers=application.handlers_list,
			autoreload=True,
			template_path=application.template_path,
			static_path=application.static_path,
			cookie_secret=secret_conf.cookie_secret,
			login_url=application.login_url
		)
		application.app.listen(args.port)
		tornado.ioloop.IOLoop.current().start()
