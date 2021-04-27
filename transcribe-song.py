import boto3
from datetime import datetime
import time
from xml.dom import minidom
import xml.etree.ElementTree as ET
import json

INPUT_MEDIA = '/Users/jarewarr/Desktop/temp/merry.mp3'
TEMP_S3_BUCKET_NAME = 'jarewarr-temp'
JOB_SYMBOL = 'merry'

s3client = boto3.client("s3")
transcribeclient = boto3.client("transcribe")


def getTranscriptionResults(inputMedia):
    with open(inputMedia, 'rb') as data:
        s3client.upload_fileobj(data, TEMP_S3_BUCKET_NAME, JOB_SYMBOL+'.mp3')

    now = datetime.now()
    dateStr = now.strftime('%Y%m%d%H%M%S')
    jobName = JOB_SYMBOL+dateStr
    outputKey = 'transcribe-output/'+jobName+'.output.json'
    print("Starting job:", jobName)

    transcribeResponse = transcribeclient.start_transcription_job(
        TranscriptionJobName=jobName,
        LanguageCode='en-US',
        Media=
            {
                "MediaFileUri": 's3://'+TEMP_S3_BUCKET_NAME+'/'+JOB_SYMBOL+'.mp3'
            },
        OutputBucketName=TEMP_S3_BUCKET_NAME,
        OutputKey=outputKey
    )

    completed = False
    status = None

    while(completed == False):
        getJobResults = transcribeclient.get_transcription_job(
            TranscriptionJobName=jobName
        )
        status = getJobResults['TranscriptionJob']['TranscriptionJobStatus']
        print("Job status",status)
        if status == 'FAILED' or status == 'COMPLETED':
            completed = True
        time.sleep(10)

    if status == 'FAILED':
        print("Job failed, exiting")
        exit(2)

    with open(jobName+'.output.json', 'wb') as data:
        s3client.download_fileobj(TEMP_S3_BUCKET_NAME,outputKey,data)

    return jobName



def createXMLOutput(jobName):
    element = ET.Element('Element')
    element.set('type', 'timing')
    element.set('name', 'TranscribedLyrics')
    layer = ET.SubElement(element, 'EffectLayer')

    transcribeOut = None
    with open(jobName+'.output.json', 'r') as data:
        transcribeOut = json.load(data)
    
    for item in transcribeOut['results']['items']:
        print(item)
        if item['type'] == 'pronunciation':
            effect = ET.SubElement(layer, 'Effect')
            effect.set('label', item['alternatives'][0]['content'])
            effect.set('startTime', "{:.0f}".format(float(item['start_time'])*1000))
            effect.set('endTime', "{:.0f}".format(float(item['end_time'])*1000))
    data = ET.tostring(element)
    print(data)



if __name__ == "__main__":
    jobName = getTranscriptionResults(INPUT_MEDIA)
    createXMLOutput(jobName)