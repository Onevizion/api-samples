import json
import datetime
import onevizion

# Handle command arguments
import argparse
Description="""Email Patch Notes to the PatchNotes mailing list.

It does this by getting a list of Versions (from the Version trackor) between the Version you give it, and the PreviousVersion that you give it, then taking a list of those Versions and getting a list of Issues (from the Issue Trackor) for each to get a complete list of changes between those versions.
"""
EpiLog = onevizion.PasswordExample + """\n\n
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description=Description,epilog=EpiLog)
parser.add_argument("Version", help="Version to Release")
parser.add_argument("PreviousVersion", help="Previous Version released last")
parser.add_argument(
	"-f", 
	"--filter", 
	metavar="filter", 
	help="Filter to add to Version ID.", 
	default=""
	)
parser.add_argument(
	"-i", 
	"--includeprev", 
	action='count', 
	default=0, 
	help="Include Changes from Previous build."
	)
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
PasswordsFile = args.passwords
ThisVersion = args.Version
Versions = [args.Version]
PreviousVersion = args.PreviousVersion
VersionFilter= args.filter

if len(args.to) > 0:
	PassedTo=args.to.split(",")
else:
	PassedTo=[]
# Load in Passwords from protected file.
PasswordData = onevizion.GetParameters(PasswordsFile)
onevizion.Config["Verbosity"]=args.verbose
onevizion.Config["SMTPToken"]="SMTP"
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


def Notif (Title,Message,To):
	"""Sends Mail notifying if an error occurs"""

	msg = onevizion.EMail()
	#msg.passwordData(PasswordData["SMTP"])
	if type(To) is list:
		msg.to=To
	else:
		msg.to = [To]
	msg.subject = Title
	msg.message = Message
	
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
			"TRACKOR_KEY":QueryVersion
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

NewerVersion=VersionInfo(ThisVersion)
OlderVersion=VersionInfo(PreviousVersion)

VersionList=OrderedDict()

VersionRequest = onevizion.Trackor(
	trackorType = 'Version', 
	URL = 'trackor.onevizion.com', 
	userName=PasswordData["trackor.onevizion.com"]["UserName"], 
	password=PasswordData["trackor.onevizion.com"]["Password"]
	)

Search = 'less_or_equal(VER_REL_DATE,{NewerVersionDate})'.format(
		NewerVersionDate=NewerVersion['ReleaseDate'].strftime('%Y-%m-%d')
		)
if args.includeprev > 0:
	Search += ' and greater_or_equal(VER_REL_DATE, {OlderVersionDate})'.format(
		OlderVersionDate=OlderVersion['ReleaseDate'].strftime('%Y-%m-%d')
		)
else:
	Search += ' and greater(VER_REL_DATE, {OlderVersionDate})'.format(
		OlderVersionDate=OlderVersion['ReleaseDate'].strftime('%Y-%m-%d')
		)
if len(VersionFilter) > 0:
	Search += ' and equal(TRACKOR_KEY, {VersionFilter})'.format(
		VersionFilter=VersionFilter
		)
VersionRequest.read(
	search=Search,
	fields=[
		'TRACKOR_KEY',
		'VER_REL_DATE'
		],
	sort={'VER_REL_DATE':'desc','TRACKOR_KEY':'desc'}
	)
if len(VersionRequest.errors) > 0:
	Notif('Patch Notes Failed','Patch Notes Failed.','development@onevizion.com')
else:
	for Ver in VersionRequest.jsonData:
		VersionList[Ver['TRACKOR_KEY']] = datetime.datetime.strptime(Ver['VER_REL_DATE'],'%Y-%m-%d')

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
				"VQS_IT_DONT_INCLUDE_IN_REL_NOTES":"0"
				} ,
			fields=[
				'TRACKOR_KEY',
				'VQS_IT_XITOR_NAME',
				'VQS_IT_RELEASE_NOTES'
				]
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
				Issues.append(Iss)
			Ver['Issues']=Issues
		if Ver != {}:
			Versions.append(Ver)


	# Send The Email since everthing is successful			
	Title = "OneVizion "+ThisVersion+" deployed in "+NewerVersion['Type']
	Message = "OneVizion "+ThisVersion+" deployed in "+NewerVersion['Type']
	if NewerVersion['Type'] == 'UAT':
		Message = Message+", we are planing production release on "+NewerVersion['ReleaseDate'].strftime('%Y-%m-%d')+"."
	else:
		Message = Message+"."
	Message = Message+" Following is list of changes since "+OlderVersion['Version']+" version:"

	for Version in Versions:
		Message += "\n\n{Version}:  {ReleaseDate}\n================================================".format(
			Version=Version['Version'],
			ReleaseDate=Version['ReleaseDate'].strftime('%Y-%m-%d')
			)
		for Issue in Version['Issues']:
			Message += "\n{IssueID}:  {Summary}\n".format(
				IssueID=Issue['IssueID'],
				Summary=Issue['Summary']
				)
			if Issue['Notes'] is not None:
				Message += "{Notes}\n".format(Notes=Issue['Notes'])
			#else:
				Message += '\n'


	if len(PassedTo) == 0:
		PassedTo = PasswordData["SMTP"]["To"]
	Notif(
		Title=Title,
		Message=Message,
		To=PassedTo
		)
