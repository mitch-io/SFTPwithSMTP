import pysftp
import os
import smtplib
from datetime import datetime
import configparser
import sys

# read in varibles from config file
cfg = configparser.ConfigParser()
cfg.read('SFTP.ini') # file name of config file - will look in working directory
# SFTP varibles
myHostname = cfg.get('SFTP', 'myHostname')
myUsername = cfg.get('SFTP', 'myUsername')
myPassword = cfg.get('SFTP', 'myPassword')
rDirectory = cfg.get('SFTP', 'rDirectory')
lDirectory = cfg.get('SFTP', 'lDirectory')
# Email varibles
email_user = cfg.get('Email', 'email_user')
email_password = cfg.get('Email', 'email_password')
email_to = cfg.get('Email', 'email_to')
smtp_server = cfg.get('Email', 'smtp_server')
smtp_port = cfg.getint('Email', 'smtp_port')

# General varibles for logic
local_files_with_dir = [] # list to hold file names with path
remote_files_in_dir = [] # list to hold file names within remote directory
non_match = [] # list to file names that haven't been uploaded yet
inProgress = True # for While loop
now = datetime.now() # datetime object containing current date and time
dt_string = now.strftime("%d/%m/%Y %H:%M:%S") # dd/mm/YY H:M:S
logFile = open('Log.txt', 'w') # file name of log file
status_title = ''

# function to list local directory
def listLocal(lDirectory):
    local_files_in_dir = []
    local_files_with_dir.clear()

    print('\nLocal path: ' + lDirectory)
    logFile.write('\nLocal path: ' + lDirectory + '\n')
    print('\n[+] Files in local path: ')
    logFile.write('\n[+] Files in local path: \n')

    # will look in sub directories too
    # r=>root, d=>directories, f=>files
    for r, d, f in os.walk(lDirectory):
        for item in f:
            local_files_in_dir.append(os.path.join(r, item))

    for item in local_files_in_dir:
        local_files_with_dir.append(item.replace("\\", "/"))
    print(local_files_with_dir)
    logFile.write('\n' + str(local_files_with_dir) + '\n')

# function to list SFTP directory
def listSFTP(myHostname, myUsername, myPassword, rDirectory):
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    remote_files_in_dir.clear()

    with pysftp.Connection(host=myHostname, username=myUsername, password=myPassword, cnopts=cnopts) as sftp:
        print('\nRemote path: SFTP://' + myHostname + rDirectory)
        logFile.write('\nRemote path: SFTP://' + myHostname + rDirectory + '\n')
        print('\nConnection succesfully established... ')
        logFile.write('\nConnection succesfully established... \n')
        # write to file

        # Switch to a remote directory
        sftp.cwd(rDirectory)

        # Obtain structure of the remote directory i.e. '/var/www/vhosts'
        directory_structure = sftp.listdir_attr()

        for attr in directory_structure:
            remote_files_in_dir.append(attr.filename)
        print('\n[+] Files already on remote server: ')
        logFile.write('\n[+] Files already on remote server: \n')
        print('\n' + str(remote_files_in_dir))
        logFile.write('\n' + str(remote_files_in_dir) + '\n')

# function to list differences between local and remote
def listDifferences(local_files_with_dir, remote_files_in_dir):
    non_match.clear() # reset the non_match list to zero
    print('\nFiles that need to be uploaded: ')
    logFile.write('\nFiles that need to be uploaded: \n')
    for i in local_files_with_dir:
        if i[i.rfind("/") + 1:] not in remote_files_in_dir: # file name after /
            non_match.append(i)
    print(non_match)
    logFile.write('\n' + str(non_match) + '\n')
    print('\nTotal items: ' + str(len(non_match)))
    logFile.write('\nTotal items: ' + str(len(non_match)) + '\n')

# function to upload files to SFTP
def uploadToSFTP(myHostname, myUsername, myPassword, rDirectory):
    global remote_files_in_dir
    global logFile
    global status_title
    
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None
    errorCount = 0

    with pysftp.Connection(host=myHostname, username=myUsername, password=myPassword, cnopts=cnopts) as sftp:
        
        print('\nConnection succesfully established... ')
        logFile.write('\nConnection succesfully established... \n')

        # iterate through list of non_match files and upload one by one
        for item in non_match:
            localFilePath = item
            print('\n[+] Local file: ' + localFilePath)
            logFile.write('\n[+] Local file: ' + localFilePath + '\n')
            remoteFilePath = rDirectory + '/' + item[item.rfind("/") + 1:]
            print('\n[+] Remote file path: ' + remoteFilePath)
            logFile.write('\n[+] Remote file path: ' + remoteFilePath + '\n')
            sftp.put(localFilePath, remoteFilePath)

        # list and compare the files/differences again
        listSFTP(myHostname, myUsername, myPassword, rDirectory)
        listLocal(lDirectory)
        listDifferences(local_files_with_dir, remote_files_in_dir)
        
        if len(non_match) == 0:
            status_title = 'Upload successfully completed - ' + dt_string # STATUS
            print('\n' + status_title)
            logFile.write('\n' + status_title + '\n')
            logFile.close() # close logfile
            logFile = open('Log.txt', 'r') # re-open logfile in read mode
            sendEmail(email_user, email_password, email_to, smtp_server, smtp_port) # send email
            logFile.close() # close logfile
            inProgress = False # stop the while loop
            sys.exit() # exit program
            
        else:
            status_title = 'Re-trying - ' + dt_string # STATUS
            print('\n' + status_title)
            logFile.write('\n' + status_title + '\n')
            errorCount += 1 # re-try loop
            if errorCount > 3: # change for more re-tries
                inProgress = False # stop the while loop
                status_title = "Failure: File couldn't be uploaded - " + dt_string # STATUS
                print('\n' + status_title)
                logFile.write('\n' + status_title + '\n')
                logFile.close() # close logfile
                logFile = open('Log.txt', 'r') # re-open logfile in read mode
                sendEmail(email_user, email_password, email_to, smtp_server, smtp_port) # send email
                logFile.close() # close logfile
                sys.exit() # exit program
                
# function to send emails
def sendEmail(email_user, email_password, email_to, smtp_server, smtp_port):
    
    sent_from = email_user
    subject = status_title
    body = logFile.read()

    email_text = """\
From: %s
To: %s
Subject: %s
    
%s
""" % (sent_from, email_to, subject, body)

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.ehlo()
        server.login(email_user, email_password)
        server.sendmail(sent_from, email_to, email_text)
        server.close()

        print('Email sent!')
    except:
        print('Something went wrong with email...')

# main program loop
while inProgress == True:

    # starting main program
    logFile.write('Starting.. ')

    # list SFTP files
    listSFTP(myHostname, myUsername, myPassword, rDirectory)
    
    # list local files
    listLocal(lDirectory)

    # list the differences in files i.e. file that need to be uploaded
    listDifferences(local_files_with_dir, remote_files_in_dir) # creates non_match list
    
    # if there are files to upload i.e non_match equals more than 0
    if len(non_match) > 0:
        print('\n' + 'Uploading files')
        logFile.write('\n' + 'Uploading files' + '\n')
        print()
        uploadToSFTP(myHostname, myUsername, myPassword, rDirectory)
    else:
        status_title = 'No new files to upload - ' + dt_string # STATUS
        print('\n' + status_title)
        logFile.write('\n' + status_title + '\n')
        logFile.close() # close logfile
        logFile = open('Log.txt', 'r') # re-open logfile in read mode
        sendEmail(email_user, email_password, email_to, smtp_server, smtp_port) # send email
        inProgress = False # stop the while loop

logFile.close()
sys.exit()