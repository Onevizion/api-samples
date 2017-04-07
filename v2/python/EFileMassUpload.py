import OVUtils
import csv
import os
import shutil
import sys
import base64
import json


# Handle command arguments
import argparse
EpiLog = OVUtils.PasswordExample + """\n\nCSV File needs columns:
	TRACKOR_KEY  - Trackor Key Value
	TRACKOR_TYPE - Trackor Type
	FIELD_NAME   - Configured Field Name
	FILE_NAME    - Local File Name to be uploaded
	PATH_TO_FILE - Path where file is located locally
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,epilog=EpiLog)
parser.add_argument("OV_URL", help="The OneVizion URL from which to download the files.")
parser.add_argument("CSV_File", help="The CSV File list of the files to download.")
parser.add_argument("-p", "--passwords", metavar="PasswordsFile", help="JSON file where passwords are stored.", default="Passwords.json")
args = parser.parse_args()
URL = args.OV_URL
CSVFile = args.CSV_File
PasswordsFile = args.passwords


# Load in Passwords from protected file.
PasswordData = OVUtils.GetPasswords(PasswordsFile)

# Make sure Passwords.json file has Stuff it needs
PDError = (
	OVUtils.CheckPasswords(PasswordData,'SMTP',['Server','Port','UserName','Password']),
	",\n",
	OVUtils.CheckPasswords(PasswordData,URL,['UserName','Password'])
	)
if len(PDError) > 3:
	print PDError
	quit()


# Build up Log for future use if needed
from collections import OrderedDict
Errors = OrderedDict()


# Start a CSV File for Errored Lines
ErrorCSVFile = open(os.path.splitext(CSVFile)[0] + '-Errors.csv',"wb")
FieldNames = ['TRACKOR_KEY','TRACKOR_TYPE','FIELD_NAME','FILE_NAME','PATH_TO_FILE']
ErrorCSV = csv.DictWriter(ErrorCSVFile, fieldnames=FieldNames)
ErrorCSV.writeheader()

# Start a Log File
LogFile = open(os.path.splitext(CSVFile)[0] + '.log',"wb")



ParamFile = csv.DictReader(open(CSVFile))
i=0
for row in ParamFile:
	#TRACKOR_KEY,TRACKOR_TYPE,FIELD_NAME,FILE_NAME,PATH_TO_FILE
	TrackorKey = row['TRACKOR_KEY']
	TrackorType = row['TRACKOR_TYPE']
	FieldName = row['FIELD_NAME']
	FileName = row['FILE_NAME']
	FilePath = row['PATH_TO_FILE']
	i=i+1

	with open(FilePath, "rb") as BFile:
		B64Data = base64.b64encode(BFile.read())

	OVCall = OVUtils.Trackor(trackorType = TrackorType, URL = URL, userName=str(PasswordData[URL]['UserName']), password=str(PasswordData[URL]['Password']))
	OVCall.update(filters={'TRACKOR_KEY':TrackorKey}, fields={FieldName:{'file_name':FileName,'data':B64Data}})
	if len(OVCall.errors) > 0:
		Errors[FilePath+'-ImportErrors'] = str(OVCall.errors)
		RowSet = {
					'TRACKOR_KEY': TrackorKey,
					'TRACKOR_TYPE': TrackorType,
					'FIELD_NAME': FieldName,
					'FILE_NAME': FileName,
					'PATH_TO_FILE': FilePath
				 }
		ErrorCSV.writerow(RowSet)
		LogError = 'Error: Row: ' + str(i) + " => " + str(OVCall.errors)
		print LogError
		LogFile.write(LogError+"\n")

	LogRow = "Row %d - %s - %s - %s - %s" % (i, TrackorKey, TrackorType, FieldName, FileName)
	print LogRow
	LogFile.write(LogRow+"\n")

ErrorCSVFile.close()
LogFile.close()
#os.remove('efile_load.json')


msg = OVUtils.EMail()
msg.server = PasswordData["SMTP"]["Server"]
msg.port = int(PasswordData["SMTP"]["Port"])
msg.userName = PasswordData["SMTP"]["UserName"]
msg.password = PasswordData["SMTP"]["Password"]
msg.to.append("ovsupport@onevizion.com")
if len(Errors) > 0:
	msg.subject = "Errors in uploading to " + URL + " from " + CSVFile
	msg.message = "Errors in upload attempt:"
	msg.info.update(Errors)
	msg.files.append(os.path.splitext(CSVFile)[0] + '-Errors.csv')
	msg.files.append(os.path.splitext(CSVFile)[0] + '.log')
else:
	msg.subject = "Success in uploading to " + URL + " from " + CSVFile
	msg.message = "No Errors."


msg.sendmail()

