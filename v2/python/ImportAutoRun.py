import OVUtils
import csv
import os
import glob
import shutil

# Handle command arguments
import argparse
EpiLog = OVUtils.PasswordExample + """\n\nCSV File needs columns:
	FileName - FileName mask to be searched for.  Can include wildcards.
	Path - OS folder in whihc ot search for these files.
	Action - UPDATE, INSERT, or INSERT_UPDATE
	ImpSpecID - The Import Spec ID from the OneVision System
	URL - The main URL for the Site, example: "trackor.onevizion.com"
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,epilog=EpiLog)
parser.add_argument("CSV_File", help="The CSV File list of the importable files to look for.", default="ImportAutoRun.csv")
parser.add_argument("-p", "--passwords", metavar="PasswordsFile", help="JSON file where passwords are stored.", default="Passwords.json")
args = parser.parse_args()
CSVFile = args.CSV_File
PasswordsFile = args.passwords

# Load in Passwords from protected file.
PasswordData = OVUtils.GetPasswords(PasswordsFile)
PDError = OVUtils.CheckPasswords(PasswordData,'SMTP',['Server','Port','UserName','Password','To'])
if len(PDError) > 0:
	print PDError
	quit()

# Build up Log for future use if needed
from collections import OrderedDict
Trace = OrderedDict()

def ErrorNotif (ErrMsg):
	"""Sends Mail notifying if an error occurs"""

	print "Sendinf ErrorNotif"
	msg = OVUtils.EMail()
	msg.server = PasswordData["SMTP"]["Server"]
	msg.port = int(PasswordData["SMTP"]["Port"])
	msg.userName = PasswordData["SMTP"]["UserName"]
	msg.password = PasswordData["SMTP"]["Password"]
	msg.to.append(PasswordData["SMTP"]["To"])
	msg.subject = ErrMsg
	msg.message = ErrMsg
	
	msg.info.update(Trace)

	msg.sendmail()
	print msg.body

	quit()


ParamFile = csv.DictReader(open(CSVFile))
for row in ParamFile:
	#FileName,Path,Action,ImpSpecID,URL
	FileMask = str(row['FileName'])
	Path = str(row['Path'])
	Action = str(row['Action'])
	ImpSpecID = str(row['ImpSpecID'])
	URL = str(row['URL'])
	try:
		Incremental = str(row['Incremental'])
	except:
		Incremental = "0"
	try:
		Comment = str(row['Comment'])
	except:
		Comment = ""

	if Action:
		if Action not in ['INSERT', 'INSERT_UPDATE', "UPDATE"]:
			raise "Action must be INSERT or UPDATE or INSERT_UPDATE"
	else:
		Action = "INSERT_UPDATE"

	if FileMask[:1] == "#" :
		print "Skipping Row : "+FileMask+" : "+Path+" : "+Action+" : "+ImpSpecID+" : "+URL+" : "+Incremental+" : "+Comment
		continue
	print "Processing Row : "+FileMask+" : "+Path+" : "+Action+" : "+ImpSpecID+" : "+URL+" : "+Incremental+" : "+Comment

	if not os.path.exists(Path+'/Archive'):
		os.makedirs(Path+'/Archive')
	if not os.path.exists(Path+'/log'):
		os.makedirs(Path+'/log')

	os.chdir(Path)
	for f in glob.glob(FileMask):
		FileName = f
		print "Processing %s" % FileName
		BaseName = os.path.splitext(FileName)[0]
		Extension = os.path.splitext(FileName)[1]
		PGPOK = True
		if Extension == '.pgp':
			print "PGP Encryption Detected."
			FileName = BaseName
			#do GPG stuff
			import gnupg
			PDError = OVUtils.CheckPasswords(PasswordData,'GPG',['home','passphrase'])
			if len(PDError) > 0:
				Trace[Path+"/"+FileName+"-PGPDecryptErrors"] = PDError
				PGPOK = False
			else:
				gpg = gnupg.GPG(gnupghome=str(PasswordData['GPG']['home']))
				with open(f, 'rb') as ef:
					status = gpg.decrypt_file( ef, 
						passphrase=str(PasswordData['GPG']['passphrase']), 
						output=FileName)
				if not status.ok:
					Trace[Path+"/"+FileName+"-PGPDecryptErrors"] = status.status + '\n' + status.stderr
					PGPOK = False
			# Move PGP file to Archive folder
			shutil.move(Path+"/"+f,Path+"/Archive/"+f)

		if PGPOK:
			PDError = OVUtils.CheckPasswords(PasswordData,URL,['UserName','Password'])
			if len(PDError) > 0:
				Trace[Path+"/"+FileName+"-ImportErrors"] = PDError
			else:
				Imp = OVUtils.OVImport(
					website = URL,
					username = PasswordData[URL]["UserName"],
					password = PasswordData[URL]["Password"],
					impSpecId = ImpSpecID,
					action = Action,
					file = Path + "/" + FileName,
					comments = Comment + FileName,
					incremental = Incremental
					)
				if len(Imp.errors) > 0:
					Trace[Path+"/"+FileName+"-ImportErrors"] = str(Imp.errors)
					Trace[Path+"/"+FileName+"-Import"] = str(Imp.request.text)
				else:
					print "Success!  ProcessID: %d" % Imp.processId
			shutil.move(Path+"/"+FileName,Path+"/Archive/"+FileName)

if len(Trace) > 0:
	ErrorNotif("Errors on Automatic Imports")
