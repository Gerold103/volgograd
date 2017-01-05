#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from zipfile import BadZipFile
import logging
logger = logging.getLogger('volgograd_log.xml_parser')

import xlrd
from openpyxl import load_workbook
from openpyxl.reader.excel import load_workbook, InvalidFileException
from openpyxl.workbook import Workbook

def get_cell(a, row, col):
	s = a.cell(row=row, column=col).value
	if s is None or s == '':
		return None
	return str(s).strip()

def get_float(a, row, col):
	val = get_cell(a, row, col)
	if val is None or val == '':
		return None
	val = val.replace(',', '.')
	if val == '-':
		return None
	return float(val)

def get_int(a, row, col):
	val = get_cell(a, row, col)
	if val is None or val == '-' or val == '':
		return None
	return int(float(val))

def validate_forecast_table_header(a, result):
	# Check begin of the table
	assert(get_cell(a, 5, 5) == 'котельная')
	assert(get_cell(a, 5, 3) == 'Расчётный темпера-турный график')
	assert(get_cell(a, 5, 7) == 'Р        газа')
	assert(get_cell(a, 5, 8) == 'котлы')
	assert(get_cell(a, 5, 13) == 'Сетевые насосы')
	assert(get_cell(a, 8, 8) == 'всего')
	assert(get_cell(a, 8, 9) == 'в работе')
	assert(get_cell(a, 9, 9) == 'котлов')
	assert(get_cell(a, 9, 10) == 'горелок')
	assert(get_cell(a, 8, 11) == 'резерв')
	assert(get_cell(a, 8, 12) == 'ремонт')
	assert(get_cell(a, 5, 13) == 'Сетевые насосы')
	assert(get_cell(a, 8, 13) == 'в работе')
	assert(get_cell(a, 8, 14) == 'резерв')
	assert(get_cell(a, 8, 15) == 'ремонт')
	assert(get_cell(a, 5, 16) == 'Среднесуточная температура')
	assert(get_cell(a, 6, 16) == 'заданная')
	assert(get_cell(a, 6, 18) == 'фактическая')
	assert(get_cell(a, 7, 16) == '(tн)срзад =')
	assert(get_cell(a, 8, 16) == 'T1срзад')
	assert(get_cell(a, 8, 17) == 'T2срзад')
	assert(get_cell(a, 8, 18) == 'T1срф')
	assert(get_cell(a, 8, 19) == 'T2срф')
	assert(get_cell(a, 5, 20) == 'Температура (ночь)')
	assert(get_cell(a, 6, 20) == 'заданная')
	assert(get_cell(a, 6, 22) == 'фактическая          на 6-00 ч.')
	assert(get_cell(a, 7, 20) == '(tн)нзад =')
	assert(get_float(a, 7, 21) == result['expected_temp_air_night'])
	assert(get_cell(a, 8, 20) == 'T1зад')
	assert(get_cell(a, 8, 21) == 'T2зад')
	assert(get_cell(a, 8, 22) == 'T1ф')
	assert(get_cell(a, 8, 23) == 'T2ф')
	assert(get_cell(a, 5, 24) == 'давление в сети')
	assert(get_cell(a, 8, 24) == 'Р1')
	assert(get_cell(a, 8, 25) == 'Р2')
	assert(get_cell(a, 5, 26) == 'расход сетевой       воды (т/час)')
	assert(get_cell(a, 8, 26) == 'расч.         Gр')
	assert(get_cell(a, 8, 27) == 'факт.         Gф')
	assert(get_cell(a, 5, 28) == 'расход подпиточной воды')
	assert(get_cell(a, 8, 28) == 'расч.    Gпр  (т\\час)')
	assert(get_cell(a, 8, 29) == 'фактический')
	assert(get_cell(a, 9, 29) == 'на             6-00 (т\\час)')
	assert(get_cell(a, 9, 30) == 'за сутки (т\\сут)')
	assert(get_cell(a, 9, 31) == 'всего с начала месяца, т')
	assert(get_cell(a, 5, 34) == 'жёсткость (мкг-экв\\л)')
	assert(get_cell(a, 5, 35) == 'прозрач-ность, см')
	assert(get_cell(a, 8, 34) == 'Ж')

