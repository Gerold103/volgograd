#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
from datetime import date as libdate

import tornado
import tornado.gen
from constants import date_format, AccessError

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
# {
# 	boiler_id: {
# 		parameter: {
# 			day1: val1,
# 			day2: val2,
# 			...
# 		},
# 		...
# 	},
# 	...
# }
#
@tornado.gen.coroutine
def get_boilers_month_values(tx, year, month, columns):
	sql = 'SELECT boiler_room_id, DAY(date), {} FROM boiler_room_reports JOIN reports'\
	      ' ON(report_id = reports.id) WHERE '\
	      'YEAR(date) = %s AND MONTH(date) = %s'.format(",".join(columns))
	params = (year, month)
	cursor = yield tx.execute(query=sql, params=params)
	boilers = {}
	row = cursor.fetchone()
	while row:
		boiler_id = row[0]
		day = row[1]
		parameters = {}
		if boiler_id in boilers:
			parameters = boilers[boiler_id]
		else:
			boilers[boiler_id] = parameters
		for i in range(2, len(columns) + 2):
			val = row[i]
			col = columns[i - 2]
			values = {}
			if col in parameters:
				values = parameters[col]
			else:
				parameters[col] = values
			values[day] = val
		row = cursor.fetchone()
	return boilers

##
# Returns the array with values:
# { 'title': title_of_a_district, 'rooms':
#   [
#     {'id': boiler_id, 'name': boiler_name},
#     ...
#   ]
# }
#
@tornado.gen.coroutine
def get_districts_with_boilers(tx):
	sql = "SELECT districts.name, boiler_rooms.id, boiler_rooms.name FROM "\
	      "districts JOIN boiler_rooms "\
	      "ON (districts.id = boiler_rooms.district_id)"
	cursor = yield tx.execute(sql)
	row = cursor.fetchone()
	districts = {}
	while row:
		district = row[0]
		id = row[1]
		name = row[2]
		boilers = []
		if district in districts:
			boilers = districts[district]
		else:
			districts[district] = boilers
		boilers.append({ 'id': id, 'name': name })
		row = cursor.fetchone()
	result = []
	for district, boilers in sorted(districts.items(), key=lambda x: x[0]):
		result.append({ 'title': district, 'rooms': boilers })
	return result

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
	      "STR_TO_DATE(%s, %s)".format(','.join(cols))
	params = (date, date_format)
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

##
# Get identifiers and titles of all boiler rooms.
#
@tornado.gen.coroutine
def get_boiler_room_ids_and_titles(tx):
	sql = "SELECT boiler_rooms.id, boiler_rooms.name, districts.name "\
	      "from boiler_rooms JOIN districts ON(districts.id = district_id)";
	cursor = yield tx.execute(query=sql)
	tuples = cursor.fetchall()
	res = []
	for t in tuples:
		res.append({'id': t[0], 'title': "%s - %s" % (t[2], t[1])})
	return res

##
# Get parameters of the specified boiler room alog the year.
# @param tx   Current transaction.
# @param id   Identifier of the boiler room.
# @param year Year along which need to gather parameters.
# @param cols List of the table columns needed to fetch.
#
# @retval Dictionary of the following format (days are numbered
#         from start of the year):
# {
# 	parameter: {
# 		day1: val1,
# 		day2: val2,
# 		...
# 	},
# 	...
# }
#
@tornado.gen.coroutine
def get_boiler_year_report(tx, id, year, cols):
	sql = "SELECT date, {} FROM reports JOIN boiler_room_reports "\
	      "ON(reports.id = report_id) WHERE YEAR(date) = %s AND "\
	      "boiler_room_id = %s"\
	      .format(",".join(cols))
	params = (year, id)
	res = {}
	#
	# Validate columns and prepare the result dictionary.
	#
	for col in cols:
		if col not in boiler_room_report_cols:
			raise AccessError('[{}]'.format(','.join(cols)))
		res[col] = {}
	cursor = yield tx.execute(query=sql, params=params)
	row = cursor.fetchone()
	while row:
		day = row[0].timetuple().tm_yday
		for i, col in enumerate(cols):
			res[col][day] = row[1 + i]
		row = cursor.fetchone()
	return res

