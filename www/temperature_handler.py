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
# Page with the table of deviations of the specified parameter
# from its expected value.
# On the page all boilers are showed.
#
class TemperatureHandler(BaseHandler):
	@tornado.gen.coroutine
	@need_rights(CAN_SEE_REPORTS)
	def get(self):
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
			tx = yield application.begin()
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
			self.render("temperature.html", year=year,
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
