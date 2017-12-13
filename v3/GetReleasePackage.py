#!/usr/bin/env python
import pysftp
import onevizion
import json
import os
import operator
from collections import OrderedDict


# Handle command arguments
import argparse
Description="""Compiles a complete upgrade package for getting a OneVizion system from a given current version to a desired New version.  It does so by using the OneVizion Releases SFTP site given to a client by a OneVizion administrator.
"""
EpiLog = onevizion.PasswordExample + """\n\n
"""
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description=Description,epilog=EpiLog)
parser.add_argument(
	"-V",
	"--version", 
	metavar="WantedVersion", 
	help="Version to be copied to SFTP", 
	default=""
	)
parser.add_argument(
	"-C",
	"--currentversion", 
	metavar="CurrentVersion", 
	help="Current Version to be compared for scripts to be copied to SFTP", 
	default="DEFAULT"
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
ParamtersFile = args.parameters
ThisVersion = args.version
CurrentVersion = args.currentversion

#Set some standard OneVizion Parameters
onevizion.Config["Verbosity"]=args.verbose
onevizion.Config["SMTPToken"]="SMTP"
Params = onevizion.GetParameters(ParamtersFile)
Message = onevizion.Message
Trace = onevizion.Config["Trace"]


def VersionSplit(ThisVersion):
	""" 
	Splits up a String Version number (e.g: '8.59.10') into a numerical array for numeric sorting.
	"""
	VersionBreak=ThisVersion.split(".")
	VersionParts=[]
	VersionParts.append(int(VersionBreak[0]))
	VersionParts.append(int(VersionBreak[1]))
	RelVer = VersionBreak[2].split('-RC')
	VersionParts.append(int(RelVer[0]))
	if len(RelVer) == 2:
		VersionParts.append(int(RelVer[1]))
	return VersionParts


# Get the SFTP login from a local Parameters.json file
sftpHost = Params['ReleaseSFTP']['Host']
sftpUserName = Params['ReleaseSFTP']['UserName']
sftpPassword = Params['ReleaseSFTP']['Password']


# Get list of Folders for releases to extrapalate all releases given.
Message("Connecting to %s"%(sftpHost))
with pysftp.Connection(sftpHost, username=sftpUserName, password=sftpPassword) as sftp:
	sftp.chdir("releases")
	ReleasesList = sftp.listdir()
Message(json.dumps(ReleasesList,indent=2),2)

# Build List of Versions from sftp directory and sort numerically to get proper order
Versions = []
for Version in ReleasesList:
	Versions.append(VersionSplit(Version))
Versions.sort(key=operator.itemgetter(0,1,2))

# Rebuild the now numerically ordered vesions list back into a lit of Strings.
VersionsStr = []
for Version in Versions:
	VersionsStr.append("%d.%d.%d"%(Version[0],Version[1],Version[2]))
Message(json.dumps(VersionsStr,indent=2), 2)

# Break out an ordered list of only the needed version updates.
NeededVersions = []
for i in range(VersionsStr.index(CurrentVersion)+1,VersionsStr.index(ThisVersion)+1):
	NeededVersions.append(VersionsStr[i])
Message("{NumVers} upgrades to apply.".format(NumVers=len(NeededVersions)))
Message(json.dumps(NeededVersions,indent=2), 1)


#Build a local folder in which to place the downloaded files
VersionRootFolder = "{CurVer}-to-{ThisVer}".format(CurVer=CurrentVersion,ThisVer=ThisVersion)
if not os.path.exists(VersionRootFolder):
    os.makedirs(VersionRootFolder)
if not os.path.exists(VersionRootFolder+"/db"):
    os.makedirs(VersionRootFolder+"/db")
if not os.path.exists(VersionRootFolder+"/db/rollback"):
    os.makedirs(VersionRootFolder+"/db/rollback")

# Download all the needed script files and executables
Message("Downloading files to folder {RootDir}".format(RootDir=VersionRootFolder))
with pysftp.Connection(sftpHost, username=sftpUserName, password=sftpPassword) as sftp:
	for Ver in NeededVersions:
		Message("Downloading Scripts for Version {Ver}".format(Ver=Ver),1)
		sftp.get_d(
			remotedir="releases/{Ver}/db".format(Ver=Ver),
			localdir=VersionRootFolder+"/db"
			)
		sftp.get_d(
			remotedir="releases/{Ver}/db/rollback".format(Ver=Ver),
			localdir=VersionRootFolder+"/db/rollback"
			)
	Message("Downloading Executables for Version {Ver}".format(Ver=ThisVersion),1)
	sftp.get_d(
		remotedir="releases/{Ver}".format(Ver=ThisVersion),
		localdir=VersionRootFolder
		)
Message("Downloads Complete.")










