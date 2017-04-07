import OVUtils
import csv
import os
import shutil
import sys
import pysftp

# Handle command arguments
import argparse
EpiLog = OVUtils.PasswordExample + """\n\nCSV File needs columns:
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
PasswordData = OVUtils.GetPasswords(PasswordsFile)

PDError = (
	OVUtils.CheckPasswords(PasswordData,'SMTP',['Server','Port','UserName','Password']),
	",\n",
	OVUtils.CheckPasswords(PasswordData,URL,['UserName','Password'])
	)
if Destination == 'SFTP':
	PDError = PDError + ",\n" + OVUtils.CheckPasswords(PasswordData,SFTPHost,['Host','UserName','Root'],['Password', 'KeyFile'])
if len(PDError) > 6:
	print PDError
	quit()


# Start a CSV File for Errored Lines
ErrorCSVFile = open(os.path.splitext(CSVFile)[0] + '-Errors.csv',"wb")
FieldNames = ['BLOB_DATA_ID','PATH','FILENAME']
ErrorCSV = csv.DictWriter(ErrorCSVFile, fieldnames=FieldNames)
ErrorCSV.writeheader()

# Start a Log File
LogFile = open(os.path.splitext(CSVFile)[0] + '.log',"wb")



OVUserName = PasswordData[URL]["UserName"]
OVPassword = PasswordData[URL]["Password"]

ParamFile = csv.DictReader(open(CSVFile))
i=0

TempRoot = "Temp"
if not os.path.exists(TempRoot):
	os.makedirs(TempRoot)

for row in ParamFile:
	#BLOB_DATA_ID,PATH,FILENAME
	BlobDataID = row['BLOB_DATA_ID']
	Path = row['PATH']
	FileName = row['FILENAME']
	FilePath = Path + '/' + FileName
	RequestURL = "https://"+ OVUserName + ":" + OVPassword + "@" + URL + "/efiles/EFileGetBlobFromDb.do?id=" + BlobDataID
	i=i+1

	# Download File to temporary location
	if not os.path.exists(TempRoot+"/"+BlobDataID):
		os.makedirs(TempRoot+"/"+BlobDataID)
	TempFileName = TempRoot+"/" + BlobDataID + "/" + FileName
	Response = OVUtils.curl('GET', RequestURL , stream = True)
	with open(TempFileName,'wb') as TempFile:
		for chunk in Response.request.iter_content(chunk_size=1024):
			if chunk:
				TempFile.write(chunk)
				TempFile.flush()
				os.fsync(TempFile.fileno())
	LogRow = "Row %d - %s - %s - %s" % (i, BlobDataID, Path, FileName)
	print LogRow
	LogFile.write(LogRow+"\n")
	if not Response.request.ok or len(Response.errors) > 0:
		#handle errors
		Errors[FilePath+'-DownloadErrors'] = str(Response.errors)
		RowSet = {
					'BLOB_DATA_ID': BlobDataID,
					'PATH': Path,
					'FILENAME': FileName
				 }
		ErrorCSV.writerow(RowSet)
		LogError = 'Error: Row: ' + str(i) + " => " + str(Response.errors)
		print LogError
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
				sftp.put(TempFileName)  # To download a file, replace put with get
				sftp.close()  # Close connection
			except Exception as e:
				Errors[FilePath+'-SFTPErrors'] = str(e)
				LogError = 'SFTP Error: Row: ' + str(i) + " => " + str(e)
				print LogError
				LogFile.write(LogError+"\n")

		else:
			# Do Local File copy
			if not os.path.exists(FileRoot+"/"+Path):
				os.makedirs(FileRoot+"/"+Path)
			try:
				shutil.move(TempFileName,FileRoot+"/"+Path)
			except Exception as e:
				Errors[FilePath+'-FileCopyErrors'] = str(e)
				LogError = 'File Move Error: Row: ' + str(i) + " => " + str(e)
				print LogError
				LogFile.write(LogError+"\n")

	# Clean up Temp Files
	shutil.rmtree(TempRoot+"/"+BlobDataID)

shutil.rmtree(TempRoot)


ErrorCSVFile.close()
LogFile.close()
os.remove('efile_load.json')


msg = OVUtils.EMail()
msg.server = PasswordData["SMTP"]["Server"]
msg.port = int(PasswordData["SMTP"]["Port"])
msg.userName = PasswordData["SMTP"]["UserName"]
msg.password = PasswordData["SMTP"]["Password"]
msg.to.append("ovsupport@onevizion.com")
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


