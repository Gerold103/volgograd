#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
from datetime import date as libdate

import tornado
import tornado.gen

boiler_room_report_cols = [
	'T1', 'T2', 'gas_pressure',
	'boilers_all', 'boilers_in_use', 'torchs_in_use', 'boilers_reserve',
	'boilers_in_repair',
	'net_pumps_in_work', 'net_pumps_reserve', 'net_pumps_in_repair',
	'all_day_expected_temp1', 'all_day_expected_temp2',
	'all_day_real_temp1', 'all_day_real_temp2',
	'all_night_expected_temp1', 'all_night_expected_temp2',
	'all_night_real_temp1', 'all_night_real_temp2',
	'net_pressure1', 'net_pressure2',
	'net_water_consum_expected_ph', 'net_water_consum_real_ph',
	'make_up_water_consum_expected_ph', 'make_up_water_consum_real_ph',
	'make_up_water_consum_real_pd', 'make_up_water_consum_real_pm',
	'hardness', 'transparency'
]

##
# Get a report for the specified date.
# @param tx   Current transaction.
# @param date Date on which need to find a report.
# @param cols String with columns separated by commas: 'id, name, ...'.
#
# @retval Tuple with specified columns or the empty tuple.
#
@tornado.gen.coroutine
def get_report_by_date(tx, date, cols):
	sql = "SELECT {} FROM reports WHERE date = "\
	      "STR_TO_DATE(%s, %s)".format(cols)
	params = (date, '%d.%m.%Y')
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchone()

##
# Get report days and months by the given year.
# @param tx   Current transaction.
# @param year Year which need to find.
#
@tornado.gen.coroutine
def get_report_dates_by_year(tx, year):
	sql = "SELECT month(date) as month, day(date) as day "\
	      "FROM reports WHERE year(date) = %s"
	params = (year, )
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchall()

@tornado.gen.coroutine
def delete_report_by_date(tx, date):
	sql = "DELETE FROM reports WHERE date = %s"
	params = (date, )
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchone()

##
# Get a district by the name.
# @param name District name.
# @param cols String with columns separated by commas: 'id, name', for example.
#
# @retval Tuple with found distict or the empty tuple.
#
@tornado.gen.coroutine
def get_district_by_name(tx, name, cols):
	sql = "SELECT {} FROM districts WHERE name = %s".format(cols)
	params = (name)
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchone()

##
# Insert the new district to the districts table.
#
@tornado.gen.coroutine
def insert_district(tx, name):
	sql = "INSERT INTO districts(name) VALUES (%s)"
	params = (name)
	yield tx.execute(query=sql, params=params)

##
# Get a boiler room by the specified district identifier and the boiler room
# name.
# @param tx      Current transaction.
# @param cols    String with columns separated by commas: 'id, name, ...'.
# @param dist_id Identifier of the district - 'id' from 'districts' table.
# @param name    Name of the boiler room.
#
# @retval Tuple with specified columns or the empty tuple.
#
@tornado.gen.coroutine
def get_boiler_room_by_dist_and_name(tx, cols, dist_id, name):
	sql = "SELECT {} FROM boiler_rooms WHERE district_id = %s AND "\
	      "name = %s".format(cols)
	params = (dist_id, name)
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchone()

##
# Insert the new boiler room to the boiler rooms table.
# @param tx      Current transaction.
# @param dist_id Identifier of the district - 'id' from 'districts' table.
# @param name    Name of the new boiler room.
#
@tornado.gen.coroutine
def insert_boiler_room(tx, dist_id, name):
	sql = "INSERT INTO boiler_rooms(district_id, name) "\
	      "VALUES (%s, %s)"
	params = (dist_id, name)
	yield tx.execute(query=sql, params=params)

##
# Get a value from iterable object by name, or None, if the object doesn't
# contain the name.
#
def get_safe_val(src, name):
	if not name in src:
		return None
	return src[name]

##
# Get a string representing the specified date.
#
def get_str_date(year, month, day):
	return libdate(year=year, month=month, day=day).strftime('%Y-%m-%d')

##
# Convert not existing and None values to '-' for html output.
#
def get_html_val(src, name):
	if not name in src or src[name] is None:
		return '-'
	return src[name]

