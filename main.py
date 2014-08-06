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
import datetime

from google.appengine.ext import db
from google.appengine.api import memcache

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
	
main_template=JINJA_ENVIRONMENT.get_template('index.html')
report_template=JINJA_ENVIRONMENT.get_template('report.html')
account_template=JINJA_ENVIRONMENT.get_template('account.html')

class Account(db.Model):
	date = db.DateTimeProperty(auto_now_add=True)
	user = db.StringProperty(indexed=True)
	site = db.StringProperty()
	initial_password = db.StringProperty()
	second_password = db.StringProperty()
	third_password = db.StringProperty()
	pass
	
def get_all_accounts():
	"""Returns all stored accounts as a list of lists."""	
	accounts=[]
	q = Account.all()
	q.order('-date')
	accounts.append(['Date','User','Site','1st pwd','2nd pwd','3rd pwd'])
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
	
def get_possible_sites():
	"""Returns a set of sites available for account creation. Each site 
	is represented by an image in the 'images' directory. """
	files=set(glob.glob('images/*'))
	return files
	
def get_registered_sites(user):
	"""Returns a set of the sites the specified user has registered for."""
	sites=set()
	q=Account.all()
	q.filter('user =',user)
	for account in q:
		sites.add(account.site)
	return sites

class MainHandler(webapp2.RequestHandler):
	def get(self):
		self.response.write(main_template.render())
		pass

class ReportHandler(webapp2.RequestHandler):
	def get(self):
		template_values = {
			'accounts' : get_all_accounts(),
		}
		self.response.write(report_template.render(template_values))
		pass
		
class AccountHandler(webapp2.RequestHandler):
	def get(self):
		user=cgi.escape(self.request.get('user'))
		possible_sites=get_possible_sites()
		try:
			if user:
				last_site=memcache.get(user)
				registered_sites=get_registered_sites(user)
				registered_sites.add(last_site)
				allowed_sites=possible_sites.difference(registered_sites)
				print registered_sites
				if len(allowed_sites)==0:
					self.redirect('/')
				site=random.sample(allowed_sites, 1)
			else:
				site=random.sample(possible_sites,1)
			
			template_values = {
				'selected_site' : cgi.escape(site.pop()),
				'user': user
			}
			self.response.write(account_template.render(template_values))
		except ValueError:
				self.response.write(main_template.render())
		pass
	
	def save(self):
		"""Saves the account credentials and redirects to the new account page."""
		user=cgi.escape(self.request.get('user'))
		password=cgi.escape(self.request.get('pass1'))
		site=cgi.escape(self.request.get('site'))
		self.response.status=201
		account=Account(
			user=user,
			initial_password=password,
			site=site
		)
		memcache.set(key=user, value=site)
		account.put()
		new_path='/account?user='+user
		return self.redirect(new_path)
		
class ExperimentHandler(webapp2.RequestHandler):
	def get(self):
		self.response.write('Experiment')
		pass
		

app = webapp2.WSGIApplication([
    webapp2.Route(r'/', handler=MainHandler),
	webapp2.Route(r'/report', handler=ReportHandler),
	webapp2.Route(r'/account', handler=AccountHandler),
	webapp2.Route(r'/experiment', handler=ExperimentHandler),
	webapp2.Route(r'/save', handler=AccountHandler, methods=['POST'], handler_method='save')
], debug=True)
