#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar

import tornado
import tornado.web
import tornado.gen

import application
from query import *
from constants import *
from base_handler import BaseHandler, need_rights

##
# Show the plot with values of one parameter of one boiler along
# the specified year.
#
class YearPlotHandler(BaseHandler):
	@tornado.gen.coroutine
	@need_rights(CAN_SEE_REPORTS)
	def get(self):
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
			tx = yield application.begin()
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
			self.rollback_error(tx, e_hdr=ERR_500)