##
# Get string representation of a float value useful for output to
# an user on a web page.
#
def get_html_float_to_str(src, name, precision=2):
	try:
		return ('{:.' + str(precision) + 'f}').format(float(src[name]))
	except:
		return '-'

##
# Insert the new report about the specified boiler room.
# @param tx        Current transaction.
# @param src       Dictionary with the boiler room attributes.
# @param room_id   Identifier of the boiler room - 'id' from
#                  'boiler_rooms' table.
# @param report_id Identifier of the report - 'id' from 'reports' table.
#
@tornado.gen.coroutine
def insert_boiler_room_report(tx, src, room_id, report_id):
	sql = 'INSERT INTO boiler_room_reports '\
	      'VALUES (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '\
		       '%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '\
		       '%s, %s, %s, %s, %s, %s)'
	assert(room_id)
	assert(report_id)
	global boiler_room_report_cols
	params = [room_id, report_id]
	for col in boiler_room_report_cols:
		params.append(get_safe_val(src, col))
	yield tx.execute(query=sql, params=params)

##
# Insert a report to the reports table. If some columns absense then replace
# them with NULL values.
#
@tornado.gen.coroutine
def insert_report(tx, src):
	sql = 'INSERT INTO reports VALUES (NULL, STR_TO_DATE(%s, %s), %s, %s, '\
	      '%s, %s, %s, STR_TO_DATE(%s, %s), %s, %s, %s, %s, %s, %s, %s)'
	params = (get_safe_val(src, 'date'),
		  '%d.%m.%Y',
		  get_safe_val(src, 'temp_average_air'),
		  get_safe_val(src, 'temp_average_water'),
		  get_safe_val(src, 'expected_temp_air_day'),
		  get_safe_val(src, 'expected_temp_air_night'),
		  get_safe_val(src, 'expected_temp_air_all_day'),
		  get_safe_val(src, 'forecast_date'),
		  '%d.%m.%Y',
		  get_safe_val(src, 'forecast_weather'),
		  get_safe_val(src, 'forecast_direction'),
		  get_safe_val(src, 'forecast_speed'),
		  get_safe_val(src, 'forecast_temp_day_from'),
		  get_safe_val(src, 'forecast_temp_day_to'),
		  get_safe_val(src, 'forecast_temp_night_from'),
		  get_safe_val(src, 'forecast_temp_night_to'))
	yield tx.execute(query=sql, params=params)

##
# Get all boiler room reports by the specified date, joined with corresponding
# district and boiler room names.
# @param tx   Current transaction.
# @param date Date by which need to find all reports.
#
# @retval Array of tuples.
#
@tornado.gen.coroutine
def get_full_report_by_date(tx, date):
	sql = 'SELECT * FROM reports WHERE date = STR_TO_DATE(%s, %s)'
	params = (date, '%Y-%m-%d')
	cursor = yield tx.execute(query=sql, params=params)
	report = cursor.fetchone()
	if not report:
		return None
	rep_id = report[0]
	sql = 'SELECT districts.name, boiler_rooms.name, {} '\
	      'FROM districts JOIN boiler_rooms '\
	      'ON(districts.id = boiler_rooms.district_id) '\
	      'JOIN boiler_room_reports '\
	      'ON (boiler_room_reports.boiler_room_id = '\
		  'boiler_rooms.id AND boiler_room_reports.report_id = {})'\
	      .format(",".join(boiler_room_report_cols), rep_id)
	cursor = yield tx.execute(sql)
	#
	# First, create a dictionary of the following format:
	#
	# {
	#     'district1': [room1, room2, ...],
	#     'district2': [room3, room4, ...],
	#     ....
	# }
	districts = {}
	next_row = cursor.fetchone()
	while next_row:
		dist_name = next_row[0]
		#
		# If it is first room for this district, then create a list
		# for it. Else - use existing.
		#
		if dist_name not in districts:
			districts[dist_name] = []
		rooms = districts[dist_name]
		next_report = {'name': next_row[1]}
		i = 2
		for col in boiler_room_report_cols:
			next_report[col] = next_row[i]
			i += 1
		rooms.append(next_report)
		next_row = cursor.fetchone()
	result = {}
	result['date'] = report[1]
	result['temp_average_air'] = report[2]
	result['temp_average_water'] = report[3]
	result['expected_temp_air_day'] = report[4]
	result['expected_temp_air_night'] = report[5]
	result['expected_temp_air_all_day'] = report[6]
	result['forecast_date'] = report[7]
	result['forecast_weather'] = report[8]
	result['forecast_direction'] = report[9]
	result['forecast_speed'] = report[10]
	result['forecast_temp_day_from'] = report[11]
	result['forecast_temp_day_to'] = report[12]
	result['forecast_temp_night_from'] = report[13]
	result['forecast_temp_night_to'] = report[14]
	result['districts'] = []
	for dist, rooms in sorted(districts.items(), key=lambda x: x[0]):
		district = {'name': dist}
		rooms[0]['district'] = dist
		for i in range(1, len(rooms)):
			rooms[i]['district'] = None
		district['rooms'] = rooms
		result['districts'].append(district)
	return result