##
# Get air temperature of all days in the specified year.
# @param year Year in which need to get air temperatures.
# @retval Dictionary with keys as day numbers and values as
#         temperatures.
#
@tornado.gen.coroutine
def get_year_temperature(tx, year):
	sql = "SELECT date, temp_average_air FROM reports WHERE YEAR(date) = %s"
	params = (year, )
	cursor = yield tx.execute(query=sql, params=params)
	data = cursor.fetchall()
	res = {}
	for row in data:
		day = row[0].timetuple().tm_yday
		res[day] = row[1]
	return res

##
# Delete report by the specified date.
#
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
	sql = "SELECT {} FROM districts WHERE name = %s".format(','.join(cols))
	params = (name, )
	cursor = yield tx.execute(query=sql, params=params)
	return cursor.fetchone()

##
# Insert the new district to the districts table.
#
@tornado.gen.coroutine
def insert_district(tx, name):
	sql = "INSERT INTO districts(name) VALUES (%s)"
	params = (name, )
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
	      "name = %s".format(','.join(cols))
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
# Insert a new user into the database.
#
@tornado.gen.coroutine
def insert_user(tx, email, password, salt, name, rights):
	sql = "INSERT INTO users VALUES (NULL, %s, %s, %s, %s, %s)"
	params = (email, password, salt, name, rights)
	yield tx.execute(query=sql, params=params)

##
# Update the user by his identifier.
#
@tornado.gen.coroutine
def update_user(tx, id, email, password, salt, name, rights):
	sql = "UPDATE users SET email = %s, name = %s, rights = %s"
	params = [email, name, rights]
	# Password update is optional.
	if password and salt:
		params.extend([password, salt])
		sql += ", password = %s, salt = %s"
	sql += " WHERE id = %s"
	params.append(id)
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
	return libdate(year=year, month=month, day=day).strftime(date_format)

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
	assert(room_id)
	assert(report_id)
	params = [room_id, report_id]
	values = ['%s', '%s']
	for i in range(len(boiler_room_report_cols)):
		values.append('%s')
	values = ','.join(values)
	sql = 'INSERT INTO boiler_room_reports VALUES (NULL, {})'.format(values)
	for col in boiler_room_report_cols:
		params.append(get_safe_val(src, col))
	yield tx.execute(query=sql, params=params)

