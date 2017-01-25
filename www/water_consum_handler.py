#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar

import tornado
import tornado.web
import tornado.gen

import application
from query import *
from constants import *
from base_handler import BaseHandler

##
# Plot average values of parameters of all boiler rooms for the
# choosed month.
#
class WaterConsumHandler(BaseHandler):
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
			tx = yield application.begin()
			statistics = None
			cols = ['net_water_consum_expected_ph',
				'net_water_consum_real_ph',
				'make_up_water_consum_expected_ph',
				'make_up_water_consum_real_ph',
				'make_up_water_consum_real_pd',
				'make_up_water_consum_real_pm']
			try:
				statistics =\
					yield get_sum_reports_by_month(tx, year,
								       month,
								       cols)
			except Exception:
				logger.exception('Error with getting average '\
						 'values for month reports')
				self.rollback_error(tx, e_hdr=ERR_500,
						    e_msg='На сервере '\
							  'произошла ошибка, '\
							  'обратитесь к '\
							  'администратору')
				return
			self.render('water_consum.html', month_names=month_names,
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