def parse_xls_with_forecast(a):
	result = {}

	assert('Сводные данные о работе котельных' in get_cell(a, 3, 2))
	#
	# Form the forecast on the next day
	#

	assert(a.cell(row=1, column=2).value.strip() == 'Прогноз на')
	result['forecast_date']      = get_cell(a, 1, 3)
	result['forecast_weather']   = get_cell(a, 2, 2)
	result['forecast_direction'] = get_cell(a, 2, 3)
	result['forecast_speed']     = get_cell(a, 2, 4)

	assert(get_cell(a, 1, 6) == 'Т день')
	assert(get_cell(a, 2, 6) == 'Т ночь')
	result['forecast_temp_day_from']   = get_float(a, 1, 7)
	result['forecast_temp_day_to']     = get_float(a, 1, 8)
	result['forecast_temp_night_from'] = get_float(a, 2, 7)
	result['forecast_temp_night_to']   = get_float(a, 2, 8)
	result['date'] = get_cell(a, 3, 27)

	#
	# Average temperature 
	#

	assert(get_cell(a, 1, 27) == 'tср.возд. за')
	assert(get_cell(a, 2, 27) == 'tср. воды. за')

	# Dates of temperatures must be equal
	
	assert(get_cell(a, 2, 29) == get_cell(a, 1, 29))
	assert(get_cell(a, 2, 29) == result['date'])
	result['temp_average_air']   = get_float(a, 1, 31)
	result['temp_average_water'] = get_float(a, 2, 31)

	assert(get_cell(a, 4, 3) == 'Задаваемая температура наружного воздуха:')
	assert(get_cell(a, 4, 15) == 'оС')
	result['expected_temp_air_day']     = get_float(a, 4, 14)
	result['expected_temp_air_night']   = get_float(a, 4, 20)
	result['expected_temp_air_all_day'] = get_float(a, 7, 17)

	#
	# Bolier rooms
	#

	assert(get_cell(a, 5, 2) == 'РАЙОН')
	i = 12
	end = a.max_row - 2
	ditricts = []

	validate_forecast_table_header(a, result)

	fields = ['boilers_all', 'boilers_in_use',
		  'torchs_in_use', 'boilers_reserve', 'boilers_in_repair',
		  'net_pumps_in_work', 'net_pumps_reserve',
		  'net_pumps_in_repair', 'all_day_expected_temp1',
		  'all_day_expected_temp2', 'all_day_real_temp1',
		  'all_day_real_temp2', 'all_night_expected_temp1',
		  'all_night_expected_temp2', 'all_night_real_temp1',
		  'all_night_real_temp2', 'net_pressure1', 'net_pressure2',
		  'net_water_consum_expected_ph', 'net_water_consum_real_ph',
		  'make_up_water_consum_expected_ph',
		  'make_up_water_consum_real_ph',
		  'make_up_water_consum_real_pd',
		  'make_up_water_consum_real_pm']

	while i <= end:
	
		# read all boiler rooms of one district

		district = get_cell(a, i, 2)
		assert(len(district) > 0)
		cur_district = None
		boiler_rooms = []
		while not cur_district and i <= end:

			# read one boiler room

			boiler_room = {}
			if (len(boiler_rooms) == 0):
				boiler_room['district'] = district
			else:
				boiler_room['district'] = None
			boiler_room['T1']   = get_float(a, i, 3)
			boiler_room['T2']   = get_float(a, i, 4)
			boiler_room['name'] = get_cell(a, i, 5)
			boiler_room['gas_pressure'] = get_float(a, i, 7)
			k = 0
			for j in range(8, 16):
				boiler_room[fields[k]] = get_int(a, i, j)
				k += 1
			for j in range(16, 32):
				boiler_room[fields[k]] = get_float(a, i, j)
				k += 1
			hardness = get_cell(a, i, 34)
			if 'компл' in hardness:
				hardness = None
			else:
				hardness = get_float(a, i, 34)
			transparency = get_cell(a, i, 35)
			if transparency == 'компл':
				transparency = None
			else:
				transparency = get_float(a, i, 35)
			boiler_room['hardness']     = hardness
			boiler_room['transparency'] = transparency

			boiler_rooms.append(boiler_room)

			i += 1
			cur_district = get_cell(a, i, 2)
		ditricts.append({'name': district, 'rooms': boiler_rooms})

	result['districts'] = ditricts
	return result

