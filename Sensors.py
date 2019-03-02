import time
import datetime
from grovepi import *
import threading
import paho.mqtt.client as mqtt
import math
import grove_rgb_lcd as glcd

##sensor determination
led = 2
dht_sensor_port = 3
motionsensor = 4

glcd.setRGB(0, 0, 0)
glcd.setText("")

##Instruction variables
dhtInstruction = -1
ledInstruction = -1
motionSensorInstruction = -1
lcdInstruction = ""
lcdEndOfRun = 0
injectError = 0

#subsription topics
topicErrorOut = "sensors/error/outbound/"
topicErrorIn = "sensors/error/inbound"
topicTemp = "sensors/instruction/temp"
topicLed = "sensors/instruction/led"
topicMotsen = "sensors/instruction/motsen"
topicLCD = "sensors/instruction/lcd"
topicValue = "sensors/value/"
topicInjError = "sensors/injecterror"


##Pinmode for LED light
pinMode(led, "OUTPUT")

##MQTT INFO
#server info
server     = ""
port       = 12345

#user info
username   = ""
password   = ""

#create mqttclient
client = mqtt.Client()
client.username_pw_set(username, password)



##GLOBAL VARIABLES - GETTERS / SETTERS##

def getCurrentTime():						#getting current time in seconds
	return int(round(time.time()))

def getDhtInstruction():
	return dhtInstruction
	
def setDhtInstruction(value):
	global dhtInstruction
	dhtInstruction = value
	
def setledInstruction(value):
	global ledInstruction
	ledInstruction = value

def getledInstruction():
	return ledInstruction
	
def setmotionSensorInstruction(value):
	global motionSensorInstruction
	motionSensorInstruction = value

def getmotionSensorInstruction():
	return motionSensorInstruction

def setlcdInstruction(value):
	global lcdInstruction
	lcdInstruction = value

def getlcdInstruction():
	return lcdInstruction

def setLCDRun(value):
	global lcdEndOfRun
	lcdEndOfRun = value
	
def getLCDRun():
	return lcdEndOfRun
	
def setInjError(value):
	global injectError
	injectError = value
	
def getInjError():
	return injectError


##INCOMING INSTRUCTION VALIDATION - CALLED FROM CONTROL LOOP##

def validate(input):
	try:
		if type(input) is int:
			return True
		else:
			return False
	except ValueError:
		return False

##reports error when value is < -1 or is not int
def validateInstruction(payload):
	isValid = True
	errorMessage = ""
	try:
		if not validate(int(payload)):
			isValid = False
			errorMessage = errorMessage + "not int: " + str(payload)
		if int(payload) < -1:
			isValid = False
			errorMessage = errorMessage + "value range:" + str(payload)
	except ValueError:
		isValid = False
		errorMessage = errorMessage + "unknown type:" + str(payload)
	if not isValid:
		publish(topicErrorIn, errorMessage)
	return isValid

##VALIDATE OUTPUT TO HANDLE ERRORS
##happens in many layers, system is capturing deviation
##messages generated will go to error queue and sensor is given instruction -1
##which will turn polling off
def validateOutput(sensor, msg):
	isValid = True
	errMsg = ""
	try:							#ERROR HANDLING
		if  msg != "...":
			if validate(int(msg)):
				if sensor=="temp" or sensor=="hum" or sensor=="motsen" or sensor=="lcd":
					if int(msg) == 0:
						isValid = False
						errMsg = "no reading"
			else:
				isValid = False
				errMsg = "unknown value"
	except ValueError:				#ERROR HANDLING
		isValid = False
		errMsg = "unknown value"
	if isValid:
		publish(topicValue+sensor, msg)
	else:
		publish(topicErrorOut+sensor, errMsg)
		if sensor=="temp" or sensor=="hum":
			setDhtInstruction(-1)
		if sensor=="motsen":
			setmotionSensorInstruction(-1)
		if sensor=="lcd":
			setlcdInstruction(-1)
	
##MQTT CALLBACK FUNCTIONS##
# Message when client is connected
def connected(client, userdata, flags, rc):
    print("Connected to service: " + mqtt.connack_string(rc))

