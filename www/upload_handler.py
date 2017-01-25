#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from io import BytesIO
from datetime import datetime
from zipfile import BadZipFile

import tornado
import tornado.web
import tornado.gen

import application
from xml_parser import parse_xls
from base_handler import BaseHandler
from query import *
from constants import *

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
		cols = ['id', ]
		room_id = yield get_boiler_room_by_dist_and_name(tx, cols, d_id,
								 name)
		if not room_id:
			yield insert_boiler_room(tx, d_id, name)
			room_id =\
				yield get_boiler_room_by_dist_and_name(tx, cols,
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
		dist_id = yield get_district_by_name(tx, name, ['id', ])
		if not dist_id:
			yield insert_district(tx, name)
			dist_id = yield get_district_by_name(tx, name, ['id', ])
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
		tx = None
		try:
			tx = yield application.begin()
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
							     ['id', ])
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
