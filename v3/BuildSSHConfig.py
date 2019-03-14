#!/usr/bin/env python

import onevizion
import os
import shutil
import sys
import json


# Handle command arguments
import argparse
Description="""Connects to trackor.onevizion.com to get a list of "Server" Trackors and relevant information as to how to connect to said Server.  It then creates a section at the end of the local SSH Config file with updated information to make easy SSH connections.

For example, if I wanted to conenct to Acme's first web server, I would be able to type:

	ssh web01.acme

This script will create a default SSH Config file if one is not already present, but if one is present, it will preserve the one that is there and append the new Info.

A Tunnel definition a "tcnn" is required.  This establishes a tunnel connection for the Internal DNS to work for other connections.  It should look like this:

Host tcnn
  HostName cnn.onevizion.com
  User {TunnelUser}
  IdentityFile {TunnelKey}

"""
EpiLog = onevizion.ParameterExample
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,description=Description,epilog=EpiLog)
parser.add_argument(
	"-u", 
	"--user", 
	metavar="UserName", 
	help="User to use to login to app and web servers.", 
	default="ec2-user"
	)
parser.add_argument(
	"-k", 
	"--key", 
	metavar="Key File Path", 
	help="Path of Key File to use to login to app and web servers.", 
	default="~/.ssh/vendor.pem"
	)
parser.add_argument(
	"-U", 
	"--tunneluser", 
	metavar="UserName", 
	help="User to use to login to tunnel.", 
	default="tunnel"
	)
parser.add_argument(
	"-K", 
	"--tunnelkey", 
	metavar="Key File Path", 
	help="Path of Key File to use to login to tunnel.", 
	default="~/.ssh/depl"
	)
parser.add_argument("-p", "--parameters", metavar="ParametersFile", help="JSON file where parameters are stored.", default="Parameters.json")
args = parser.parse_args()
ParametersFile = args.parameters

WebUser = args.user
WebKeyFile = os.path.expanduser(args.key)
TunnelUser = args.tunneluser
TunnelKeyFile = os.path.expanduser(args.tunnelkey)

# FInd Home Folder of user
HomeFolder = os.path.expanduser('~')


# Load in Passwords from protected file.
ParameterData = onevizion.GetParameters(ParametersFile)

ServerListRequest = onevizion.Trackor(trackorType = 'server', paramToken = 'trackor.onevizion.com')
ServerListRequest.read(
		filters={
			'VQS_SVR_LOCATION':'AWS',
			'EC2_PRIVATE_DNS':'not null'
			}, 
		fields=[
			'TRACKOR_KEY',
			'EC2_PRIVATE_IP',
			'EC2_PRIVATE_DNS',
			'EC2_CLIENT_TAG'
			]
		)
if len(ServerListRequest.errors) > 0:
	print str(ServerListRequest.errors)
	quit()

# Put in a default header if the config file doens't exist
if not os.path.isfile(HomeFolder+'/.ssh/config'):
	if not os.path.exists(HomeFolder+'/.ssh'):
		os.makedirs(HomeFolder+'/.ssh')
		os.chmod(HomeFolder+'/.ssh', 0o700)
	with os.fdopen(os.open(HomeFolder+'/.ssh/config', os.O_WRONLY | os.O_CREAT, 0o700), 'w') as ConfigFile:
		ConfigFile.write("""### default for all ###
Host *
  ForwardAgent no
  ForwardX11 no
  ForwardX11Trusted yes
  Port 22
  Protocol 2
  ServerAliveInterval 60
  ServerAliveCountMax 30

Host tcnn
  HostName cnn.onevizion.com
  User {TunnelUser}
  IdentityFile {TunnelKey}

""".format(
	TunnelUser=TunnelUser,
	TunnelKey=TunnelKeyFile
	)
)

# backup old config file and create stub for new one
shutil.move(HomeFolder+'/.ssh/config',HomeFolder+'/.ssh/config.old')
with os.fdopen(os.open(HomeFolder+'/.ssh/config', os.O_WRONLY | os.O_CREAT, 0o700), 'w') as ConfigFile:
	ConfigFile.write("")
ConfigFile = open(HomeFolder+'/.ssh/config','a')

# Copy header part from old config file until you get the AutoGen demarker
with open(HomeFolder+'/.ssh/config.old','r') as OldFile:
	OldFileLines = OldFile.readlines()
for line in OldFileLines:
	if line == "### Start Generated Portion ###\n":
		break
	else:
		ConfigFile.write(line)
ConfigFile.write("### Start Generated Portion ###\n")
KeyList = []


# Add block for each Server in the list
for Server in ServerListRequest.jsonData:
	if Server["EC2_PRIVATE_DNS"].endswith('.ov.internal'):
		ShortName = Server["EC2_PRIVATE_DNS"][:-12]
	else:
		ShortName = Server["EC2_PRIVATE_DNS"]
	ConfigFile.write("""### {Tag}
Host {ShortName}
  HostName {PrivateDNS}
  User {WebUser}
  IdentityFile {WebKeyFile}
  Port 22
  ProxyCommand ssh -W %h:%p tcnn

""".format(
		Tag=Server["EC2_CLIENT_TAG"],
		ShortName=ShortName,
		PrivateDNS=Server["EC2_PRIVATE_DNS"],
		WebUser=WebUser,
		WebKeyFile=WebKeyFile
		)
	)

	KeyList.append(Server["EC2_PRIVATE_DNS"])
	KeyList.append(Server["EC2_PRIVATE_IP"])


# Remove the old key(s) from known_hosts
if os.path.isfile(HomeFolder+'/.ssh/known_hosts'):
	with open(HomeFolder+'/.ssh/known_hosts','rb') as f:
		KnownHostsLines = f.read().splitlines()

	KnownHosts = []
	NewKnownHosts = []
	for KnownHostLine in KnownHostsLines:
		KnownHost = {}
		Fields = KnownHostLine.split()
		KnownHost["KeyType"] = Fields[1]
		KnownHost["Key"] = Fields[2]
		KnownHost["Names"] = Fields[0].split(',')
		KnownHosts.append(KnownHost)
		Good = True
		for Name in KnownHost["Names"]:
			if Name in KeyList:
				Good = False
		if Good:
			NewKnownHosts.append(KnownHost)

	with open(HomeFolder+'/.ssh/known_hosts','wb') as f:
		for KnownHost in NewKnownHosts:
			f.write("{Names} {KeyType} {Key}\n".format(
				Names=",".join(KnownHost["Names"]),
				KeyType=KnownHost["KeyType"],
				Key=KnownHost["Key"]
				)
			)

	with open(HomeFolder+'/.ssh/known_hosts.old','wb') as f:
		for KnownHost in KnownHosts:
			f.write("{Names} {KeyType} {Key}\n".format(
				Names=",".join(KnownHost["Names"]),
				KeyType=KnownHost["KeyType"],
				Key=KnownHost["Key"]
				)
			)

