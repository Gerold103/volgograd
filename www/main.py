#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from io import BytesIO
from datetime import datetime
from datetime import date as libdate
from zipfile import BadZipFile
import json
import argparse
import calendar
import logging

import tornado
import tornado.ioloop
import tornado.web
import tornado.gen

import tormysql

from xml_parser import parse_xls
from query import *
import secret_conf
import math

import re

pool = None

DUPLICATE_ERROR = 1062
ERR_INSERT = 'Ошибка вставки данных'
ERR_500    = 'Ошибка сервера'
ERR_ACCESS = 'Ошибка доступа'
ERR_LOGIN  = 'Ошибка входа'
ERR_UPLOAD = 'Ошибка загрузки'
ERR_404    = 'Не найдено'
ERR_PARAMETERS = 'Неверные параметры'
ERR_DELETE = 'Ошибка удаления'
ERR_EDIT = 'Ошибка редактирования'

CAN_UPLOAD_REPORTS = 0x01
CAN_SEE_REPORTS = 0x02
CAN_DELETE_REPORTS = 0x04
CAN_SEE_USERS = 0x08
CAN_EDIT_USERS = 0x10

permissions = {\
		'can_upload_reports': (CAN_UPLOAD_REPORTS, 'Загрузка отчетов'),\
		'can_see_reports': (CAN_SEE_REPORTS, 'Просмотр отчетов'),\
		'can_delete_reports': (CAN_DELETE_REPORTS, 'Удаление отчетов'),\
		'can_see_users': (CAN_SEE_USERS, 'Просмотр пользователей'),\
		'can_edit_users': (CAN_EDIT_USERS, 'Добавление и редактирование пользователей')}

NAME_PATTERN = '^[A-Za-zА-Яа-яЁё0-9]+(?:[ _-][A-Za-zА-Яа-яЁё0-9]+)*$'
MAX_NAME_LENGTH = 65535
NUMBER_USERS_IN_PAGE = 8

month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май',
	       'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь',
	       'Ноябрь', 'Декабрь']

logger = logging.getLogger('volgograd_log')

##
# Base class for users authentication and error pages rendering.
#
class BaseHandler(tornado.web.RequestHandler):
	##
	# User cookies are: user_id, rights. This methods return user_id.
	#
	def get_current_user(self):
		user_id = self.get_secure_cookie('user_id', None)
		if not user_id:
			return None
		user = {'user_id': user_id}
		user['rights'] = int(self.get_secure_cookie('rights'))
		user['user_name'] = self.get_secure_cookie('user_name', None)
		if user['user_name']:
			user['user_name'] = user['user_name'].decode('utf-8')
		return user
	
	##
	# Render an error page with specified an error header and a message.
	#
	def render_error(self, e_hdr, e_msg):
		self.render('error_page.html', error_header=e_hdr,
			    error_msg=e_msg)

	##
	# Render an error page, flush it to the user and then rollback
	# transaction. Such actions sequence allows the user to avoid waiting
	# for rollback.
	#
	@tornado.gen.coroutine
	def rollback_error(self, tx, e_hdr, e_msg):
			self.render_error(e_hdr=e_hdr, e_msg=e_msg)
			yield self.flush()
			yield tx.rollback()

	##
	# Check that the current use can execute specified actions.
	# @sa CAN_... flags.
	# @param rights Bitmask with actions flags.
	# @retval true  The user can execute all specified actions.
	# @retval false The user can't execute one or more of the specified
	#               actions.
	#
	@tornado.web.authenticated
	def check_rights(self, rights):
		user_rights = int(self.get_secure_cookie('rights'))
		if not (rights & user_rights):
			self.render_error(e_hdr=ERR_ACCESS,
					  e_msg='Доступ запрещен')
			return False
		return True

##
# Main page render.
#
class MainHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("index.html")

