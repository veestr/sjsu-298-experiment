#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2
import jinja2
import os
import random
import glob
import json
import cgi
import string

import re
import time

from datetime import datetime, tzinfo, timedelta

from google.appengine.ext import db
from google.appengine.api import memcache

JINJA_ENVIRONMENT = jinja2.Environment(
loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
extensions=['jinja2.ext.autoescape'],
autoescape=True)
	
main_template=JINJA_ENVIRONMENT.get_template('index.html')
report_template=JINJA_ENVIRONMENT.get_template('report.html')
account_template=JINJA_ENVIRONMENT.get_template('account.html')
bad_password_template=JINJA_ENVIRONMENT.get_template('bad_password.html')


class Zone(tzinfo):
	"""Define timezone objects."""
	def __init__(self,offset,isdst,name):
		self.offset = offset
		self.isdst = isdst
		self.name = name
		
	def utcoffset(self, dt):
		return timedelta(hours=self.offset) + self.dst(dt)
	
	def dst(self, dt):
		return timedelta(hours=1) if self.isdst else timedelta(0)
	
	def tzname(self,dt):
		return self.name

PST = Zone(-8, True, 'PST')

class Account(db.Model):
	"""Defines accounts in the database."""
	date = db.StringProperty()
	user = db.StringProperty(indexed=True)
	site = db.StringProperty()
	initial_password = db.StringProperty()
	second_password = db.IntegerProperty()
	third_password = db.IntegerProperty()
	pass
	
def get_all_accounts():
	"""Returns all stored accounts as a list of lists."""	
	accounts=[]
	q = Account.all()
	q.order('-date')
	accounts.append(['Date','User','Site','Original Password','5 Min ','1 Week'])
	for account in q:
		entry=[]
		entry.append(account.date)
		entry.append(account.user)
		entry.append(account.site)
		entry.append(account.initial_password)
		entry.append(account.second_password)
		entry.append(account.third_password)
		accounts.append(entry)
	return accounts
	
def get_possible_sites(user):
	"""Returns a set of sites available for the specified user. Each site 
	is represented by an image in the 'images' directory. """
	files=()
	if user.lower().endswith("ur"):
		#ASSERT: the username indicates unrelated condition
		files=(file.replace('images/', '') for file in glob.glob('images/ur_*'))
	elif user.lower().endswith("r"):
		#ASSERT: the username indicates related condition
		files=(file.replace('images/', '') for file in glob.glob('images/r_*'))
	return set(files)
	
def get_registered_sites(user,iteration):
	"""Returns a set of the sites the specified user has registered for given the 
	specific iteration. The sites are considered to be registered if the password is set to a
	value in ragen [0,3] for the specified iteration."""
	sites=set()
	q=Account.all()
	q.filter('user =',user)
	
	if int(iteration)==1:
		#ASSERT: Filter out the site where second_password has not been set
		q.filter('second_password >=', 0).filter('second_password <=', 3)
		
	if int(iteration)==2:
		#ASSERT: Filter out the site where third_password has not been set
		q.filter('third_password >=', 0).filter('third_password <=', 3)

	for account in q:
		sites.add(account.site)
		
	return sites
	
def verify_site(user, site, password):
	"""Verifies whether the password for user is correct for the specific site."""
	q=Account.all()
	q.filter('user =',user)
	q.filter('site =', site)
	result = q.get()
	
	stored_pass = str(result.initial_password)
	return stored_pass == password
	
def get_site_for_user(iteration, user):
	"""Returns the site for the specified user or '' of no such sites can be returned."""
	possible_sites=get_possible_sites(user)
	last_site=memcache.get(user)
	registered_sites=get_registered_sites(user,iteration)
	registered_sites.add(last_site)
	allowed_sites=possible_sites.difference(registered_sites)
	print "Registred sites: %s" % registered_sites
	print "Possible sites: %s" % possible_sites
	print "Allowed sites: %s"  % allowed_sites
	if len(allowed_sites) > 0:
		return random.sample(allowed_sites, 1).pop()
	else:
		return ''
			
class MainHandler(webapp2.RequestHandler):
	def get(self):
		self.response.write(main_template.render())
		memcache.flush_all()
		pass

class ReportHandler(webapp2.RequestHandler):
	def get(self):
		template_values = {
			'accounts' : get_all_accounts(),
		}
		self.response.write(report_template.render(template_values))
		pass
		
