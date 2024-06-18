#!/usr/bin/env python

import json
import time
import csv
import sys
import os
import onevizion
import argparse
import base64
import traceback
#import ftplibs
import datetime
import shutil
import subprocess
import pandas as pd
from collections import OrderedDict


Description="""Download file from a onevizion efile field.  Run downloaded file as import using import spec and action from config.
"""
EpiLog = onevizion.PasswordExample + """\n\n
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description=Description,epilog=EpiLog)
parser.add_argument("-v", "--verbose", action='count', default=0, help="Print extra debug messages and save to a file. Attach file to email if sent.")
parser.add_argument("-p", "--passwords", metavar="PasswordsFile", help="JSON file where passwords are stored.", default="settings.json")
args = parser.parse_args()
PasswordsFile = args.passwords

PasswordData = onevizion.GetParameters(PasswordsFile)
onevizion.Config["Verbosity"]=args.verbose

OVSourceUserName = PasswordData["OV_SOURCE"]["UserName"]
OVSourcePassword = PasswordData["OV_SOURCE"]["Password"]
OVSourceUrl      = PasswordData["OV_SOURCE"]["Url"]

Trace = onevizion.Config["Trace"]
Message = onevizion.Message

Integrations = onevizion.Trackor(trackorType = 'IntegrationTrackor', URL = OVSourceUrl, userName=OVSourceUserName, password=OVSourcePassword)

searchCond   = 'equal(IT_INTEGRATION_STATUS, "Enabled")'
resultFields = ['TRACKOR_KEY', 'IT_DESTINATION_URL',
				'IT_OV_SOURCE_FILTER','IT_OV_SOURCE_SEARCH','IT_OV_SOURCE_TRACKOR_TYPE',
				'IT_OV_DESTINATION_MAPPING','IT_OV_DESTINATION_TRACKOR_TYPE',
				'IT_OV_SOURCE_KEY_FIELD','IT_OV_DESTINATION_KEY_FIELD','IT_OV_SOURCE_CLEAR_FIELD',
				'IT_ORDER_NUMBER','IT_SOURCE_ERROR_FIELD'
				]
sortFields   = {'IT_ORDER_NUMBER':'ASC'}

Integrations.read(search = searchCond, fields = resultFields, sort=sortFields)

for intT in Integrations.jsonData:

	Message(intT['TRACKOR_KEY'])

	OVDestUserName = PasswordData[intT["IT_DESTINATION_URL"]]["UserName"]
	OVDestPassword = PasswordData[intT["IT_DESTINATION_URL"]]["Password"]
	OVDestUrl      = PasswordData[intT["IT_DESTINATION_URL"]]["Url"]

	Message(OVDestUrl)

	srcFields = []
	srcFields2 = []
	desFields = []

	for x,y in json.loads(intT['IT_OV_DESTINATION_MAPPING']).items():
		srcFields.append(x)
		srcFields2.append(x)
		desFields.append(y)
	srcFields2.append(intT['IT_OV_SOURCE_KEY_FIELD'])
	Message(srcFields)
	Message(desFields)

	srcReq = onevizion.Trackor(trackorType = intT['IT_OV_SOURCE_TRACKOR_TYPE'], URL = OVSourceUrl, userName=OVSourceUserName, password=OVSourcePassword)
	srcReq.read(
		search = intT['IT_OV_SOURCE_SEARCH'],
		fields = srcFields2
		)

	# T_READY_TO_SEND_ERRORS T_TRC_READY_TO_SEND
	if len(srcReq.errors) == 0:
		Message("Found %s records to move for %s" %(intT['TRACKOR_KEY'], len(srcReq.jsonData)))
		innerTrace = OrderedDict()
		for row in srcReq.jsonData:

			srcClearFields = {}
			updateColl = {}
			for i in range(len(srcFields)):
				updateColl[ desFields[i] ] = row[ srcFields[i] ]
			#Message(updateColl)
			desReq = onevizion.Trackor(trackorType = intT['IT_OV_DESTINATION_TRACKOR_TYPE'], URL = OVDestUrl, userName=OVDestUserName, password=OVDestPassword)
			desReq.update(
				filters = {intT['IT_OV_DESTINATION_KEY_FIELD'] : row[intT['IT_OV_SOURCE_KEY_FIELD']]},
				fields = updateColl
				)
			srcClear = onevizion.Trackor(trackorType = intT['IT_OV_SOURCE_TRACKOR_TYPE'], URL = OVSourceUrl, userName=OVSourceUserName, password=OVSourcePassword)
			if len(desReq.errors) == 0:
				Message(intT['IT_OV_SOURCE_CLEAR_FIELD'])
				srcClearFields[intT['IT_OV_SOURCE_CLEAR_FIELD']] = 'Sent'
				srcClearFields[intT['IT_SOURCE_ERROR_FIELD']] = None

				Message(srcClearFields)
				srcClear.update(
					filters = {"TRACKOR_ID": row["TRACKOR_ID"]},
					fields = srcClearFields
					)
				if len(srcClear.errors) > 0:
					innerTrace[intT['TRACKOR_KEY']+' '+intT['IT_OV_DESTINATION_KEY_FIELD']+" clear"] = srcClear.errors
			else:
				innerTrace[intT['TRACKOR_KEY']+' '+intT['IT_OV_DESTINATION_KEY_FIELD']] = desReq.errors
				srcClearFields[intT['IT_OV_SOURCE_CLEAR_FIELD_TRIGGER']] = 'Error'
				srcClearFields[intT['IT_SOURCE_ERROR_FIELD']] = desReq.errors
				srcClear.update(
					filters = {"TRACKOR_ID": row["TRACKOR_ID"]},
					fields = srcClearFields
					)
				if len(srcClear.errors) > 0:
					innerTrace[intT['TRACKOR_KEY']+' '+intT['IT_OV_DESTINATION_KEY_FIELD']+" clear"] = srcClear.errors

				#todo check errors
#if len(Trace)>0:
	#Message(Trace)
#	ErrorNotif("Errors in loading onevizion to onevizion")
