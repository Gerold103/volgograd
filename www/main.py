#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from io import BytesIO
import json

import tornado
import tornado.ioloop
import tornado.web
import tornado.gen

import tormysql

from xml_parser import parse_xls
from query import *
import secret_conf

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

DUPLICATE_ERROR = 1062

CAN_UPLOAD_REPORTS = 0x01
CAN_SEE_REPORTS = 0x02

##
# Base class for users authentication and error pages rendering.
#
class BaseHandler(tornado.web.RequestHandler):
	##
	# User cookies are: user_id, rights. This methods return user_id.
	#
	def get_current_user(self):
		return self.get_secure_cookie("user_id", None)
	
	##
	# Render an error page with specified an error header and a message.
	#
	def render_error(self, e_hdr, e_msg):
		self.render('error_page.html', error_header=e_hdr,
			    error_msg=e_msg)

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
			self.render_error(e_hdr='Ошибка доступа',
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
	# Upload the report table to the database.
	#
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def post(self):
		if not self.check_rights(CAN_UPLOAD_REPORTS):
			return
		if 'xls-table' not in self.request.files:
			self.render_error(e_hdr='Ошибка загрузки',
					  e_msg='Не указан файл')
			return
		fileinfo = self.request.files['xls-table'][0]
		#
		# We emulate a file by BytesIO usage.
		#
		data = parse_xls(BytesIO(fileinfo['body']))
		#
		# Start a transaction. Commit only if all is good
		#
		tx = yield pool.begin()
		try:
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
			self.render('show_table.html', data=data)
		except Exception as e:
			yield tx.rollback()
			print(e)
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				self.render_error(e_hdr='Ошибка вставки данных',
						  e_msg='Запись с таким '\
							'идентификатором уже '\
							'существует')
			else:
				self.render_error(e_hdr='Ошибка сервера',
						  e_msg='На сервере произошла '\
						  	'ошибка, обратитесь к '\
						  	'администратору')
		else:
			yield tx.commit()

class ShowHandler(BaseHandler):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		if not self.check_rights(CAN_SEE_REPORTS):
			return
		date = self.get_argument('date', None)
		if not date:
			self.render('choose_day.html')
			return
		tx = yield pool.begin()
		try:
			report = yield get_full_report_by_date(tx, date)
			if not report:
				yield tx.rollback()
				self.render('choose_day.html')
				return
		except Exception as e:
			yield tx.rollback()
			print(e)
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				self.render('error_page.html', e_hdr='Ошибка вставки '\
							'данных', e_msg='Запись с таким '\
							'идентификатором уже существует')
			else:
				self.render('error_page.html', e_hdr='Ошибка',
							e_msg='На сервере произошла ошибка, обратитесь'\
									  ' к администратору')
		else:
			yield tx.commit()
			self.render('show_table.html', data=report)

class LoginHandler(BaseHandler):
	def get(self):
		if self.get_current_user():
			self.render_error(e_hdr='Ошибка входа',
							  e_msg='Вы уже авторизованы')
			return
		self.render('login.html')

	@tornado.gen.coroutine
	def rollback_error(self, tx, e_msg):
			self.render_error(e_hdr='Ошибка входа', e_msg=e_msg)
			yield self.flush()
			yield tx.rollback()

	@tornado.gen.coroutine
	def post(self):
		if self.get_current_user():
			self.render_error(e_hdr='Ошибка входа',
							  e_msg='Вы уже авторизованы')
			return
		email = self.get_argument('email', None)
		if not email:
			self.render_error(e_hdr='Ошибка входа',
							  e_msg='Не указан email')
			return
		password = self.get_argument('password', None)
		if not password:
			self.render_error(e_hdr='Ошибка входа',
							  e_msg='Не указан пароль')
			return
		tx = yield pool.begin()
		try:
			user = yield get_user_by_email(tx, 'id, password, salt, rights',
										   email)
			if not user:
				self.rollback_error(tx, e_msg='Пользователь с таким email '\
									'не зарегистрирован')
				return
			if not secret_conf.check_password(password, user[2], user[1]):
				self.rollback_error(tx, e_msg='Неправильный пароль')
				return
			user_id = user[0]
			rights = user[3]
			self.set_secure_cookie('user_id', str(user_id), expires_days=1)
			self.set_secure_cookie('rights', str(rights), expires_days=1)
		except Exception as e:
			self.rollback_error(tx, e_msg='На сервере произошла ошибка, '\
								'обратитесь к администратору')
			return
		else:
			yield tx.commit()
			self.redirect('/')

class LogoutHandler(BaseHandler):
	def get(self):
		self.clear_all_cookies()
		self.redirect('/')

if __name__ == "__main__":
	app = tornado.web.Application(
		handlers=[
			(r'/', MainHandler),
			(r'/upload', UploadHandler),
			(r'/show_table', ShowHandler),
			(r'/login', LoginHandler),
			(r'/logout', LogoutHandler)
			],
		autoreload=True,
		template_path="templates/",
		static_path="static/",
		cookie_secret=secret_conf.cookie_secret,
		login_url='/login')
	app.listen(8888)
	print("Server is started on 8888")
	tornado.ioloop.IOLoop.current().start()