# Message when disconnected
def disconnected(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnect")

# Message when subscribed
def subscribed(client, userdata, mid, granted_qos):
	print("Subscribed to topic: " + topic1)
	
def published(client,userdata,result):             #create function for callback
    print("data published \n")

# Message arrived
def messagereceived(client, userdata, msg):
	print("Message received: " + msg.topic + " " + str(msg.payload))
	if msg.topic.lower() == topicTemp:		
		setDhtInstruction(msg.payload)
	elif msg.topic.lower() == topicLed:
		setledInstruction(msg.payload)
	elif msg.topic.lower() == topicMotsen:
		setmotionSensorInstruction(msg.payload)
	elif msg.topic.lower() == topicLCD:
		setlcdInstruction(msg.payload)
	elif msg.topic.lower() == topicInjError:
		setInjError(msg.payload)
	else:		
		publish(topicError, "/Unknown topic:" + msg.topic)

##MQTT START + INFINITE LOOP FOR NEW MESSAGES##		
def mqttStart():
	#messaging
	client.on_connect    = connected
	client.on_disconnect = disconnected
	client.on_subscribe  = subscribed
	client.on_message    = messagereceived
	client.on_publish = published

	#connect and susbscribe
	client.connect(server, port)
	client.subscribe(topicTemp)
	client.subscribe(topicLed)
	client.subscribe(topicMotsen)
	client.subscribe(topicLCD)
	client.subscribe(topicInjError)

	#loop for messages
	client.loop_forever()

##MQTTPUBLISH RUNNING ON SEPARATE "PUBLISH" THREAD##
def publish(topic, message):
	threadPublish = threading.Thread(target = client.publish, args=(topic, message))
	threadPublish.start()
	

##SENSOR MANAGEMENT	
def getTemp():								#getting temperature value from dht sensor
	dht_sensor_port = 3
	[temp, hum] = dht(dht_sensor_port, 0)	
	return temp
	
def getHumidity():							#getting humidity value from dht sensor
	dht_sensor_port = 3
	[temp, hum] = dht(dht_sensor_port, 0)
	return hum

def setLCDText(text, sensor):	#Set text on LCD screen, protected by except IOError in case thread runs out of memory
	try:
		glcd.setRGB(0, 0, 255)
		glcd.setText(text[:33])
		time.sleep(3)	
		glcd.setText("")
		time.sleep(.5)
		glcd.setRGB(0, 0, 0)
		validateOutput(sensor, 1)
		setlcdInstruction("")
		setLCDRun(0)
	except IOError:
		client.publish(topicError+sensor, "IO Error Reported")
		print "IO Error"

##LISTENER RUNNING ON SEPARATE "LISTENER" THREAD#
threadListen = threading.Thread(target=mqttStart)
threadListen.start()

##Loop timers#
dhtTimer = getCurrentTime() + getDhtInstruction()
ledTimer = getCurrentTime() + getledInstruction()
motsenTimer = getCurrentTime() + getmotionSensorInstruction()

##Sensor definition, publishing purposes
snsTemp = "temp"
snsHum = "hum"
snsLed = "led"
snsMotsen = "motsen"
snsLCD = "lcd"

##CONTROL - MAIN LOOP##
##Below is infinite loop functioning on timing principle. Idea is to turn sensors on / off by receiving 
##instructions from Android device. Instruction comes as integer values and is either 0 or >0.
##Instruction acts as sample timer. Instruction 1 will turn sensor on and send sample back in 1 second interval.
##Instruction 0 will turn off sensor immediately.
##formula is simple: timerIndex = currenttime + instruction. If currenttime > then timeIndex = sampling start. timeIndex is updated on each successful sampling
##Logic is linear, no "time.sleep()" is used therefore it can run on main thread.
##Each sensor has if and elif. if instruction > 0 has been received, if yes, validate input and update global timeindex to enter the if
##elif catpures instruction to turn off sensor (0) and is actioned immediately
## NB! Below can look repetitive BUT couldn't be separated into a single function because although similar, each sensor has separate logic path.

while True:
	try:																																				
		if int(getDhtInstruction()) > 0 and validateInstruction(getDhtInstruction()) and getCurrentTime() > dhtTimer:		#DHT SENSOR CONTROL START
			validateOutput(snsTemp, getTemp())
			validateOutput(snsHum, getHumidity())
			dhtTimer = getCurrentTime() + int(getDhtInstruction())					
		elif int(getDhtInstruction()) == 0:
			validateOutput(snsTemp, "...")
			validateOutput(snsHum, "...")
			setDhtInstruction(-1)																		#DHT SENSOR CONTROL END								
		if int(getledInstruction()) > 0 and validateInstruction(getledInstruction()) and getCurrentTime() > ledTimer:						#LED SENSOR CONTROL START
			sensor = "led"
			digitalWrite(led, 1)
			validateOutput(snsLed, digitalRead(led))
			ledTimer = getCurrentTime() + int(getledInstruction())					
		elif int(getledInstruction()) == 0:
			sensor = "led"
			digitalWrite(led, 0)
			validateOutput(snsLed, digitalRead(led))
			setledInstruction(-1)																			#LED SENSOR CONTROL END
		if int(getmotionSensorInstruction()) > 0 and validateInstruction(getmotionSensorInstruction()) and getCurrentTime() > motsenTimer:	#ULTRASONIC SENSOR CONTROL START
			validateOutput(snsMotsen, ultrasonicRead(motionsensor))
			motsenTimer = getCurrentTime() + int(getmotionSensorInstruction())					
		elif int(getmotionSensorInstruction()) == 0:
			validateOutput(snsMotsen, "...")
			setmotionSensorInstruction(-1)		#ULTRASONIC SENSOR CONTROL END
		if len(getlcdInstruction()) > 0 and lcdEndOfRun == 0:							#LCD CONTROL START 
			setLCDRun(1)
			threadLCD = threading.Thread(target=setLCDText, args=(getlcdInstruction(),snsLCD))		
			threadLCD.start() #LCD CONTROL END
		if int(getInjError()) == 1:
			setInjError(0)
			validateOutput(snsTemp, "RANDOMSTRING")
			validateOutput(snsHum, "0")
			validateOutput(snsLed, "RANDOMSTRING")
			validateOutput(snsMotsen, "ABC")
			validateInstruction("ABC")
			validateInstruction("-100000")
			validateInstruction("RANDOMSTRING")
	except KeyboardInterrupt:
		digitalWrite(led, 0)
		threadListen.join()
		threadLCD.join()
		client.disconnect()
		break
	except IOError:
		digitalWrite(led, 0)
		print "Error"