##
# Insert a report to the reports table. If some columns absense then replace
# them with NULL values.
#
@tornado.gen.coroutine
def insert_report(tx, author_id, src):
	sql = 'INSERT INTO reports VALUES (NULL, %s, STR_TO_DATE(%s, %s), %s, '\
	      '%s, %s, %s, %s, STR_TO_DATE(%s, %s), %s, %s, %s, %s, %s, %s, %s)'
	params = (author_id, get_safe_val(src, 'date'), date_format,
		  get_safe_val(src, 'temp_average_air'),
		  get_safe_val(src, 'temp_average_water'),
		  get_safe_val(src, 'expected_temp_air_day'),
		  get_safe_val(src, 'expected_temp_air_night'),
		  get_safe_val(src, 'expected_temp_air_all_day'),
		  get_safe_val(src, 'forecast_date'), date_format,
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
	sql = 'SELECT reports.*, users.name FROM reports LEFT JOIN users '\
	      'ON (author_id = users.id) WHERE date = STR_TO_DATE(%s, %s)'
	params = (date, date_format)
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
	result['date'] = report[2]
	result['temp_average_air'] = report[3]
	result['temp_average_water'] = report[4]
	result['expected_temp_air_day'] = report[5]
	result['expected_temp_air_night'] = report[6]
	result['expected_temp_air_all_day'] = report[7]
	result['forecast_date'] = report[8]
	result['forecast_weather'] = report[9]
	result['forecast_direction'] = report[10]
	result['forecast_speed'] = report[11]
	result['forecast_temp_day_from'] = report[12]
	result['forecast_temp_day_to'] = report[13]
	result['forecast_temp_night_from'] = report[14]
	result['forecast_temp_night_to'] = report[15]
	result['author'] = report[16]
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
# Get summary values of all parameters for the specified month
# in all boiler rooms.
# @retval Dictionary with the following format:
# {
# 	parameter: {
# 		day1: sum in all boilers,
# 		day2: sum in all boilers,
# 		...
# 	},
# 	...
# }
#
@tornado.gen.coroutine
def get_sum_reports_by_month(tx, year, month, cols):
	avg_list = list(['SUM({})'.format(col) for col in cols])
	sql = 'SELECT DAY(date), {} FROM reports JOIN boiler_room_reports '\
	      'ON(reports.id = report_id) WHERE MONTH(date) = %s and '\
	      'YEAR(date) = %s GROUP BY date;'.format(",".join(avg_list))
	params = (month, year)
	cursor = yield tx.execute(query=sql, params=params)
	res = {}
	for col in cols:
		res[col] = {}
	row = cursor.fetchone()
	while row:
		day = row[0]
		for i, col in enumerate(cols):
			res[col][day] = row[1 + i]
		row = cursor.fetchone()
	return res

##
# Create the dictionary of column values with keys same as
# requested column names.
# @param tx   Current transaction.
# @param cols List of requested columns.
# @param row  A row from the database.
#
# @retval Dictionary with keys-columns.
#
def process_db_row(tx, cols, row):
	assert(row)
	res = {}
	for i, col in enumerate(cols):
		res[col] = row[i]
	return res

##
# Get a user by the specified email.
# @param tx    Current transaction.
# @param cols  List of columns to fetch.
# @param email Email of the user.
#
# @retval Dictionary with keys same as requested columns, or None,
#         if an user was not found.
#
@tornado.gen.coroutine
def get_user_by_email(tx, cols, email):
	sql = "SELECT {} FROM users WHERE email = %s".format(','.join(cols))
	params = (email, )
	cursor = yield tx.execute(query=sql, params=params)
	row = cursor.fetchone()
	if not row:
		return None
	return process_db_row(tx, cols, row)

##
# Get range of users with the specified offset and limit.
# @param tx     Current transaction.
# @param limit  Limit of users to fetch.
# @param Offset Offset from the begin of all users list, ordered
#               by name.
# @param cols   List of columns to fetch.
#
# @retval List with the following format: [ { column values dictionary }, ... ].
#
@tornado.gen.coroutine
def get_users_range(tx, limit, offset, cols):
	sql = 'SELECT {} FROM users ORDER BY name IS NULL, name ASC, email '\
	      'LIMIT %s OFFSET %s'.format(','.join(cols))
	params = (limit, offset)
	cursor = yield tx.execute(query=sql, params=params)
	row = cursor.fetchone()
	res = []
	while row:
		next = process_db_row(tx, cols, row)
		res.append(next)
		row = cursor.fetchone()
	return res

##
# Delete the user with the specified ID.
#
@tornado.gen.coroutine
def delete_user_by_id(tx, id):
	sql = 'DELETE FROM users WHERE id = %s'
	params = (id, )
	cursor = yield tx.execute(query=sql, params=params)

##
# Switch the active database on the test database. Then clear it
# to start testing from the 'empty paper'.
#
@tornado.gen.coroutine
def prepare_tests(tx, old_db_name, test_db_name):
	sql = "DROP DATABASE IF EXISTS {}; CREATE DATABASE {}; USE {}; "\
	      "CREATE TABLE reports LIKE {}.reports; "\
	      "CREATE TABLE districts LIKE {}.districts; "\
	      "CREATE TABLE boiler_rooms LIKE {}.boiler_rooms; "\
	      "CREATE TABLE boiler_room_reports LIKE {}.boiler_room_reports; "\
	      "CREATE TABLE users LIKE {}.users; "\
	      .format(test_db_name, test_db_name, test_db_name, old_db_name,
		      old_db_name, old_db_name, old_db_name, old_db_name)
	yield tx.execute(sql)
