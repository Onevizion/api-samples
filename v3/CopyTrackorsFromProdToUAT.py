import onevizion

# Having a parameters file is just an easy way to not have you passwords stored in a script
PasswordData = onevizion.GetParameters('Parameters.json')
# This enables some automatic messaging within the onveizion library.  Can be 0, 1, or 2.  the higher the number, the more messages you get.
onevizion.Config["Verbosity"]=1


#Let's create some Trackor object for later use in the script
#Trackor object to get a list of Needed "Casees"
CaseRequest = onevizion.Trackor(
	trackorType = 'Case', 
	URL = 'trackor.onevizion.com', 
	userName=PasswordData["trackor.onevizion.com"]["UserName"], 
	password=PasswordData["trackor.onevizion.com"]["Password"]
	)
#Trackor object to pull individual "Cases" from Production
CasePuller = onevizion.Trackor(
	trackorType = 'Case', 
	URL = 'trackor.onevizion.com', 
	userName=PasswordData["trackor.onevizion.com"]["UserName"], 
	password=PasswordData["trackor.onevizion.com"]["Password"]
	)
#Trackor object to Push "Cases" into UAT
CaseMaker = onevizion.Trackor(
	trackorType = 'Case', 
	URL = 'uat-trackor.onevizion.com', 
	userName=PasswordData["uat-trackor.onevizion.com"]["UserName"], 
	password=PasswordData["uat-trackor.onevizion.com"]["Password"]
	)



# Since some of the fields are EFiles, let's first get a list, then do the records one at a time to 
# reduce the memory required for the total transfer and reduce the chances of failure.
CaseRequest.read(
	search="greater(C_CREATED_AT, 2017-12-19T00:00:00)", # We are pulling all "Cases" created after Dec 19th
	fields=[
		'TRACKOR_KEY'
		]
	)

for Case in CaseRequest.jsonData:
	# With each item in the list, we'll query for the complete  data and send it
	CasePuller.read(
		filters={
			"TRACKOR_KEY":Case['TRACKOR_KEY']
			} ,
		fields=[
			'TRACKOR_KEY',
			'C_OWNER_GROUP',
			'C_OWNER',
			'C_STATUS',
			'C_SEVERITY',
			'C_TYPE'
			]
		)
	#Now that we have the data, let's send it
	CaseMaker.create(
		fields=CasePuller.jsonData[0]
		)


