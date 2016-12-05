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

pool = tormysql.helpers.ConnectionPool(
	max_connections = 20, #max open connections
	idle_seconds = 7200, #conntion idle timeout time, 0 is not timeout
	wait_connection_timeout = 3, #wait connection timeout
	host = "127.0.0.1",
	user = "root",
	passwd = "126241441008Pf",
	db = "volgograd",
	charset = "utf8"
)

DUPLICATE_ERROR = 1062

class MainHandler(tornado.web.RequestHandler):
	def get(self):
		self.render("index.html")

class UploadHandler(tornado.web.RequestHandler):
	def get(self):
		self.render('upload_xls.html')

	@tornado.gen.coroutine
	def post(self):
		fileinfo = self.request.files['xls-table'][0]
		data = parse_xls(BytesIO(fileinfo['body']))
		tx = yield pool.begin()
		try:
			yield insert_report(tx, data)
			report_id = yield get_report_by_date(tx, data['date'], 'id')
			assert(report_id)
			report_id = report_id[0]

			for district in data['districts']:
				dist_name = district['name']
				dist_id = yield get_district_by_name(tx, dist_name, 'id')
				if not dist_id:
					yield insert_district(tx, dist_name)
					dist_id = yield get_district_by_name(tx, dist_name, 'id')
				assert(dist_id)
				dist_id = dist_id[0]

				for room in district['rooms']:
					room_name = room['name']
					room_id = yield get_boiler_room_by_dist_and_name(tx, 'id',
															 dist_id, room_name)
					if not room_id:
						yield insert_boiler_room(tx, dist_id, room_name)
						room_id = yield get_boiler_room_by_dist_and_name(tx,
													   'id', dist_id, room_name)
					assert(room_id)
					room_id = room_id[0]
					yield insert_boiler_room_report(tx, room, room_id,
													report_id)

		except Exception as e:
			yield tx.rollback()
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				self.render('error_page.html', error_header='Ошибка вставки '\
							'данных', error_msg='Запись с таким '\
							'идентификатором уже существует')
			else:
				self.render('error_page.html', error_header='Ошибка',
							error_msg='На сервере произошла ошибка, обратитесь'\
									  ' к администратору')
		else:
			yield tx.commit()
			self.render('show_table.html', data=data)


class ShowHandler(tornado.web.RequestHandler):
	@tornado.gen.coroutine
	def get(self):
		date = self.get_argument('date', None)
		if not date:
			self.render('choose_day.html')
			return
		tx = yield pool.begin()
		try:
			report = yield get_full_report_by_date(tx, date)
			if not report:
				self.render('choose_day.html')
				return
		except Exception as e:
			yield tx.rollback()
			if len(e.args) > 0 and e.args[0] == DUPLICATE_ERROR:
				self.render('error_page.html', error_header='Ошибка вставки '\
							'данных', error_msg='Запись с таким '\
							'идентификатором уже существует')
			else:
				self.render('error_page.html', error_header='Ошибка',
							error_msg='На сервере произошла ошибка, обратитесь'\
									  ' к администратору')
		else:
			yield tx.commit()
			self.render('show_table.html')

if __name__ == "__main__":
	app = tornado.web.Application(
		handlers=[
			(r'/', MainHandler),
			(r'/upload', UploadHandler),
			(r'/show_table', ShowHandler),
			],
		autoreload=True,
		template_path="templates/",
		static_path="static/",)
	app.listen(8888)
	print("Server is started on 8888")
	tornado.ioloop.IOLoop.current().start()