##
# Page for uploading new report tables.
#
class UploadHandler(BaseHandler):
	##
	# Render the page with a form for sending a table to the server.
	#
	@tornado.web.authenticated
	def get(self):
		if not self.check_rights(CAN_UPLOAD_REPORTS):
			return
		self.render('upload_xls.html')

	##
	# Upload to the database the boiler room.
	# @param tx   Transaction.
	# @param r_id Report identifier.
	# @param d_id District identifier.
	# @param room Map with the boiler room attributes.
	#
	@tornado.gen.coroutine
	def upload_room(self, tx, r_id, d_id, room):
		name = room['name']
		room_id = yield get_boiler_room_by_dist_and_name(tx, 'id', d_id,
								 name)
		if not room_id:
			yield insert_boiler_room(tx, d_id, name)
			room_id = yield get_boiler_room_by_dist_and_name(tx,
									 'id',
									 d_id,
									 name)
		assert(room_id)
		room_id = room_id[0]
		yield insert_boiler_room_report(tx, room, room_id, r_id)

	##
	# Upload to the database the district itself and all its boiler rooms.
	# @param tx       Transaction.
	# @param r_id     Report identifier.
	# @param district Map with the district name and rooms.
	#
	@tornado.gen.coroutine
	def upload_district(self, tx, r_id, district):
		name = district['name']
		#
		# Try to find the district. If not found then
		# first insert it to the database.
		#
		dist_id = yield get_district_by_name(tx, name, 'id')
		if not dist_id:
			yield insert_district(tx, name)
			dist_id = yield get_district_by_name(tx, name, 'id')
		assert(dist_id)
		#
		# get_... returns the entire district in which
		# first element is 'id' column.
		#
		dist_id = dist_id[0]

		for room in district['rooms']:
			yield self.upload_room(tx, r_id, dist_id, room)

	##
	# Upload the report to the database.
	#
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def post(self):
		if not self.check_rights(CAN_UPLOAD_REPORTS):
			return
		if 'xls-table' not in self.request.files:
			self.render_error(e_hdr=ERR_UPLOAD,
					  e_msg='Не указан файл')
			return
		fileinfo = self.request.files['xls-table'][0]
		tx = yield pool.begin()
		try:
			#
			# We emulate a file by BytesIO usage.
			#
			data = parse_xls(BytesIO(fileinfo['body']))
			#
			# Start a transaction. Commit only if all is good
			#
			yield insert_report(tx, data)
			#
			# Get the inserted report id for creating foreign key to
			# it in other tables.
			#
			report_id = yield get_report_by_date(tx, data['date'],
							     'id')
			assert(report_id)
			#
			# get_... returns the entire report in which first
			# element is 'id' column.
			#
			report_id = report_id[0]

			for district in data['districts']:
				yield self.upload_district(tx, report_id,
							   district)
			#
			# Get date in dd.mm.yyyy format
			date = data['date']
			# Create datetime python object
			date = datetime.strptime(date, '%d.%m.%Y')
			# Convert it to the format yyyy-mm-dd as in mysql
			# database.
			date = date.strftime('%Y-%m-%d')
			self.redirect('/show_table?date={}'.format(date))
		except BadZipFile:
			logger.exception("Unsupported file type")
			self.rollback_error(tx, e_hdr=ERR_INSERT,
					    e_msg='Файл имеет неподдерживаемый'\
						  ' формат')
		except Exception as e:
			logger.exception("Error with uploading report")
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				self.rollback_error(tx,
						    e_hdr=ERR_INSERT,
						    e_msg='Запись с таким '\
						    	  'идентификатором уже'\
							  ' существует')
			else:
				self.rollback_error(tx,
						    e_hdr=ERR_500,
						    e_msg='На сервере '\
						    	  'произошла ошибка, '\
						    	  'обратитесь к '\
						    	  'администратору')
		else:
			yield tx.commit()

