#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging

import tornado
import tornado.ioloop
import tornado.web
import tornado.gen

import secret_conf
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
			tx = yield db.begin()
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
			# TODO: dont store rights on a client side.
			# Rights specifies which actions the user can execute.
			#
			self.set_secure_cookie('rights', str(rights),
					       expires_days=1)
			if user_name:
				self.set_secure_cookie('user_name', user_name,
						       expires_days=1)
		except Exception as e:
			print(e)
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
		tx = None
		try:
			tx = yield db.begin()
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
			tx = yield db.begin()
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
			tx = yield db.begin()
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
	db.connect(max_connections = 20, idle_seconds = 7200,
		   wait_connection_timeout = 3, host = secret_conf.db_host,
		   user = secret_conf.db_user, passwd = secret_conf.db_passwd,
		   db = secret_conf.db_name, charset = "utf8"
	)

	app = tornado.web.Application(
		handlers=[
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
