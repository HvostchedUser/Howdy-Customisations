# PAM interface in python, launches compare.py

# Import required modules
import subprocess
import os
import glob
import syslog
import random
import time

# pam-python is running python 2, so we use the old module here
import ConfigParser

# Read config from disk
config = ConfigParser.ConfigParser()
config.read(os.path.dirname(os.path.abspath(__file__)) + "/config.ini")


def doAuth(pamh):
	"""Starts authentication in a seperate process"""
	
	#immediately authentificate despite the result
	#pamh.conversation(pamh.Message(pamh.PAM_TEXT_INFO, "LOLLOL"))
	#time.sleep(1)
	#return pamh.PAM_SUCCESS
	
	# Abort is Howdy is disabled
	if config.getboolean("core", "disabled"):
		return pamh.PAM_AUTHINFO_UNAVAIL

	# Abort if we're in a remote SSH env
	if config.getboolean("core", "ignore_ssh"):
		if "SSH_CONNECTION" in os.environ or "SSH_CLIENT" in os.environ or "SSHD_OPTS" in os.environ:
			return pamh.PAM_AUTHINFO_UNAVAIL

	# Abort if lid is closed
	if config.getboolean("core", "ignore_closed_lid"):
		if any("closed" in open(f).read() for f in glob.glob("/proc/acpi/button/lid/*/state")):
			return pamh.PAM_AUTHINFO_UNAVAIL

	# Alert the user that we are doing face detection
	if config.getboolean("core", "detection_notice"):
		listt=["Smile!", "Who are you?","Detecting faces..."]
		time.sleep(0.5)
		pamh.conversation(pamh.Message(pamh.PAM_TEXT_INFO, random.choice(listt)))

	
	syslog.syslog(syslog.LOG_AUTH, "[HOWDY] Attempting facial authentication for user " + pamh.get_user())

	# Run compare as python3 subprocess to circumvent python version and import issues
	status = subprocess.call(["/usr/bin/python3", os.path.dirname(os.path.abspath(__file__)) + "/compare.py", pamh.get_user()], stdout=open(os.devnull, 'wb'))
	#status = compare_inside.mainCall(["",pamh.get_user()])

	
	
	# Status 10 means we couldn't find any face models
	
	if status == 10:
		if not config.getboolean("core", "suppress_unknown"):
			pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "No face model known"))

		syslog.syslog(syslog.LOG_AUTH, "[HOWDY] Failure, no face model known")
		return pamh.PAM_USER_UNKNOWN

	# Status 11 means we exceded the maximum retry count
	elif status == 11:
		pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "I don't know you, enter the password please"))
		syslog.syslog(syslog.LOG_AUTH, "[HOWDY] Failure, timeout reached")
		return pamh.PAM_AUTH_ERR

	# Status 12 means we aborted
	elif status == 12:
		syslog.syslog(syslog.LOG_AUTH, "[HOWDY] Failure, general abort")
		return pamh.PAM_AUTH_ERR

	# Status 13 means the image was too dark
	elif status == 13:
		syslog.syslog(syslog.LOG_AUTH, "[HOWDY] Failure, image too dark")
		pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "Face detection image too dark"))
		return pamh.PAM_AUTH_ERR
	# Status 0 is a successful exit
	elif status == 0:
		# Show the success message if it isn't suppressed
		if not config.getboolean("core", "no_confirmation"):
			
			listt=["Hello, {}","User {} is recognized","You are {}, nice","You look good, {}"]
			pamh.conversation(pamh.Message(pamh.PAM_TEXT_INFO, random.choice(listt).format(pamh.get_user())))
			time.sleep(0.5)

		syslog.syslog(syslog.LOG_AUTH, "[HOWDY] Login approved")
		return pamh.PAM_SUCCESS

	# Otherwise, we can't discribe what happend but it wasn't successful
	#pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "Unknown error: " + str(status)))
	pamh.conversation(pamh.Message(pamh.PAM_ERROR_MSG, "Turn on the camera or enter the password"))
	syslog.syslog(syslog.LOG_AUTH, "[HOWDY] Failure, unknown error" + str(status))
	return pamh.PAM_SYSTEM_ERR


def pam_sm_authenticate(pamh, flags, args):
	"""Called by PAM when the user wants to authenticate, in sudo for example"""
	return doAuth(pamh)


def pam_sm_open_session(pamh, flags, args):
	"""Called when starting a session, such as su"""
	return doAuth(pamh)


def pam_sm_close_session(pamh, flags, argv):
	"""We don't need to clean anyting up at the end of a session, so returns true"""
	return pamh.PAM_SUCCESS


def pam_sm_setcred(pamh, flags, argv):
	"""We don't need set any credentials, so returns true"""
	return pamh.PAM_SUCCESS
