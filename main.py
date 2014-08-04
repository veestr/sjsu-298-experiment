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

from google.appengine.ext import ndb

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
	
main_template=JINJA_ENVIRONMENT.get_template('index.html')
report_template=JINJA_ENVIRONMENT.get_template('report.html')
account_template=JINJA_ENVIRONMENT.get_template('account.html')

def getPossibleSites():
	"""Returns a set of sites available for account creation. Each site 
	is represented by an image in the 'images' directory. """
	files=set(glob.glob('images/*'))
	return files
	
class Account(ndb.Model):
	date = ndb.DateTimeProperty(auto_now_add=True)
	user = ndb.StringProperty(indexed=True)
	site = ndb.StringProperty()
	initial_password = ndb.StringProperty()
	second_password = ndb.StringProperty()
	third_password = ndb.StringProperty()
	pass
	
	@classmethod
	def getRegisteredSites(cls,user):
		"""Returns a set of the sites the specified user has registered for."""
		sites=set()
		qry=Account.query(Account.user==user)
		for account in qry:
			sites.add(account.site)
		return sites

class MainHandler(webapp2.RequestHandler):
	def get(self):
		self.response.write(main_template.render())
		pass

class ReportHandler(webapp2.RequestHandler):
	def get(self):
		self.response.write('Report')
		pass
		
class AccountHandler(webapp2.RequestHandler):
	def get(self):
		user=cgi.escape(self.request.get('user'))
		possible_sites=getPossibleSites()
		try:
			if user:
				#ASSERT: The user could have registered for sites in the past
				existing_sites=Account.getRegisteredSites(user)
				allowed_sites=possible_sites.difference(existing_sites)
				print existing_sites
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
		"""Saves the account credentials"""
		user=cgi.escape(self.request.get('user'))
		password=cgi.escape(self.request.get('pass1'))
		site=cgi.escape(self.request.get('site'))
		self.response.status=201
		account=Account(
			user=user,
			initial_password=password,
			site=site
		)
		account.put()
		pass
		
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
