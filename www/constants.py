#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

DUPLICATE_ERROR = 1062
ERR_INSERT = 'Ошибка вставки данных'
ERR_500    = 'Ошибка сервера'
ERR_ACCESS = 'Ошибка доступа'
ERR_LOGIN  = 'Ошибка входа'
ERR_UPLOAD = 'Ошибка загрузки'
ERR_404    = 'Не найдено'
ERR_PARAMETERS = 'Неверные параметры'

ERR_MESSAGES = {
	ERR_500: 'На сервере произошла ошибка, обратитесь к администратору'
}

CAN_UPLOAD_REPORTS = 0x01
CAN_SEE_REPORTS = 0x02
CAN_DELETE_REPORTS = 0x04
CAN_SEE_USERS = 0x08
CAN_EDIT_USERS = 0x10

CONFIRM_DELETE = 'Вы уверены? Действие нельзя будет отменить.'

##
# If in a html template you need to check the user rights, then
# you can use the following syntax:
#
# 	current_user['rights'] & any_rights_you_need
#
# It is possible since we are passing the rigts dictionary to
# each template in BaseHandler.
#
rights_dictionary = {
	'CAN_UPLOAD_REPORTS': CAN_UPLOAD_REPORTS,
	'CAN_SEE_REPORTS': CAN_SEE_REPORTS,
	'CAN_DELETE_REPORTS': CAN_DELETE_REPORTS,
	'CAN_SEE_USERS': CAN_SEE_USERS,
	'CAN_EDIT_USERS': CAN_EDIT_USERS
}

month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май',
	       'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь',
	       'Ноябрь', 'Декабрь']
logger = logging.getLogger('volgograd_log')

wind_directions = {
	'С': 'Северный',
	'С-З': 'Северо-Западный',
	'С-В': 'Северо-Восточный',
	'Ю': 'Южный',
	'Ю-З': 'Юго-Западный',
	'Ю-В': 'Юго-Восточный',
	'З': 'Западный',
	'В': 'Восточный'
}

date_format = '%d.%m.%Y'

class AccessError(Exception):
	def __init__(self, access_to_what):
		message = 'Доступ к ресурсам {} '\
			  'запрещен'.format(access_to_what)
		super(AccessError, self).__init__(message)
