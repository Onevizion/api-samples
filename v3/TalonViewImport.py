#!/usr/bin/env python3

import json
import csv
import sys
import os
import shutil
import glob
import zipfile
import csv
import onevizion

# Handle command arguments
import argparse
Description="""Moves files generated from TalonView and place in Closeout Package container.

1) Find files in the Inbound folder with given filemask
	a) Send CSV file to import
	b) unzip document archive
	c) Get List of TrackorIDs of COP-Lines with this associated COP as lookup
	d) Go through each document from zip file
		1) Match TrackorID
		2) send file to Trackor Location for COP-Line and Field
"""
EpiLog =  """ Example Parameters File:
{
	"TalonImport": {
		"url":"demo.onevizion.com",
		"UserName": "jsmith",
		"Password": "mypassword1",
		"SFTPToken": "TalonSFTP",
		"SMTPToken": "SMTP",
		"InboundFolder":".",
		"FileMask":"Talon*.csv",
		"ImportID":"10019666",
		"COPTrackorType":"CloseoutPackage",
		"COPLineTrackorType":"InspectionLineItem",
		"COPLineFields":["ILI_PRIMARY_PHOTO","ILI_PHOTO_2","ILI_PHOTO_3","ILI_PHOTO_4","ILI_PHOTO_5","ILI_PHOTO_6"],
		"COPID-CSV-Col":"ILI:Inspection Line Item ID"
	},
	"TalonSFTP": {
		"Host": "ftp.onevizion.com",
		"UserName": "ftpuser1",
		"Password": "ftppass1234"
	},
	"SMTP": {
		"UserName": "no-reply@onevizion.com",
		"Password": "noreppass1234",
		"Server": "smtp.office365.com",
		"Port": "587",
		"To": ["jsmith@onevizion.com","sholmes@onevizion.com","support@onevizion.com"],
		"Security": "STARTTLS"
	}
}
\n\n
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description=Description,epilog=EpiLog)
parser.add_argument(
	"-t",
	"--token",
	metavar="ParametersFileToken",
	help="JToken Name in Parameters File that holds parameter data for this script.",
	default="TalonImport"
	)
parser.add_argument(
	"-v",
	"--verbose",
	action='count',
	default=0,
	help="Print extra debug messages and save to a file. Attach file to email if sent."
	)
parser.add_argument(
	"-p",
	"--parameters",
	metavar="ParametersFile",
	help="JSON file where parameters are stored.",
	default="Parameters.json"
	)
args = parser.parse_args()
ParametersFile = args.parameters
onevizion.Config["Verbosity"] = args.verbose
ConfigToken = args.token

# Load in Passwords from protected file.
ParameterData = onevizion.GetParameters(ParametersFile)
Params = ParameterData[ConfigToken]
onevizion.Config["SMTPToken"] = Params["SMTPToken"]


Message = onevizion.TraceMessage

# Build up Log for future use if needed
from collections import OrderedDict
Trace = onevizion.Config["Trace"]


#FileNames to Use in Process
FileNameHead = __file__[:-3]
LockFileName = FileNameHead+'.lck'
LockFile = None

def ConfigDump():
	Conf = {}
	Conf[ConfigToken] = Params
	Conf[Params["SMTPToken"]] = ParameterData[Params["SMTPToken"]]
	Conf[Params["SFTPToken"]] = ParameterData[Params["SFTPToken"]]
	Conf[ConfigToken]["Password"] = "************"
	Conf[Params["SMTPToken"]]["Password"] = "************"
	Conf[Params["SFTPToken"]]["Password"] = "************"
	return json.dumps(Conf,indent=2)

def ErrorNotif (ErrMsg):
	"""Sends Mail notifying if an error occurs"""

	msg = onevizion.EMail()
	msg.subject = ErrMsg
	msg.message = ErrMsg + "\nConfig:\n" + ConfigDump()

	msg.info.update(Trace)

	msg.sendmail()

	quit()


###############################################################################
#  Start Script Here														  #
###############################################################################
Locker = onevizion.Singleton(LockFileName)
Err = False

DocFileFields = Params["COPLineFields"]


# 1) Find files in the Inbound folder with given filemask
for filename in glob.glob(Params["InboundFolder"]+"/"+Params["FileMask"]):
	# a) Send CSV file to import
	Message("Sending Import to Trackor for {File}".format(File=filename))
	Imp = onevizion.Import(
		paramToken = ConfigToken,
		impSpecId = Params["ImportID"],
		action='UPDATE',
		file = filename
		)
	if len(Imp.errors) > 0 or Imp.processId is None:
		Message(filename+" failed to Import from TalonView.")
		Err = True
		continue
	else:
		ProcID = Imp.processId
		Message("{File} import successfully started. ProcessID={ProcID}".format(File=filename,ProcID=ProcID),1)

	# find which COP this is
	CSVData = csv.DictReader(open(filename))

	COPLIID = ""
	for row in CSVData:
		COPLIID = row[Params["COPID-CSV-Col"]]
		break

	COP = "-".join(COPLIID.split("-"))[:-1][:-1]
	Message("This COP is {COP}".format(COP=COP),1)

	# b) unzip document archive
	COPFolder = Params["InboundFolder"]+"/"+COP
	if not os.path.exists(COPFolder):
		os.makedirs(COPFolder)
	ZipFileName = ".".join(filename.split(".")[:-1])+".zip"
	Message("Unzipping {File}".format(File=ZipFileName),1)
	with zipfile.ZipFile(ZipFileName,"r") as zip_ref:
		zip_ref.extractall(COPFolder)

	# c) Get List of TrackorIDs of COP-Lines with this associated COP as lookup
	COPLineRequest = onevizion.Trackor(
		trackorType = Params["COPLineTrackorType"],
		paramToken = ConfigToken
		)
	COPLineRequest.read(
		filters={
			Params["COPTrackorType"]+".TRACKOR_KEY":COP
			} ,
		fields=[
			'TRACKOR_KEY'
			]
		)
	COPLines={}
	for COPLine in COPLineRequest.jsonData:
		COPLines[COPLine["TRACKOR_KEY"]] = COPLine["TRACKOR_ID"]

	# d) Go through each document from zip file
	for docname in glob.glob(Params["InboundFolder"]+"/"+COP+"/*.*"):
		# Remove extension
		Message("Processing File {File}".format(File=docname),1)

		DocData = ".".join(docname.split("/")[-1].split(".")[:-1])
		# Remove last hyphen section , which is the file number and join the rest back up
		COPLine = "-".join(DocData.split("-")[:-1])
		# Get only the file number
		try:
			FileNum = int(DocData[-1])
		except Exception as e:
			Message("Invalid File name: {File}".format(docname))
			Err = True
			continue
		if FileNum > len(DocFileFields):
			Message("Invalid Field Number in file name: {File}".format(docname))
			Err = True
			continue

		# 1) Match TrackorID
		# 2) send file to Trackor Location for COP-Line and Field
		COPLineRequest.UploadFile(
			trackorId = COPLines[COPLine],
			fieldName = DocFileFields[FileNum - 1],
			fileName = docname
			)

	# Archive Files so they won't get picked up next time. And Clean up unzipped files
	ArchiveFolder = Params["InboundFolder"]+"/Archive"
	if not os.path.exists(ArchiveFolder):
		os.makedirs(ArchiveFolder)
	shutil.move(filename,ArchiveFolder)
	shutil.move(ZipFileName,ArchiveFolder)
	shutil.rmtree(Params["InboundFolder"]+"/"+COP)

if Err:
	ErrorNotif("TalonView Import had errors.")


