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
ERR_DELETE = 'Ошибка удаления'
ERR_EDIT = 'Ошибка редактирования'

CAN_UPLOAD_REPORTS = 0x01
CAN_SEE_REPORTS = 0x02
CAN_DELETE_REPORTS = 0x04
CAN_SEE_USERS = 0x08
CAN_EDIT_USERS = 0x10

month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май',
	       'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь',
	       'Ноябрь', 'Декабрь']
logger = logging.getLogger('volgograd_log')

permissions = {\
		'can_upload_reports': [CAN_UPLOAD_REPORTS, 'Загрузка отчетов'],\
		'can_see_reports': [CAN_SEE_REPORTS, 'Просмотр отчетов'],\
		'can_delete_reports': [CAN_DELETE_REPORTS, 'Удаление отчетов'],\
		'can_see_users': [CAN_SEE_USERS, 'Просмотр пользователей'],\
		'can_edit_users': [CAN_EDIT_USERS, 'Добавление и редактирование пользователей']}

NAME_PATTERN = '^[A-Za-zА-Яа-яЁё0-9]+(?:[ _-][A-Za-zА-Яа-яЁё0-9]+)*$'
MAX_NAME_LENGTH = 65535

EMAIL_PATTERN = '^[a-zA-Z0-9.!#$%&’*+/=?^_`{|}~-]+@[a-zA-Z0-9-]'\
				'+(?:\.[a-zA-Z0-9-]+)*$'

NUMBER_USERS_IN_PAGE = 8
