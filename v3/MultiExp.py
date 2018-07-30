import asyncio
import aiohttp
import onevizion

onevizion.Config["Verbosity"] = 1

ParameterData = onevizion.GetParameters('Parameters.json')

Message = onevizion.Message

async def GetExport(URL,userName,password,paramToken,trackorType,filters,fields,exportMode='CSV',delivery='File',waitPeriod=15):
	CSVText = None
	Exp = onevizion.Export(
		URL=URL,
		userName=userName,
		password=password,
		paramToken=paramToken,
		trackorType=trackorType,
		filters=filters,
		fields=fields,
		exportMode=exportMode,
		delivery=delivery
		)
	if len(Exp.errors) == 0:
		Message("Export Started. ProcessID: {ProcID}  Status: '{Status}'".format(ProcID=Exp.processId,Status=Exp.status),1)
		# Wait for Export to complete, poling every 60 seconds
		while Exp.status in ('PENDING', 'IN_QUEUE', 'RUNNING'):
			await asyncio.sleep(waitPeriod)
			Exp.getProcessStatus()
			Message("Export status is '{Status}' for ProcessID: {ProcID}".format(Status=Exp.status,ProcID=Exp.processId),1)
		if Exp.status not in ('EXECUTED','EXECUTED_WITHOUT_ERRORS'):
			# Log Error
			Message("Export failed with status '{Status}' for ProcessID: {ProcID}".format(Status=Exp.status,ProcID=Exp.processId))
		else:
			CSVText = Exp.getFile()
	return CSVText


loop = asyncio.get_event_loop()
tasks = []

tasks.append(
	asyncio.ensure_future(
			GetExport(
				paramToken='trackor.onevizion.com',
				trackorType='Website',
				filters={'VQS_WEB_ACTIVE':1},
				fields=[
					"TRACKOR_KEY",
					"VQS_WEB_DBSCHEMA",
					"WEB_MONITOR_USER",
					"WEB_MONITOR_PASSWORD",
					"Database.DB_CONNECTION_STRING",
					"WEB_MONITORING_ENABLED",
					"WEB_MONITORS_DISABLED"
					]
				)
		)
	)
tasks.append(
	asyncio.ensure_future(
			GetExport(
				paramToken='trackor.onevizion.com',
				trackorType='Website',
				filters={'VQS_WEB_ACTIVE':1},
				fields=[
					"TRACKOR_KEY",
					"VQS_WEB_DBSCHEMA",
					"WEB_MONITOR_USER",
					"WEB_MONITOR_PASSWORD",
					"Database.DB_CONNECTION_STRING",
					"WEB_MONITORING_ENABLED",
					"WEB_MONITORS_DISABLED"
					]
				)
		)
	)
tasks.append(
	asyncio.ensure_future(
			GetExport(
				paramToken='trackor.onevizion.com',
				trackorType='Website',
				filters={'VQS_WEB_ACTIVE':1},
				fields=[
					"TRACKOR_KEY",
					"VQS_WEB_DBSCHEMA",
					"WEB_MONITOR_USER",
					"WEB_MONITOR_PASSWORD",
					"Database.DB_CONNECTION_STRING",
					"WEB_MONITORING_ENABLED",
					"WEB_MONITORS_DISABLED"
					]
				)
		)
	)


loop.run_until_complete(asyncio.wait(tasks))
loop.close()