##
# Choose date and show page with a report table on specified date.
#
class ShowHandler(BaseHandler):
	##
	# Render the calendar for the specified year.
	# @param year Print calendar with all months of this year.
	#
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def print_calendar(self, year):
		assert(year > 1970)
		if not self.check_rights(CAN_SEE_REPORTS):
			return
		uploaded_days_raw = []
		#
		# Find what reports were uploaded.
		#
		tx = yield pool.begin()
		try:
			uploaded_days_raw = yield get_report_dates_by_year(tx,
									   year)
		except Exception:
			logger.exception('Error with getting report dates by '\
					 'year')
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='Не удалось загрузить год')
			return
		yield tx.commit()
		uploaded_days = {}
		#
		# Group days by months.
		#
		for month, day in uploaded_days_raw:
			if month in uploaded_days:
				uploaded_days[month] |= {day}
			else:
				uploaded_days[month] = set([day, ])
		#
		# If not reports for the specified year then
		# render the error page - nothing to show.
		#
		if not uploaded_days:
			self.render_error(e_hdr=ERR_404,
					  e_msg='За указанный год %s отчетов '\
						'не найдено' % year)
			return
		months = []
		#
		# Build months table. i-th element - array of i-th
		# month with specified report date if it was found
		# in reports table.
		#
		for month_num in range(1, 13):
			#
			# Start week - number of the first day of
			# the month in the week: 0 - 6 = from
			# monday to sunday.
			#
			start_week, month_range =\
				calendar.monthrange(year, month_num)
			month = []
			day_iter = 1
			#
			# Weeks count - how many full weeks need
			# to contain this month.
			#
			weeks_cnt = int((start_week + month_range) / 7)
			if (start_week + month_range) % 7 != 0:
				weeks_cnt += 1
			for day in range(0, weeks_cnt * 7):
				#
				# If the day not in this month
				# then skip it.
				#
				if start_week > day or day_iter > month_range:
					month.append({'day_val': ''})
					continue

				#
				# If the day from this month but
				# a report for this day wasn't
				# found then print only day.
				#
				if month_num not in uploaded_days or\
				   day_iter not in uploaded_days[month_num]:
					month.append({'day_val': day_iter})
					day_iter += 1
					continue
				#
				# Else generate the link to the
				# report table.
				#
				month.append({'day_val': day_iter,
					      'full_date':
						get_str_date(year, month_num,
							     day_iter)})
				day_iter += 1
			months.append(month)
		self.render('choose_day.html', months=months,
			    month_names=month_names, year=year)

	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		if not self.check_rights(CAN_SEE_REPORTS):
			return
		#
		# If date is not specified then choose one.
		#
		date = self.get_argument('date', None)
		year = self.get_argument('year', libdate.today().year)
		try:
			year = int(year)
		except Exception:
			logger.exception("Year must be positive number")
			self.render_error(e_hdr=ERR_PARAMETERS,
					  e_msg='Год должен быть целым числом')
			return
		if not date:
			yield self.print_calendar(year)
			return
		tx = yield pool.begin()
		try:
			report = yield get_full_report_by_date(tx, date)
			if not report:
				self.rollback_error(tx,
						    e_hdr=ERR_404,
						    e_msg='Отчет за указанную '\
						    	  'дату не найден')
				return
		except Exception as e:
			logger.exception("Unsupported file type")
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				self.rollback_error(tx, e_hdr=ERR_INSERT,
						    e_msg='Запись с таким '\
							  'идентификатором уже'\
							  ' существует')
			else:
				self.rollback_error(tx, e_hdr=ERR_500,
						    e_msg='На сервере '\
							  'произошла ошибка, '\
							  'обратитесь к '\
							  'администратору')
		else:
			yield tx.commit()
			user = self.get_current_user()
			assert(user)
			assert('rights' in user)
			enable_delete = user['rights'] & CAN_DELETE_REPORTS
			self.render('show_table.html', **report,
				    get_val=get_html_val,
				    enable_delete=enable_delete)

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
		tx = yield pool.begin()
		try:
			#
			# Try to find the user by specified email.
			#
			user = yield get_user_by_email(tx, 'id, password, '\
						       'salt, rights, name',
						       email)
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
			# TODO: dont store rights on a client side.
			# Rights specifies which actions the user can execute.
			#
			self.set_secure_cookie('rights', str(rights),
					       expires_days=1)
			if user_name:
				self.set_secure_cookie('user_name', user_name,
						       expires_days=1)
		except Exception as e:
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
					    	  'ошибка, обратитесь к '\
					    	  'администратору')
			return
		else:
			yield tx.commit()
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
	@tornado.web.authenticated
	def get(self):
		if not self.check_rights(CAN_DELETE_REPORTS):
			self.render_error(e_hdr=ERR_ACCESS,
					  e_msg='Вы не можете удалять отчеты')
			return
		date = self.get_argument('date', None)
		if date is None:
			self.render_error(e_hdr=ERR_404,
					  e_msg='Не указана дата отчета')
			return
		tx = yield pool.begin()
		try:
			yield delete_report_by_date(tx, date)
		except Exception:
			logger.exception("Error with deleting report by date")
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return
		tx.commit()
		self.redirect('/')

##
# Plot average values of parameters of all boiler rooms for the
# choosed month.
#
class MonthPlotHandler(BaseHandler):
	@tornado.gen.coroutine
	@tornado.web.authenticated
	def get(self):
		if not self.check_rights(CAN_SEE_REPORTS):
			return
		#
		# Need to specify both the year and the month.
		#
		year = self.get_argument('year', None)
		if year is None:
			self.render_error(e_hdr=ERR_404, e_msg='Не указан год')
			return
		month = self.get_argument('month', None)
		if month is None:
			self.render_error(e_hdr=ERR_404,
					  e_msg='Не указан месяц')
			return
		try:
			year = int(year)
			month = int(month)
			if year <= 0 or month <= 0:
				raise ValueError('Illegal month or year')
		except Exception:
			logger.exception('Year and month must be positive '\
					 'numbers')
			self.render_error(e_hdr=ERR_PARAMETERS,
					  e_msg='Год и месяц должны быть '\
						'положительными числами')
			return
		tx = None
		try:
			start_week, month_range =\
				calendar.monthrange(year, month)
			tx = yield pool.begin()
			statistics = None
			try:
				statistics = yield get_avg_reports_by_month(tx,
									   year,
									  month)
			except Exception:
				logger.exception('Error with getting average '\
						 'values for month reports')
				self.rollback_error(tx, e_hdr=ERR_500,
						    e_msg='На сервере '\
							  'произошла ошибка, '\
							  'обратитесь к '\
							  'администратору')
				return
			self.render('month_plot.html', month_names=month_names,
				    month=month, year=year,
				    month_range=month_range,
				    statistics=statistics, get_val=get_html_val,
				    get_float=get_html_float_to_str,
				    get_date=get_str_date)
			tx.commit()
		except Exception:
			logger.exception("Error with rendering month report")
			if tx:
				tx.rollback()
			self.render_error(e_hdr=ERR_500,
					  e_msg='Ошибка при генерации страницы')
			return


