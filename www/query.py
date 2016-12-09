#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tornado
import tornado.gen

@tornado.gen.coroutine
def get_report_by_date(tx, date, cols):
	sql = "SELECT {} FROM reports WHERE date = "\
	      "STR_TO_DATE('{}', '%d.%m.%Y')".format(cols, date)
	cursor = yield tx.execute(sql)
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

@tornado.gen.coroutine
def insert_boiler_room(tx, dist_id, name):
	sql = "INSERT INTO boiler_rooms(district_id, name) "\
	      "VALUES ({}, '{}')".format(dist_id, name)
	yield tx.execute(sql)

def get_sql_val(src, name):
	if not name in src:
		return 'NULL'
	val = src[name]
	if val is None:
		return 'NULL'
	else:
		return val

##
# Get a value from iterable object by name, or None, if the object doesn't
# contain the name.
#
def get_safe_val(src, name):
	print(name)
	if not name in src:
		return None
	return src[name]

@tornado.gen.coroutine
def insert_boiler_room_report(tx, src, room_id, report_id):
	sql = "INSERT INTO boiler_room_reports VALUES (NULL, {}, {}, {}, {}, {}, "\
		  "{}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {},"\
		  " {}, {}, {}, {}, {}, {}, {}, {}, {})"\
		  .format(room_id, report_id, get_sql_val(src, 'T1'),
		  		  get_sql_val(src, 'T2'), get_sql_val(src, 'gas_pressure'),
		  		  get_sql_val(src, 'boilers_all'),
		  		  get_sql_val(src, 'boilers_in_use'),
		  		  get_sql_val(src, 'torchs_in_use'),
		  		  get_sql_val(src, 'boilers_reserve'),
		  		  get_sql_val(src, 'boilers_in_repair'),
		  		  get_sql_val(src, 'net_pumps_in_work'),
		  		  get_sql_val(src, 'net_pumps_reserve'),
		  		  get_sql_val(src, 'net_pumps_in_repair'),
		  		  get_sql_val(src, 'all_day_expected_temp1'),
		  		  get_sql_val(src, 'all_day_expected_temp2'),
		  		  get_sql_val(src, 'all_day_real_temp1'),
		  		  get_sql_val(src, 'all_day_real_temp2'),
		  		  get_sql_val(src, 'all_night_expected_temp1'),
		  		  get_sql_val(src, 'all_night_expected_temp2'),
		  		  get_sql_val(src, 'all_night_real_temp1'),
		  		  get_sql_val(src, 'all_night_real_temp2'),
		  		  get_sql_val(src, 'net_pressure1'),
		  		  get_sql_val(src, 'net_pressure2'),
		  		  get_sql_val(src, 'net_water_consum_expected_ph'),
		  		  get_sql_val(src, 'net_water_consum_real_ph'),
		  		  get_sql_val(src, 'make_up_water_consum_expected_ph'),
		  		  get_sql_val(src, 'make_up_water_consum_real_ph'),
		  		  get_sql_val(src, 'make_up_water_consum_real_pd'),
		  		  get_sql_val(src, 'make_up_water_consum_real_pm'),
		  		  get_sql_val(src, 'hardness'),
		  		  get_sql_val(src, 'transparency'))
	yield tx.execute(sql)

##
# Insert a report to the reports table. If some columns absense then replace
# them with NULL values.
#
@tornado.gen.coroutine
def insert_report(tx, src):
	sql = "INSERT INTO reports VALUES (NULL, STR_TO_DATE(%s, %s),"\
		  " %s, %s, %s, %s, %s, STR_TO_DATE(%s, %s), %s, %s, "\
		  "%s, %s, %s, %s, %s)"
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

@tornado.gen.coroutine
def get_full_report_by_date(tx, date):
	sql = "SELECT * FROM reports WHERE date = STR_TO_DATE('{}', "\
		  "'%Y-%m-%d')".format(date)
	cursor = yield tx.execute(sql)
	report = cursor.fetchone()
	if not report:
		return None
	rep_id = report[0]
	sql = "SELECT districts.name, boiler_rooms.name, T1, T2, gas_pressure, "\
		  "boilers_all, boilers_in_use, torchs_in_use, boilers_reserve, "\
		  "boilers_in_repair, net_pumps_in_work, net_pumps_reserve, "\
		  "net_pumps_in_repair, all_day_expected_temp1, "\
		  "all_day_expected_temp2, all_day_real_temp1, all_day_real_temp2, "\
		  "all_night_expected_temp1, all_night_expected_temp2, "\
		  "all_night_real_temp1, all_night_real_temp2, net_pressure1, "\
		  "net_pressure2, net_water_consum_expected_ph, "\
		  "net_water_consum_real_ph, make_up_water_consum_expected_ph, "\
		  "make_up_water_consum_real_ph, make_up_water_consum_real_pd, "\
		  "make_up_water_consum_real_pm, hardness, transparency "\
		  "FROM districts JOIN boiler_rooms "\
		  "ON(districts.id = boiler_rooms.district_id) JOIN "\
		  "boiler_room_reports ON (boiler_room_reports.boiler_room_id = "\
		  "boiler_rooms.id AND boiler_room_reports.report_id = {})"\
		  .format(rep_id)
	cursor = yield tx.execute(sql)
	districts = {}
	next_row = cursor.fetchone()
	while next_row:
		dist_name = next_row[0]
		if dist_name not in districts:
			districts[dist_name] = []
		rooms = districts[dist_name]
		rooms.append({'name': next_row[1], 'T1': next_row[2], 'T2': next_row[3],
					  'gas_pressure': next_row[4], 'boilers_all': next_row[5],
					  'boilers_in_use': next_row[6],
					  'torchs_in_use': next_row[7],
					  'boilers_reserve': next_row[8],
					  'boilers_in_repair': next_row[9],
					  'net_pumps_in_work': next_row[10],
					  'net_pumps_reserve': next_row[11],
					  'net_pumps_in_repair': next_row[12],
					  'all_day_expected_temp1': next_row[13],
					  'all_day_expected_temp2': next_row[14],
					  'all_day_real_temp1': next_row[15],
					  'all_day_real_temp2': next_row[16],
					  'all_night_expected_temp1': next_row[17],
					  'all_night_expected_temp2': next_row[18],
					  'all_night_real_temp1': next_row[19],
					  'all_night_real_temp2': next_row[20],
					  'net_pressure1': next_row[21],
					  'net_pressure2': next_row[22],
					  'net_water_consum_expected_ph': next_row[23],
					  'net_water_consum_real_ph': next_row[24],
					  'make_up_water_consum_expected_ph': next_row[25],
					  'make_up_water_consum_real_ph': next_row[26],
					  'make_up_water_consum_real_pd': next_row[27],
					  'make_up_water_consum_real_pm': next_row[28],
					  'hardness': next_row[29],
					  'transparency': next_row[30]
					 })
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
	for dist, rooms in districts.items():
		district = {'name': dist}
		rooms[0]['district'] = dist
		for i in range(1, len(rooms)):
			rooms[i]['district'] = None
		district['rooms'] = rooms
		result['districts'].append(district)
	return result

@tornado.gen.coroutine
def get_user_by_email(tx, cols, email):
	sql = "SELECT {} FROM users WHERE email = '{}'".format(cols, email)
	cursor = yield tx.execute(sql)
	return cursor.fetchone()

@tornado.gen.coroutine
def insert_user(tx, email, pass_hash):
	sql = "INSERT INTO users(email, pass_hash) "\
		  "VALUES ('{}', '{}')".format(email, pass_hash)
	yield tx.execute(sql)