def parse_xls_without_forecast(a):
	result = {}

	assert('Сводные данные о работе котельных' in get_cell(a, 1, 2))
	result['date'] = get_cell(a, 1, 18)

	#
	# Bolier rooms
	#

	assert(get_cell(a, 2, 2) == 'РАЙОН')
	i = 6
	ditricts = []

	fields = ['boilers_all', 'boilers_in_use',
		  'torchs_in_use', 'boilers_reserve', 'boilers_in_repair',
		  'all_day_real_temp1', 'all_day_real_temp2',
		  'all_night_real_temp1', 'all_night_real_temp2',
		  'net_pressure1', 'net_pressure2',
		  'net_water_consum_expected_ph', 'net_water_consum_real_ph',
		  'make_up_water_consum_expected_ph',
		  'make_up_water_consum_real_ph',
		  'make_up_water_consum_real_pd',
		  'make_up_water_consum_real_pm']

	end = False
	while not end:
	
		# read all boiler rooms of one district

		district = get_cell(a, i, 2)
		assert(len(district) > 0)
		cur_district = None
		boiler_rooms = []
		while cur_district is None:
			if not get_cell(a, i, 3):
				end = True
				break
			# read one boiler room

			boiler_room = {}
			if (len(boiler_rooms) == 0):
				boiler_room['district'] = district
			else:
				boiler_room['district'] = None
			boiler_room['T1']   = get_float(a, i, 3)
			boiler_room['T2']   = get_float(a, i, 4)
			boiler_room['name'] = get_cell(a, i, 5)
			boiler_room['gas_pressure'] = get_float(a, i, 6)
			k = 0
			for j in range(7, 12):
				boiler_room[fields[k]] = get_int(a, i, j)
				k += 1
			for j in range(12, 24):
				boiler_room[fields[k]] = get_float(a, i, j)
				k += 1
			hardness = get_cell(a, i, 27)
			if hardness == 'компл':
				hardness = None
			else:
				hardness = get_float(a, i, 27)
			transparency = get_cell(a, i, 28)
			if transparency == 'компл':
				transparency = None
			else:
				transparency = get_float(a, i, 28)
			boiler_room['hardness']     = hardness
			boiler_room['transparency'] = transparency

			boiler_rooms.append(boiler_room)

			i += 1
			cur_district = get_cell(a, i, 2)
		ditricts.append({'name': district, 'rooms': boiler_rooms})

	result['districts'] = ditricts
	return result

def open_xls_as_xlsx(filename):
    # First open using xlrd.
    book = xlrd.open_workbook(file_contents=filename.getvalue())
    index = 0
    nrows, ncols = 0, 0
    while nrows * ncols == 0:
        sheet = book.sheet_by_index(index)
        nrows = sheet.nrows
        ncols = sheet.ncols
        index += 1

    # prepare a xlsx sheet
    book1 = Workbook()
    sheet1 = book1.get_active_sheet()

    for row in range(0, nrows):
        for col in range(0, ncols):
            sheet1.cell(row=row+1, column=col+1).value = sheet.cell_value(row, col)

    return book1

def parse_xls(file):
	wb = None
	try:
		wb = load_workbook(filename=file, data_only=True)
	except BadZipFile:
		logger.warning("Can't open xls, try to use xlrd...")
		wb = open_xls_as_xlsx(file)
		logger.warning('Success')
	a = wb.active
	if get_cell(a, 1, 2) == 'Сводные данные о работе котельных  МУП '\
				'"ВКХ" на':
		return parse_xls_without_forecast(a)
	else:
		return parse_xls_with_forecast(a);
