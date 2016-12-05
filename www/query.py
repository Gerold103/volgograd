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

@tornado.gen.coroutine
def get_district_by_name(tx, name, cols):
	sql = "SELECT {} FROM districts WHERE name = '{}'".format(cols, name)
	cursor = yield tx.execute(sql)
	return cursor.fetchone()

@tornado.gen.coroutine
def insert_district(tx, name):
	sql = "INSERT INTO districts(name) VALUES ('{}')".format(name)
	yield tx.execute(sql)

@tornado.gen.coroutine
def get_boiler_room_by_dist_and_name(tx, cols, dist_id, name):
	sql = "SELECT {} FROM boiler_rooms WHERE district_id = {} AND "\
	      "name = '{}'".format(cols, dist_id, name)
	cursor = yield tx.execute(sql)
	return cursor.fetchone()

@tornado.gen.coroutine
def insert_boiler_room(tx, dist_id, name):
	sql = "INSERT INTO boiler_rooms(district_id, name) "\
	      "VALUES ({}, '{}')".format(dist_id, name)
	yield tx.execute(sql)

def get_sql_val(val):
	if not val:
		return 'NULL'
	else:
		return val

@tornado.gen.coroutine
def insert_boiler_room_report(tx, src, room_id, report_id):
	sql = "INSERT INTO boiler_room_reports VALUES (NULL, {}, {}, {}, {}, {}, "\
		  "{}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {},"\
		  " {}, {}, {}, {}, {}, {}, {}, {}, {})"\
		  .format(room_id, report_id, get_sql_val(src['T1']),
		  		  get_sql_val(src['T2']), get_sql_val(src['gas_pressure']),
		  		  get_sql_val(src['boilers_all']),
		  		  get_sql_val(src['boilers_in_use']),
		  		  get_sql_val(src['torchs_in_use']),
		  		  get_sql_val(src['boilers_reserve']),
		  		  get_sql_val(src['boilers_in_repair']),
		  		  get_sql_val(src['net_pumps_in_work']),
		  		  get_sql_val(src['net_pumps_reserve']),
		  		  get_sql_val(src['net_pumps_in_repair']),
		  		  get_sql_val(src['all_day_expected_temp1']),
		  		  get_sql_val(src['all_day_expected_temp2']),
		  		  get_sql_val(src['all_day_real_temp1']),
		  		  get_sql_val(src['all_day_real_temp2']),
		  		  get_sql_val(src['all_night_expected_temp1']),
		  		  get_sql_val(src['all_night_expected_temp2']),
		  		  get_sql_val(src['all_night_real_temp1']),
		  		  get_sql_val(src['all_night_real_temp2']),
		  		  get_sql_val(src['net_pressure1']),
		  		  get_sql_val(src['net_pressure2']),
		  		  get_sql_val(src['net_water_consum_expected_ph']),
		  		  get_sql_val(src['net_water_consum_real_ph']),
		  		  get_sql_val(src['make_up_water_consum_expected_ph']),
		  		  get_sql_val(src['make_up_water_consum_real_ph']),
		  		  get_sql_val(src['make_up_water_consum_real_pd']),
		  		  get_sql_val(src['make_up_water_consum_real_pm']),
		  		  get_sql_val(src['hardness']),
		  		  get_sql_val(src['transparency']))
	yield tx.execute(sql)

@tornado.gen.coroutine
def insert_report(tx, data):
	sql = "INSERT INTO reports VALUES (NULL, STR_TO_DATE('{}', '%d.%m.%Y'),"\
		  " {}, {}, {}, {}, {}, STR_TO_DATE('{}', '%d.%m.%Y'), '{}', '{}', "\
		  "'{}', {}, {}, {}, {})"\
		  .format(data['date'], data['temp_average_air'],
		  		  data['temp_average_water'], data['expected_temp_air_day'],
	      	      data['expected_temp_air_night'],
	      	      data['expected_temp_air_all_day'], data['forecast_date'],
	      	      data['forecast_weather'], data['forecast_direction'],
	      	      data['forecast_speed'], data['forecast_temp_day_from'],
	      	      data['forecast_temp_day_to'],
	      	      data['forecast_temp_night_from'],
	      	      data['forecast_temp_night_to'])
	yield tx.execute(sql)

@tornado.gen.coroutine
def get_full_report_by_date(tx, date):
	sql = "SELECT * FROM reports WHERE date = STR_TO_DATE('{}', "\
		  "'%Y-%m-%d')".format(date)
	print(sql)
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
	print(sql)
	cursor = yield tx.execute(sql)
	print('ok')