##
# Get average values of all parameters for the specified month
# in all boiler rooms.
#
@tornado.gen.coroutine
def get_avg_reports_by_month(tx, year, month):
	get_avg = lambda x: 'AVG({})'.format(x)
	avg_list = list(map(get_avg, boiler_room_report_cols))
	sql = 'SELECT DAY(date), {} FROM reports JOIN boiler_room_reports '\
	      'ON(reports.id = report_id) WHERE MONTH(date) = %s and '\
	      'YEAR(date) = %s GROUP BY date;'.format(",".join(avg_list))
	params = (month, year)
	cursor = yield tx.execute(query=sql, params=params)
	data = cursor.fetchall()
	start_week, month_range = calendar.monthrange(year, month)
	res = {}
	for row in data:
		params = {}
		day = row[0]
		i = 1
		for col in boiler_room_report_cols:
			params[col] = row[i]
			i += 1
		res[day] = params
	return res

##
# Get a user by the specified email.
# @param tx    Current transaction.
# @param cols  String with columns separated by commas: 'id, name, ...'.
# @param email Email of the user.
#
# @retval Tuple with specified columns or the empty tuple.
#
@tornado.gen.coroutine
def get_user_by_email(tx, cols, email):
	sql = "SELECT {} FROM users WHERE email = %s".format(cols)
	params = (email)
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchone()

##
# Insert the user to the users table.
#
@tornado.gen.coroutine
def insert_user(tx, email, pass_hash):
	sql = "INSERT INTO users(email, pass_hash) VALUES (%s, %s)"
	params = (email, pass_hash)
	yield tx.execute(query=sql, params=params)

##
# Get all users.
# @param tx    Current transaction.
# @param cols  String with columns separated by commas: 'name, email, ...'.
#
# @retval 
#
@tornado.gen.coroutine
def get_all_users(tx, cols):
	sql = "SELECT {} FROM users".format(cols)
	cursor = yield tx.execute(query=sql)

	users = []
	next_row = cursor.fetchone()
	while next_row:
		users.append((next_row[0], next_row[1], next_row[2]))
		next_row = cursor.fetchone()

	return users

##
# Insert a user to database
#
@tornado.gen.coroutine
def insert_full_user(tx, src):
	sql = "INSERT INTO users(email, password, salt, name, rights) "\
		"VALUES (%s, %s, %s, %s, %s)"
	params = (get_safe_val(src, 'email'),\
			  get_safe_val(src, 'password'),\
			  get_safe_val(src, 'salt'),\
			  get_safe_val(src, 'name'),\
			  get_safe_val(src, 'rights'),)
	yield tx.execute(query=sql, params=params)

##
# Delete a user by id
#
@tornado.gen.coroutine
def delete_user_by_id(tx, id):
	sql = "DELETE FROM users WHERE id = %s"
	params = (id, )
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchone()

##
# Get a user by id
#
@tornado.gen.coroutine
def get_user_by_id(tx, cols, id):
	sql = "SELECT {} FROM users WHERE id = %s".format(cols)
	params = (id, )
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchone()

##
# Update a user
#
@tornado.gen.coroutine
def update_user_by_id(tx, cols, id):
	sql = "UPDATE users SET "
	first = True
	for c in cols:
		if not first:
			sql += ","
		first = False
		sql += (c + "='" + str(cols[c]) + "'")
	sql += " WHERE id = %s"
	params = (id, )
	yield tx.execute(query=sql, params=params)
