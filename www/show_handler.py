#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import application
import calendar
from datetime import date

import tornado
import tornado.web
import tornado.gen

from query import *
from constants import *
from base_handler import BaseHandler, need_rights

##
# Choose date and show page with a report table on specified date.
#
class ShowHandler(BaseHandler):
	##
	# Render the calendar for the specified year.
	# @param year Print calendar with all months of this year.
	#
	@tornado.gen.coroutine
	@need_rights(CAN_SEE_REPORTS)
	def print_calendar(self, year):
		assert(year > 1970)
		uploaded_days_raw = []
		#
		# Find what reports were uploaded.
		#
		tx = None
		try:
			tx = yield application.begin()
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

	@tornado.gen.coroutine
	@need_rights(CAN_SEE_REPORTS)
	def get(self):
		#
		# If date is not specified then choose one.
		#
		full_date = self.get_argument('date', None)
		year = self.get_argument('year', date.today().year)
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
		if not full_date:
			yield self.print_calendar(year)
			return
		tx = None
		try:
			tx = yield application.begin()
			report = yield get_full_report_by_date(tx, full_date)
			if not report:
				self.rollback_error(tx, e_hdr=ERR_404,
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
