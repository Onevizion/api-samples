#!/usr/bin/env python3

import json
import os
import onevizion
import PyPDF2
import datetime

'''
mergeFile = PyPDF2.PdfFileMerger()
mergeFile.append(PyPDF2.PdfFileReader('x.pdf', 'rb'))
mergeFile.append(PyPDF2.PdfFileReader('y.pdf', 'rb'))
mergeFile.write("NewMergedFile.pdf")
'''

# sample settings.json
'''
{
	"OV":
		{
			"UserName":"service-account",
			"Password":"******",
			"Url":"xxx.onevizion.com"
		},
	"MainTrackor":
		{
			"TrackorType":"LTC",
			"Fields" : ["TRACKOR_KEY","LTC_COMPLETE_TITLE_PACKET_STAT"],
			"Filters" : {"LTC_COMPLETE_TITLE_PACKET_STAT":"Queued"},
			"Sort" : {"TRACKOR_KEY":"ASC"},
			"FirstFileFieldName" : "LTC_COMPLETED_LTC_DOCUMENT",
			"DestFileFieldName" : "LTC_COMPLETED_LTC_PACKET",
			"StatusField" : "LTC_COMPLETE_TITLE_PACKET_STAT",
			"ErrorField" : "LTC_COMPLETE_TITLE_PACKET_ERRO"
		},
	"ChildTrackor":
		{
			"TrackorType":"Title_Documents",
			"Fields" : ["TDOC_RECORDED_DATE", "TDOC_BOOKPAGE", "TDOC_PAGE", "TDOC_CLERKS_FILE__DOCUMENT_", "TRACKOR_KEY"],
			"Filters" : {"TDOC_DOCUMENT_FILE": "not null"},
			"Sort" : {"TDOC_RECORDED_DATE":"ASC", "TDOC_BOOKPAGE": "ASC", "TDOC_PAGE": "ASC", "TDOC_CLERKS_FILE__DOCUMENT_":"ASC"},
			"FileFieldName" : "TDOC_DOCUMENT_FILE"
		}
}
'''
#The settings file is in 3 parts.
# OV - how to log into OneVizion
# MainTrackor - Trackor that source and destination fields.
# ChildTrackor - Trackor with many source files.

# Read settings
with open('settings.json','r') as p:
	params = json.loads(p.read())

try:
	OvUserName = params['OV']['UserName']
	OvPassword = params['OV']['Password']
	OvUrl      = params['OV']['Url']
	MainTrackorType = params['MainTrackor']['TrackorType']
	MainFields = params['MainTrackor']['Fields']
	MainFilters = params['MainTrackor']['Filters']
	MainSort = params['MainTrackor']['Sort']
	MainSourceFileFieldName = params['MainTrackor']['SourceFileFieldName']
	MainDestFileFieldName = params['MainTrackor']['DestFileFieldName']
	MainStatusFieldName = params['MainTrackor']['StatusField']
	MainErrorFieldName = params['MainTrackor']['ErrorField']
	ChildTrackorType = params['ChildTrackor']['TrackorType']
	ChildFields = params['ChildTrackor']['Fields']
	ChildFilters = params['ChildTrackor']['Filters']
	ChildSort = params['ChildTrackor']['Sort']
	ChildFileFieldName = params['ChildTrackor']['FileFieldName']
except Exception as e:
	raise "Please check settings"

#TODO make sure api user has RE on the tab with checkbox and the field list of blobs and RE for the trackor type(sometimes Checklist) and R for WEB_SERVICES 
Req = onevizion.Trackor(trackorType = MainTrackorType, URL = OvUrl, userName=OvUserName, password=OvPassword)
Req.read(filters = MainFilters,
		fields = MainFields,
		sort = MainSort,
		page = 1, 
		perPage = 100)

if len(Req.errors)>0:
	# If can not read list of efiles then must be upgrade or something.  Quit and try again later.
	print(Req.errors)
	quit(1)

print("Found {x} records".format(x=len(Req.jsonData)))
for row in Req.jsonData:
	mergeFile = PyPDF2.PdfFileMerger()

	filename = ""

	try:
		fname = Req.GetFile(trackorId=row['TRACKOR_ID'], fieldName = MainSourceFileFieldName)
		# add to the pdf
		mergeFile.append(PyPDF2.PdfFileReader(fname, 'rb'))

		# remove downloaded pdf
		os.remove(fname)

		cdocs = onevizion.Trackor(trackorType = ChildTrackorType, URL = OvUrl, userName=OvUserName, password=OvPassword)
		cdocsfilter = ChildFilters
		cdocsfilter[ MainTrackorType+".TRACKOR_ID" ] = row["TRACKOR_ID"]
		cdocs.read(
			filters = cdocsfilter,
			fields = ChildFields,
			sort = ChildSort
			)
		if len(cdocs.errors)>0:
			print('hi')
		for cdoc in cdocs.jsonData:
			#
			# download the file
			print(cdoc)
			fname = cdocs.GetFile(trackorId=cdoc['TRACKOR_ID'], fieldName = ChildFileFieldName)
			# add to the pdf
			mergeFile.append(PyPDF2.PdfFileReader(fname, 'rb'))

			# remove downloaded pdf
			os.remove(fname)


		#filename = [LTC XITOR KEY] - Complete LTC Packet - [mmddyyyy]
		filename = '{ltckey} Complete LTC Packet - {date}.pdf'.format(
				ltckey = row['TRACKOR_KEY'], 
				date = datetime.datetime.today().strftime('%m%d%Y') 
				)

		mergeFile.write(filename)

		# send back to onevizion
		updateFields = {}
		updateFields[MainDestFileFieldName] = onevizion.EFileEncode(filename)
		updateFields[MainStatusFieldName] = 'Success'
		Req.update(
			filters = {'TRACKOR_ID' : row['TRACKOR_ID']},
			fields = updateFields
			) 

		# delete pdf
		os.remove(filename)
	except Exception as e:
		errors = e
		print(e)
		# send back to onevizion
		updateFields = {}
		updateFields[MainErrorFieldName] = errors
		updateFields[MainStatusFieldName] = 'Error'
		Req.update(
			filters = {'TRACKOR_ID' : row['TRACKOR_ID']},
			fields = updateFields
			) 

		# delete pdf
		#os.remove(filename)