class AccountHandler(webapp2.RequestHandler):
	
	def get(self,iteration,attempt):
		user=cgi.escape(self.request.get('user'))
		site=cgi.escape(self.request.get('site'))
		
		#TODO: Handle this more gracefully
		if not user:
			self.redirect('/')
			
		possible_sites=get_possible_sites(user)
		
		if site:
			#ASSESRT: We know for which site to display the account info
			selected_site = site
		else:
			#ASSERT: we need to figure out the site for the user and if
			# such site does not exist, we need to go back to the main screen
			selected_site=get_site_for_user(iteration, user)
			if selected_site=="":
				self.redirect('/')
		
		if int(iteration)==1 or int(iteration)==2:
			# ASSERT: The user is going to verify the site's credentials
			# thus, we need a different verification procedure
			action="/verify"
		elif int(iteration)==0:
			#ASSERT: This is the user's first time, so we need to save the info
			action="/save"
		
		template_values = {
			'selected_site' : cgi.escape(selected_site),
			'user': user,
			'iteration': iteration,
			'attempt': attempt,
			'action': action,
		}
		
		self.response.write(account_template.render(template_values))
		
	pass
	
	def save(self):
		"""Saves the account credentials and redirects to the new account page."""
		user=cgi.escape(self.request.get('user'))
		print "user in save(): %s" % user
		password=cgi.escape(self.request.get('pass1'))
		site=cgi.escape(self.request.get('site'))
		iteration=int(cgi.escape(self.request.get('iteration')))
		self.response.status=201
		account=Account(
			user=user,
			initial_password=password,
			site=site,
			second_password=-1,
			third_password=-1,
			date=datetime.now(PST).strftime('%m/%d/%Y %H:%M:%S %Z')
			)
		account.put()	
		memcache.set(key=user, value=site)
		new_path='/account/0/1/?user='+user
		return self.redirect(new_path)
		
	def verify(self):
		"""Verifies the credentials for the site."""
		user=cgi.escape(self.request.get('user'))
		password=cgi.escape(self.request.get('pass1'))
		site=cgi.escape(self.request.get('site'))
		iteration=int(cgi.escape(self.request.get('iteration')))
		attempt=int(cgi.escape(self.request.get('attempt')))
		is_pass_valid=verify_site(user,site, password)
		
		existing_accounts=db.GqlQuery("SELECT * from Account WHERE user=:1 AND site=:2",user,site).fetch(1)
		account=existing_accounts[0]
		
		if is_pass_valid:
			#ASSERT: The password provided by user for the site is valid
			#Mark the attempt as such and go on to the next site
			if iteration==1:
				account.second_password=attempt
			if iteration==2:
				account.third_password=attempt
				
			new_path = '/account/'+str(iteration)+'/1/?user='+user
			memcache.set(key=user, value=site)
			account.put()
			return self.redirect(new_path)
		
		else:
			
			if attempt < 3:
				#ASSERT: The pass is not valid, redirect to the next attempt for this site	
				next_attempt=attempt+1
				new_path = '/account/'+str(iteration)+'/'+str(next_attempt)+'/?user='+user+'&site='+site
				msg = "Your password did not match the one you've created for this site. " 	
			if attempt >= 3:
				#ASSERT: The pass is not valid for this site and we do not have any more attempts left
				#redirect to the next site within the same iteration
				if iteration==1:
					account.second_password=0
				if iteration==2:
					account.third_password=0
					
				new_path = '/account/'+str(iteration)+'/1/?user='+user
				memcache.set(key=user, value=site)
				account.put()
				msg = "You have exhausted all attemps. Re-directing to the next site or the main menu if no sites are available. "
			
			template_values = {
				'attempts_left' : 3-attempt,
				'target_url': new_path,
				'message': msg,
			}
			self.response.write(bad_password_template.render(template_values))

		pass

app = webapp2.WSGIApplication([
    webapp2.Route(r'/', handler=MainHandler),
	webapp2.Route(r'/report', handler=ReportHandler),
	webapp2.Route(r'/account/<iteration>/<attempt>/', handler=AccountHandler),
	webapp2.Route(r'/save',   handler=AccountHandler, methods=['POST'], handler_method='save'),
	webapp2.Route(r'/verify', handler=AccountHandler, methods=['POST'], handler_method='verify')
], debug=True)
