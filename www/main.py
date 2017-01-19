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

pool = None

DUPLICATE_ERROR = 1062
ERR_INSERT = 'Ошибка вставки данных'
ERR_500    = 'Ошибка сервера'
ERR_ACCESS = 'Ошибка доступа'
ERR_LOGIN  = 'Ошибка входа'
ERR_UPLOAD = 'Ошибка загрузки'
ERR_404    = 'Не найдено'
ERR_PARAMETERS = 'Неверные параметры'

CAN_UPLOAD_REPORTS = 0x01
CAN_SEE_REPORTS = 0x02
CAN_DELETE_REPORTS = 0x04

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
	def render_error(self, e_hdr, e_msg, template='error_page.html',
			 **kwargs):
		self.render(template, error_header=e_hdr,
			    error_msg=e_msg, **kwargs)

	##
	# Render the answer in the JSON format with the specified
	# response data.
	#
	def render_json(self, data):
		self.write(json.dumps({ 'response': data }))

	##
	# Render the error information in the JSON format with the
	# specified error message.
	#
	def render_json_error(self, msg):
		self.write(json.dumps({ 'error': msg }))

	##
	# Render an error page, flush it to the user and then rollback
	# transaction. Such actions sequence allows the user to avoid waiting
	# for rollback.
	#
	@tornado.gen.coroutine
	def rollback_error(self, tx, e_hdr, e_msg):
		self.render_error(e_hdr=e_hdr, e_msg=e_msg)
		yield self.flush()
		if tx:
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
	def check_rights(self, rights, render=True):
		user_rights = int(self.get_secure_cookie('rights'))
		if not (rights & user_rights):
			if render:
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
						'не найдено' % year,
					  template='choose_day_year_error.html',
					  year=year)
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
			if year < 1970:
				raise ValueError('Illegal year')
		except Exception:
			logger.exception("Year must be positive number")
			self.render_error(e_hdr=ERR_PARAMETERS,
					  e_msg='Год должен быть целым '\
						'положительным числом от 1970')
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
# Show the plot with values of one parameter of one boiler along
# the specified year.
#
class YearPlotHandler(BaseHandler):
	@tornado.gen.coroutine
	@tornado.web.authenticated
	def get(self):
		if not self.check_rights(CAN_SEE_REPORTS):
			return
		year = self.get_argument('year', None)
		if year is None:
			self.render_error(e_hdr=ERR_404, e_msg='Не указан год')
			return
		try:
			year = int(year)
			if year <= 0:
				raise ValueError('Illegal year')
		except Exception:
			logger.exception('Year must be positive number')
			self.render_error(e_hdr=ERR_PARAMETERS,
					  e_msg='Год должен быть положительным'\
						' числом')
			return
		days = calendar.isleap(year) and 366 or 365
		tx = None
		try:
			tx = yield pool.begin()
			ids = yield get_boiler_room_ids_and_titles(tx)
			column = ['all_day_expected_temp1', ]
			first_id = ids[0]['id']
			first_report =\
				yield get_boiler_year_report(tx, first_id,
							     year, column)
			year_temperature = yield get_year_temperature(tx, year)
			self.render("year_plot.html", year=year,
				    days_count=days, boiler_ids=ids,
				    first_report=first_report,
				    first_column=column[0],
				    year_temperature=year_temperature)
			tx.commit()
		except:
			logger.exception('Error with getting boiler room ids '\
					 'and reports about first room')
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return

##
# Page with the table of deviations of the specified parameter
# from its expected value.
# On the page all boilers are showed.
#
class MonthOneParameterHandler(BaseHandler):
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
			tx = yield pool.begin()
			#
			# We don't need to render a first
			# parameter, because it will be requested
			# from a client side after loading via
			# AJAX.
			# To avoid strongly increasing page size
			# and thus page loading speed, we avoid
			# to render the page already with all
			# parameters of all boilers. Instead of
			# this way, the parameters are downloading
			# by the client as requiered.
			# So we need to pass only boiler and
			# parameter identifiers.
			#
			districts = yield get_districts_with_boilers(tx)
			start_week, month_range =\
				calendar.monthrange(year, month)
			self.render("month_one_parameter.html", year=year,
				    days_count=month_range, districts=districts,
				    month_names=month_names, month=month,
				    get_date=get_str_date, get_val=get_html_val)
			tx.commit()
		except:
			logger.exception('Error with getting districts and '\
					 'boilers')
			self.rollback_error(tx, e_hdr=ERR_500,
					    e_msg='На сервере произошла '\
						  'ошибка, обратитесь к '\
						  'администратору')
			return

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
			tx = yield pool.begin()
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
		columns = [col.decode('utf-8') for col in columns_bin]
		tx = None
		try:
			tx = yield pool.begin()
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
			(r'/year_plot', YearPlotHandler),
			(r'/get_year_parameter', GetYearParameterHandler),
			(r'/month_one_parameter', MonthOneParameterHandler),
			(r'/get_month_parameter', GetMonthParameterHandler)
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
