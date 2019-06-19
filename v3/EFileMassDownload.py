import onevizion
import csv
import os
import shutil
import sys
import pysftp

# Handle command arguments
import argparse
EpiLog = onevizion.PasswordExample + """\n\nCSV File needs columns:
	BLOB_DATA_ID - Blob Data ID for the file as found in OveVizion System
	PATH - FilePath within the Root Folder that you wish this to be saved into
	FILENAME - FileName to be given this file in the PATH's folder.
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,epilog=EpiLog)
parser.add_argument("OV_URL", help="The OneVizion URL from which to download the files.")
parser.add_argument("CSV_File", help="The CSV File list of the files to download.")
parser.add_argument("-d", "--destination", nargs=2, metavar=('TYPE','LOCATION'), help='Destination for the downlaoded files. The "Type" parameter can be "SFTP" or "Local". This is followed by the "Location" parameter, which is the hostname of the SFTP server if the type is SFTP, or a local file system path for the root folder of where to place the files if the Type is Local.')
parser.add_argument("-p", "--passwords", metavar="PasswordsFile", help="JSON file where passwords are stored.", default="Passwords.json")
parser.set_defaults(destination=["Local","."])
args = parser.parse_args()
URL = args.OV_URL
CSVFile = args.CSV_File
Destination = args.destination[0].upper()
if Destination == 'SFTP':
	SFTPHost = args.destination[1]
	FileRoot = ""
elif Destination == 'LOCAL':
	FileRoot = args.destination[1]
	SFTPHost = ""
PasswordsFile = args.passwords


# Build up Log for future use if needed
from collections import OrderedDict
Errors = OrderedDict()

# Load in Passwords from protected file.
PasswordData = onevizion.GetPasswords(PasswordsFile)

PDError = (
	onevizion.CheckPasswords(PasswordData,'SMTP',['Server','Port','UserName','Password']),
	",\n",
	onevizion.CheckPasswords(PasswordData,URL,['UserName','Password'])
	)
if Destination == 'SFTP':
	PDError = PDError + ",\n" + onevizion.CheckPasswords(PasswordData,SFTPHost,['Host','UserName','Root'],['Password', 'KeyFile'])
if len(PDError) > 6:
	print (PDError)
	quit()

#Make sure only one instance running
Locker = onevizion.Singleton()

# Start a CSV File for Errored Lines
print(CSVFile)
ErrorCSVFile = open(os.path.splitext(CSVFile)[0] + '-Errors.csv',"w")
FieldNames = ['TRACKOR_ID','FIELD_NAME','FILE_NAME','TRACKOR_KEY','PATH']
ErrorCSV = csv.DictWriter(ErrorCSVFile, fieldnames=FieldNames)
ErrorCSV.writeheader()

# Start a Log File
LogFile = open(os.path.splitext(CSVFile)[0] + '.log',"w")



OVUserName = PasswordData[URL]["UserName"]
OVPassword = PasswordData[URL]["Password"]

ParamFile = csv.DictReader(open(CSVFile))
i=0

TempRoot = "Temp"
if not os.path.exists(TempRoot):
	os.makedirs(TempRoot)

for row in ParamFile:
	#
	TrackorID = row['TRACKOR_ID']
	FieldName = row['FIELD_NAME']
	TrackorKey = row['TRACKOR_KEY']
	FileName = row['FILE_NAME']
	Path = row['PATH']
	FilePath = Path + '/' + FileName

	EFileReq = onevizion.Trackor(URL = URL, userName=OVUserName, password=OVPassword)
	tmpFileName = EFileReq.GetFile(trackorId=TrackorID, fieldName=FieldName)
	i=i+1

	LogRow = "Row %d - %s - %s - %s" % (i, TrackorID, TrackorKey, FieldName)
	print (LogRow)
	LogFile.write(LogRow+"\n")
	if not EFileReq.request.ok or len(EFileReq.errors) > 0:
		#handle errors
		Errors[FilePath+'-DownloadErrors'] = str(EFileReq.errors)
		ErrorCSV.writerow(row)
		LogError = 'Error: Row: ' + str(i) + " => " + str(EFileReq.errors)
		print (LogError)
		LogFile.write(LogError+"\n")
	else:
		# Copy File to final Destination
		if Destination == 'SFTP':
			UserName = PasswordData[SFTPHost]['UserName']
			RootFolder = PasswordData[SFTPHost]['Root']
			Host = PasswordData[SFTPHost]['Host']
			# Do SFTP copy
			try:
				if "KeyFile" in PasswordData[SFTPHost]:
					# Use Private key if it is available
					KeyFile = PasswordData[SFTPHost]['KeyFile']
					sftp = pysftp.Connection(host=Host, username=UserName, private_key=KeyFile)
				else:
					# Use Password
					SFTPPassword = PasswordData[SFTPHost]['Password']
					sftp = pysftp.Connection(host=Host, username=UserName, password=SFTPPassword)
				sftp.mkdir(RootFolder+"/"+Path) # makes all non-existing dirs in path
				sftp.chdir(RootFolder+"/"+Path)  # change directory on remote server
				sftp.put(FileName)  # To download a file, replace put with get
				sftp.close()  # Close connection
			except Exception as e:
				Errors[FilePath+'-SFTPErrors'] = str(e)
				LogError = 'SFTP Error: Row: ' + str(i) + " => " + str(e)
				print (LogError)
				LogFile.write(LogError+"\n")

		else:
			# Do Local File copy
			if not os.path.exists(Path):
				os.makedirs(Path)
			try:
				shutil.move(tmpFileName,FilePath)
			except Exception as e:
				Errors[FilePath+'-FileCopyErrors'] = str(e)
				LogError = 'File Move Error: Row: ' + str(i) + " => " + str(e)
				print (LogError)
				LogFile.write(LogError+"\n")

shutil.rmtree(TempRoot)


ErrorCSVFile.close()
LogFile.close()


onevizion.Config["SMTPToken"]="SMTP"

msg = onevizion.EMail()
if len(Errors) > 0:
	msg.subject = "Errors in downloading to " + URL + " from " + CSVFile
	msg.message = "Errors in download attempt:"
	msg.info.update(Errors)
	msg.files.append(os.path.splitext(CSVFile)[0] + '-Errors.csv')
	msg.files.append(os.path.splitext(CSVFile)[0] + '.log')
else:
	msg.subject = "Success in downloading to " + URL + " from " + CSVFile
	msg.message = "No Errors."


msg.sendmail()
