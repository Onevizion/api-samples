import json
import time
import csv
import sys
import os
import base64
import onevizion

# Handle command arguments
import argparse

Description="""Upload EFiles to the JX_Electronic_Files Trackor and set some additional data.
"""
EpiLog = onevizion.PasswordExample + """Configuration File:
There a 4 "settings" for each of the 4 required pieces of data to insert a file.  Each of the 4 required datapoints will have 2 pieces of data.  "type", which can be "const" or "column", and "value" which is either a constant string in the case of "const" type, or the name of a CSV column in the case of "column" type.
Types are:
	TrackorType: This is the Trackor Type that the File is to be loaded into.
	FieldName: This is the Configured Field Name that will hold the uploaded file.
	FileName: This is the name of the file to be uplaoded.
	FilePath: This is the path where the file is found.
In addition to the 4 "settings", there is a "mappings" section.  This has 2 parts, "this" and "parent".  The "this" section is list of additional CSV Columns and the configured fields on this Trackor Type for which they are matched.  The "parent" lists CSV Columns and which parent TrackorType they are matched to.  The Parents will match the TRACKOR_KEY of the parent from that CSV Column.
Example Config.json:
{
	"settings": {
		"TrackorType": {
			"type": "const",
			"value": "JX_Electronic_Files"
		},
		"FieldName": {
			"type": "const",
			"value": "JXF_DOC"
		},
		"FilePath": {
			"type" : "const",
			"value" : "."
		},
		"FileName": {
			"type": "column",
			"value": "Document"
		},
		"NewFileName": {
			"type": "column",
			"value": "Document"
		}
	},
	"mappings": {
		"this": {
			"MT Document ID": "JXF_MT_DOCUMENT_ID",
			"Short Description": "JXF_SHORT_DESCRIPTION",
			"Last Updated": "JXF_LAST_UPDATED",
			"External File Name": "JXF_ORIGINATING_FILENAME"
		},
		"parent": {
			"GEL:Jurisdiction ID": "Government_Entity_Library",
			"COM: Comm ID": "Communications",
			"AGMT: Agreement ID": "Agreements_Library"
		}
	}
}
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description=Description,epilog=EpiLog)
parser.add_argument("OV_URL", help="The OneVizion URL from which to download the files. example: 'trackor.onevizion.com'.")
parser.add_argument("CSV_File", help="The CSV File list of the importable files to look for.")
parser.add_argument("ConfigFile", help="The JSON File defining CSV file mapping for this load.")
parser.add_argument("-p", "--passwords", metavar="PasswordsFile", help="JSON file where passwords are stored.", default="Passwords.json")
args = parser.parse_args()
URL = args.OV_URL
CSVFile = args.CSV_File
args = parser.parse_args()
PasswordsFile = args.passwords

#Load ConfigurationFile
with open(args.ConfigFile,"rb") as ConfFile:
	Configuration = json.load(ConfFile)

# Load in Passwords from protected file.
PasswordData = onevizion.GetPasswords(PasswordsFile)
# Make sure Passwordsfile has correct sections
PDError = (
	onevizion.CheckPasswords(PasswordData,'SMTP',['Server','Port','UserName','Password','To']),
	",\n",
	onevizion.CheckPasswords(PasswordData,URL,['UserName','Password'])
	)
if len(PDError) > 6:
	print PDError
	quit()

OVUserName = PasswordData[URL]["UserName"]
OVPassword = PasswordData[URL]["Password"]

# Build up Log for future use if needed
from collections import OrderedDict
Errors = OrderedDict()

#Readin the Parameter file
ParamFile = csv.DictReader(open(CSVFile))
CSVColumns = ParamFile.fieldnames

# Start a CSV File for Errored Lines
ErrorCSVFile = open(os.path.splitext(CSVFile)[0] + '-Errors.csv',"wb")
ErrorCSV = csv.DictWriter(ErrorCSVFile, fieldnames=CSVColumns)
ErrorCSV.writeheader()

# Start a Log File
LogFile = open(os.path.splitext(CSVFile)[0] + '.log',"wb")

#Iterate through the Parameter file (meaining the csv containing the list of documents)
i=0
for row in ParamFile:
	#Get TrackorType Settings
	if Configuration["settings"]["TrackorType"]["type"] == "const":
		TrackorType = Configuration["settings"]["TrackorType"]["value"]
	else:
		TrackorType = row[Configuration["settings"]["TrackorType"]["value"]]

	#Get FieldName Settings
	if Configuration["settings"]["FieldName"]["type"] == "const":
		FieldName = Configuration["settings"]["FieldName"]["value"]
	else:
		FieldName = row[Configuration["settings"]["FieldName"]["value"]]

	#Get FileName Settings
	if Configuration["settings"]["FileName"]["type"] == "const":
		FileName = Configuration["settings"]["FileName"]["value"]
	else:
		FileName = row[Configuration["settings"]["FileName"]["value"]]

	#Get FilePath Settings
	if Configuration["settings"]["FilePath"]["type"] == "const":
		FilePath = Configuration["settings"]["FilePath"]["value"]
	else:
		FilePath = row[Configuration["settings"]["FilePath"]["value"]]

	FullFilePath = FilePath+"/"+FileName

	#Get NewFileName Settings if specified
	try:
		if Configuration["settings"]["NewFileName"]["type"] == "const":
			FilePath = Configuration["settings"]["NewFileName"]["value"]
		else:
			NewFileName = row[Configuration["settings"]["NewFileName"]["value"]]
	except:
		NewFileName = FileName

	i=i+1

	try:
		#Read in and encode File to variable
		with open(FullFilePath, "rb") as BFile:
			B64Data = base64.b64encode(BFile.read())

		if len(B64Data) == 0:
			Errors[FullFilePath+'-ReadErrors'] = 'Empty file'
			ErrorCSV.writerow(row)
			LogError = 'Error: Row: ' + str(i) + " => " + "Empty file"
			print (LogError)
			LogFile.write(LogError+"\n")
			continue

	except:
		Errors[FullFilePath+'-ReadErrors'] = str(sys.exc_info()[0])
		ErrorCSV.writerow(row)
		LogError = 'Error: Row: ' + str(i) + " => Cannot read file"
		print (LogError)
		LogFile.write(LogError+"\n")
		continue

	OVCall = onevizion.Trackor(
		trackorType = TrackorType, 
		URL = URL, 
		userName=OVUserName, 
		password=OVPassword
		)

	# Create Parent Set connections for this Row
	parents={}
	for key, value in Configuration["mappings"]["parent"].items():
		if len(row[key])>0:
			parents[value] = {
				"TRACKOR_KEY": row[key]
				}

	#Create Fields mapping for this Row
	fields={}
	for key, value in Configuration["mappings"]["this"].items():
		if len(row[key])>0:
			fields[value] = row[key]
	# Attach Document
	fields[FieldName] = {'file_name':NewFileName,'data':B64Data}


	OVCall.create(
		fields=fields,
		parents=parents
		)
	if len(OVCall.errors) > 0:
		Errors[FullFilePath+'-ImportErrors'] = str(OVCall.errors)
		ErrorCSV.writerow(row)
		LogError = 'Error: Row: ' + str(i) + " => " + str(OVCall.errors)
		print (LogError)
		LogFile.write(LogError+"\n")

	LogRow = "Row %d - %s" % (i, FileName)
	print (LogRow)
	LogFile.write(LogRow+"\n")

ErrorCSVFile.close()
LogFile.close()


msg = onevizon.EMail()
msg.server = PasswordData["SMTP"]["Server"]
msg.port = int(PasswordData["SMTP"]["Port"])
msg.userName = PasswordData["SMTP"]["UserName"]
msg.password = PasswordData["SMTP"]["Password"]
if type(PasswordData["SMTP"]["To"]) is list:
	msg.to.extend(PasswordData["SMTP"]["To"])
else:
	msg.to.append(PasswordData["SMTP"]["To"])
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
