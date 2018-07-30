import json
import datetime
import operator
import onevizion

# Handle command arguments
import argparse
Description="""Email Patch Notes to the PatchNotes mailing list.
"""
EpiLog = onevizion.PasswordExample + """\n\n
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description=Description,epilog=EpiLog)
parser.add_argument("Version", help="Version to Release")
parser.add_argument("PreviousVersion", help="Previous Version released last")
parser.add_argument(
	"-i",
	"--includeprev",
	action='count',
	default=0,
	help="Include Changes from Previous build."
	)
parser.add_argument("-P", "--product", metavar="Product", help="Product Name for the Version list.", default="OneVizion")
parser.add_argument("-t", "--to", help="Comma Sepearated list of email addresses to send this email 'To'", default="")
parser.add_argument("-p", "--parameters", metavar="ParametersFile", help="JSON file where parameters are stored.", default="Parameters.json")
parser.add_argument(
	"-v",
	"--verbose",
	action='count',
	default=0,
	help="Print extra debug messages and save to a file. Attach file to email if sent."
	)
args = parser.parse_args()
PasswordsFile = args.parameters
Product = args.product
ThisVersion = args.Version
Versions = [args.Version]
PreviousVersion = args.PreviousVersion

if len(args.to) > 0:
	PassedTo=args.to.split(",")
else:
	PassedTo=[]
# Load in Passwords from protected file.
PasswordData = onevizion.GetParameters(PasswordsFile)
onevizion.Config["Verbosity"]=args.verbose
onevizion.Config["SMTPToken"]="SMTP"
Message=onevizion.Message
# Make sure Passwordsfile has correct sections
PDError = (
	onevizion.CheckPasswords(PasswordData,'SMTP',['Server','Port','UserName','Password','To']),
	",\n",
	onevizion.CheckPasswords(PasswordData,'trackor.onevizion.com',['UserName','Password'])
	)
if len(PDError) > 6:
	print PDError
	quit()


# Build up Log for future use if needed
from collections import OrderedDict
Trace = onevizion.Config["Trace"]
Issues = OrderedDict()


def Notif (Title,Body,To):
	"""Sends Mail notifying if an error occurs"""

	msg = onevizion.EMail()
	#msg.passwordData(PasswordData["SMTP"])
	if type(To) is list:
		msg.to=To
	else:
		msg.to = [To]
	msg.subject = Title
	msg.message = Body

	msg.info.update(Trace)

	msg.sendmail()

	quit()

def VersionInfo(GivenVersion):
	ThisVersion={}
	if GivenVersion[-3:][:-1] == "RC":
		QueryVersion = GivenVersion[:-4]
		VerType = 'UAT'
	else:
		QueryVersion = GivenVersion
		VerType = 'Production'
	# Find the Release Date for Prod Version
	VersionRequest = onevizion.Trackor(
		trackorType = 'Version',
		URL = 'trackor.onevizion.com',
		userName=PasswordData["trackor.onevizion.com"]["UserName"],
		password=PasswordData["trackor.onevizion.com"]["Password"]
		)
	VersionRequest.read(
		filters={
			"TRACKOR_KEY":QueryVersion,
			"Product.TRACKOR_KEY":Product
			} ,
		fields=[
			'TRACKOR_KEY',
			'VER_REL_DATE'
			]
		)
	if len(VersionRequest.errors) == 0:
		ThisVersion['Version'] = VersionRequest.jsonData[0]['TRACKOR_KEY']
		ThisVersion['ReleaseDate'] = datetime.datetime.strptime(VersionRequest.jsonData[0]['VER_REL_DATE'],'%Y-%m-%d')
		ThisVersion['Type'] = VerType

	return ThisVersion

def VersionSplit(ThisVersion):
	VersionBreak=ThisVersion.split(".")
	VersionParts=[]
	VersionParts.append(int(VersionBreak[0]))
	VersionParts.append(int(VersionBreak[1]))
	RelVer = VersionBreak[2].split('-RC')
	VersionParts.append(int(RelVer[0]))
	if len(RelVer) == 2:
		VersionParts.append(int(RelVer[1]))
	return VersionParts

def GetVersionsList(VersionsStr,VersionDate):
	VersionRequest = onevizion.Trackor(
		trackorType = 'Version',
		paramToken = 'trackor.onevizion.com'
		)
	VersionRequest.read(
		search="equal(TRACKOR_KEY, 8.*) and equal(Product.TRACKOR_KEY, OneVizion) and is_not_null(VER_REL_DATE)",
		fields=[
			'TRACKOR_KEY',
			'VER_REL_DATE'
			],
		sort={'TRACKOR_KEY':'asc'}
		)

	AllVers=[]
	for Version in VersionRequest.jsonData:
		AllVers.append(VersionSplit(Version['TRACKOR_KEY']))
		VersionDate[Version['TRACKOR_KEY']]=Version['VER_REL_DATE']

	AllVers.sort(key=operator.itemgetter(0,1,2))
	Message(json.dumps(AllVers,indent=2),2)

	for Version in AllVers:
		if "%d.%d.%d"%(Version[0],Version[1],Version[2]) not in VersionsStr:
			VersionsStr.append("%d.%d.%d"%(Version[0],Version[1],Version[2]))

	Message(json.dumps(VersionsStr,indent=2), 2)



NewerVersion=VersionInfo(ThisVersion)
OlderVersion=VersionInfo(PreviousVersion)

VersionList=OrderedDict()


AllVersions=[]
VersionDates={}
GetVersionsList(AllVersions,VersionDates)

#Message(json.dumps(AllVersions,indent=2))
#Message(json.dumps(VersionDates,indent=2))



# Break out an ordered list of only the needed version updates.
NeededVersions = []
if args.includeprev > 0:
	PrevBuffer = 0
else:
	PrevBuffer = 1
for i in range(AllVersions.index(OlderVersion['Version'])+PrevBuffer,AllVersions.index(NewerVersion['Version'])+1):
	NeededVersions.append(AllVersions[i])
Message("{NumVers} versions to list.".format(NumVers=len(NeededVersions)))
Message(json.dumps(NeededVersions,indent=2), 1)



NeededVersions.reverse()
for Ver in NeededVersions:
	VersionList[Ver] = datetime.datetime.strptime(VersionDates[Ver],'%Y-%m-%d')

Versions=[]

# Get Issues for any Versions attached to this Email
IssueList = onevizion.Trackor(
	trackorType = 'Issue',
	URL = 'trackor.onevizion.com',
	userName=PasswordData["trackor.onevizion.com"]["UserName"],
	password=PasswordData["trackor.onevizion.com"]["Password"]
	)
for Version,RelDate in VersionList.items():
	Ver={}
	IssueList.read(
		filters={
			"Version.TRACKOR_KEY":Version,
			"Product.TRACKOR_KEY":"OneVizion",
			"VQS_IT_DONT_INCLUDE_IN_REL_NOTES":"0"
			} ,
		fields=[
			'TRACKOR_KEY',
			'VQS_IT_XITOR_NAME',
			'VQS_IT_RELEASE_NOTES',
			'TRACKOR_CLASS_ID'
			],
		sort={
			'TRACKOR_CLASS_ID':'desc',
			'TRACKOR_KEY':'asc'
			}
		)
	if len(IssueList.errors) > 0:
		Notif('Patch Notes Failed','Patch Notes Failed.','development@onevizion.com')
	else:
		Ver['Version']=Version
		Ver['ReleaseDate']=RelDate
		Issues=[]
		for Issue in IssueList.jsonData:
			Iss={}
			Iss['IssueID']=Issue['TRACKOR_KEY']
			Iss['Summary']=Issue['VQS_IT_XITOR_NAME']
			Iss['Notes']=Issue['VQS_IT_RELEASE_NOTES']
			Iss['IssueType']=Issue['TRACKOR_CLASS_ID']
			Issues.append(Iss)
		Ver['Issues']=Issues
	if Ver != {}:
		Versions.append(Ver)


# Send The Email since everthing is successful
Title = "OneVizion "+ThisVersion+" deployed in "+NewerVersion['Type']
Body = "OneVizion "+ThisVersion+" deployed in "+NewerVersion['Type']
if NewerVersion['Type'] == 'UAT':
	Body = Body+", we are planing production release on "+NewerVersion['ReleaseDate'].strftime('%Y-%m-%d')+"."
else:
	Body = Body+"."
Body = Body+" Following is list of changes since "+OlderVersion['Version']+" version:"

for Version in Versions:
	Body += "\n\n{Version}:  {ReleaseDate}\n================================================".format(
		Version=Version['Version'],
		ReleaseDate=Version['ReleaseDate'].strftime('%Y-%m-%d')
		)
	IssueType = ""
	for Issue in Version['Issues']:
		if IssueType != Issue['IssueType']:
			IssueType = Issue['IssueType']
			Body += "\n{IssueType}s:\n===========\n".format(IssueType=IssueType)
		Body += "\n{IssueID}:  {Summary}\t\n".format(
			IssueID=Issue['IssueID'],
			Summary=Issue['Summary']
			)
		if Issue['Notes'] is not None:
			Body += "{Notes}\n".format(Notes=Issue['Notes'])
		#else:
			Body += '\n'


if len(PassedTo) == 0:
	PassedTo = PasswordData["SMTP"]["To"]
Notif(
	Title=Title,
	Body=Body,
	To=PassedTo
	)