##
#	Users management (adding, editing, deleting a user)
#
class UsersHandler(BaseHandler):
	
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
class UsersAddHandler(BaseHandler):
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
class UsersEditHandler(BaseHandler):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		# user doesn't have access rights to edit a users
		if not self.check_rights(CAN_EDIT_USERS):
			return

		# get the email of the person who editing
		email = self.get_argument('email', None)
		if not email:
			self.render_error(e_hdr=ERR_EDIT,
					  e_msg='Не выбран пользователь')
			return

		# get all user's field which are editing by email
		tx = yield pool.begin()
		try:
			user = yield get_user_by_email(tx, 'name, rights', email)
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
			pers_value[key] = bool(user[1] & permissions[key][0])

		# render page, form of editing a user:
		# string name - name of a user
		# string email - email of a user
		# dict pers - all rights
		# list<bool> pers_value - current rights of a user
		self.render('users_management/edit_user.html',
			name = user[0],
			email = email,
			pers = permissions,
			pers_value = pers_value)

	@tornado.gen.coroutine
	def post(self):
		# dict with fields that have changed and will be updated
		# key - name of field in db
		# value - new value of field
		updated_cols = {}

		# get the email of the user who edited
		email = self.get_argument('email', None)
		if not email:
			self.render_error(e_hdr=ERR_404,
					  e_msg='Пользователя с таким email не существует')
			return

		tx = yield pool.begin()
		try:
			# get all user's data by email
			user = yield get_user_by_email(tx, 'id, password, '\
			       'salt, rights, name',
			       email)
			if not user:
				self.rollback_error(tx, e_hdr=ERR_404,
						    e_msg='Пользователь с '\
						    	  'таким email не '\
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
				yield update_user_by_email(tx, updated_cols, email)

				# if the current user has changed himself
				current_user = self.get_current_user()
				current_email = yield get_user_by_id(tx, 'email',\
					current_user['user_id'])
				if (email == current_email[0]):
					# update cookies for the current user
					self.set_secure_cookie('user_id', str(user[0]),
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
class UsersDeleteHandler(BaseHandler):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		# user doesn't have access rights to delete a users
		if not self.check_rights(CAN_EDIT_USERS):
			return

		# get the email of the person who deleting
		email = self.get_argument('email', None)
		if not email:
			self.render_error(e_hdr=ERR_DELETE,
					  e_msg='Не выбран пользователь')
			return

		tx = yield pool.begin()
		try:
			# forbidden to delete itself
			current_user = self.get_current_user()
			current_email = yield get_user_by_id(tx, 'email',\
				current_user['user_id'])
			current_email = current_email[0]
			if current_email == email:
				self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='Вы не можете удалить себя')
				return

			# delete the user by email
			yield delete_user_by_email(tx, email)
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
	args = parser.parse_args()
	secret_conf.parse_config()
	pool = tormysql.helpers.ConnectionPool(
		max_connections = 20, #max open connections
		idle_seconds = 7200, #conntion idle timeout time, 0 is not timeout
		wait_connection_timeout = 3, #wait connection timeout
		host = secret_conf.db_host,
		user = secret_conf.db_user,
		passwd = secret_conf.db_passwd,
		db = secret_conf.db_name,
		charset = "utf8"
	)

	app = tornado.web.Application(
		handlers=[
			(r'/', MainHandler),
			(r'/upload', UploadHandler),
			(r'/show_table', ShowHandler),
			(r'/login', LoginHandler),
			(r'/logout', LogoutHandler),
			(r'/drop_report', DropHandler),
			(r'/month_plot', MonthPlotHandler),
			(r'/users_management', UsersHandler),
			(r'/users_management/add', UsersAddHandler),
			(r'/users_management/edit', UsersEditHandler),
			(r'/users_management/delete', UsersDeleteHandler)
			],
		autoreload=True,
		template_path="templates/",
		static_path="static/",
		cookie_secret=secret_conf.cookie_secret,
		login_url='/login')
	app.listen(args.port)
	logger.setLevel(logging.DEBUG)
	formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	sh = logging.StreamHandler()
	sh.setFormatter(formatter)
	logger.addHandler(sh)
	logger.debug("Server is started on %s" % args.port)
	tornado.ioloop.IOLoop.current().start()
