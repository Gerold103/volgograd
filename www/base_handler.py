#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

import tornado
import tornado.web

from constants import *

##
# Base class for users authentication and error pages rendering.
#
class BaseHandler(tornado.web.RequestHandler):
	##
	# Redefine render method to add rights constants.
	#
	def render(self, *args, **kwargs):
		return super(BaseHandler, self).render(*args, **kwargs,
						       **rights_dictionary)
	##
	# User cookies are: user_id, rights. This methods return user_id.
	#
	def get_current_user(self):
		user_id = self.get_secure_cookie('user_id', None)
		if not user_id:
			return None
		user = {'user_id': int(user_id)}
		user['rights'] = int(self.get_secure_cookie('rights'))
		user['user_name'] = self.get_secure_cookie('user_name', None)
		if user['user_name']:
			user['user_name'] = user['user_name'].decode('utf-8')
		return user
	
	##
	# Render an error page with specified an error header and a message.
	#
	def render_error(self, e_hdr, e_msg=None, template='error_page.html',
			 **kwargs):
		if e_msg == None:
			if e_hdr in ERR_MESSAGES:
				e_msg = ERR_MESSAGES[e_hdr]
			else:
				e_msg = ''
		self.render(template, error_header=e_hdr,
			    error_msg=e_msg, **kwargs)

	##
	# Render the answer in the JSON format with the specified
	# response data.
	#
	def render_json(self, data):
		self.write(json.dumps({ 'response': data }))

	##
	# Render the error information in the JSON format with the
	# specified error message.
	#
	def render_json_error(self, msg):
		self.write(json.dumps({ 'error': msg }))

	##
	# Render an error page, flush it to the user and then rollback
	# transaction. Such actions sequence allows the user to avoid waiting
	# for rollback.
	#
	@tornado.gen.coroutine
	def rollback_error(self, tx, e_hdr, e_msg=None):
		self.render_error(e_hdr=e_hdr, e_msg=e_msg)
		try:
			yield self.flush()
		except:
			pass
		if tx:
			yield tx.rollback()

	##
	# Check that the current use can execute specified actions.
	# @sa CAN_... flags.
	# @param rights Bitmask with actions flags.
	# @retval true  The user can execute all specified actions.
	# @retval false The user can't execute one or more of the specified
	#               actions.
	#
	@tornado.web.authenticated
	def check_rights(self, rights, render=True):
		user_rights = int(self.get_secure_cookie('rights'))
		if not (rights & user_rights):
			if render:
				self.render_error(e_hdr=ERR_ACCESS,
						  e_msg='Доступ запрещен')
			return False
		return True

##
# Decorator to check rights mask.
# @sa constants.py
#
def need_rights(mask, render=True):
	def need_rights_impl(method):
		def wrapper(self, *args, **kwargs):
			if not self.check_rights(mask, render=render):
				return
			return method(self, *args, **kwargs)
		return wrapper
	return need_rights_impl
