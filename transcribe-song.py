import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import boto3
import click
from pydantic import BaseModel, validator

TEMP_S3_BUCKET_NAME = os.environ["S3_BUCKET"]
JOB_SYMBOL = os.environ["JOB_SYMBOL"]

s3client = boto3.client("s3")
transcribeclient = boto3.client("transcribe")


class Effect(BaseModel):
    start_time: int
    end_time: int
    content: str

    @validator("start_time", "end_time", pre=True)
    def check_time(cls, v):
        return float(v) * 1000


def getTranscriptionResults(inputMedia: str):
    with open(inputMedia, "rb") as outfile:
        s3client.upload_fileobj(outfile, TEMP_S3_BUCKET_NAME, JOB_SYMBOL + ".mp3")

    now = datetime.now()
    dateStr = now.strftime("%Y%m%d%H%M%S")
    jobName = JOB_SYMBOL + dateStr
    outputKey = f"transcribe-output/{jobName}.output.json"
    print(f"Starting job: {jobName}")

    transcribeResponse = transcribeclient.start_transcription_job(
        TranscriptionJobName=jobName,
        LanguageCode="en-US",
        Media={"MediaFileUri": f"s3://{TEMP_S3_BUCKET_NAME}/{JOB_SYMBOL}.mp3"},
        OutputBucketName=TEMP_S3_BUCKET_NAME,
        OutputKey=outputKey,
    )

    completed = False
    status = None

    while completed == False:
        getJobResults = transcribeclient.get_transcription_job(
            TranscriptionJobName=jobName
        )
        status = getJobResults["TranscriptionJob"]["TranscriptionJobStatus"]
        print("Job status", status)
        if status == "FAILED" or status == "COMPLETED":
            completed = True
        time.sleep(10)

    if status == "FAILED":
        print("Job failed, exiting")
        exit(2)

    result_file = Path(f"{jobName}.output.json")
    with open(result_file, "wb") as outfile:
        s3client.download_fileobj(TEMP_S3_BUCKET_NAME, outputKey, outfile)

    return jobName


def generate_xtiming(job_name):

    # Read JSON file
    datafile = Path(f"{job_name}.output.json")
    with open(datafile, "r") as f:
        data = json.load(f)

    words = []
    for i in data["results"]["items"]:
        if i["type"] != "pronunciation":
            continue

        # If this is the first line go ahead and zero pad it
        # I don't think this is needed
        if len(words) == 0:
            words.append(
                Effect(
                    content="",
                    start_time=0,
                    end_time=i["start_time"],
                )
            )

        # Fill in the gaps between words.
        # # I don't think this is needed
        elif words[-1].end_time != i["start_time"]:
            words.append(
                Effect(
                    content="",
                    start_time=words[-1].end_time,
                    end_time=i["start_time"],
                )
            )

        words.append(
            Effect(
                content=i["alternatives"][0]["content"],
                start_time=i["start_time"],
                end_time=i["end_time"],
            )
        )

    # ET object is created here
    root = ET.Element("timings")
    timing = ET.SubElement(
        root, "timing", attrib={"name": "New Timing", "SourceVersion": "2018.4"}
    )
    effectlayer = ET.SubElement(timing, "EffectLayer")
    for word in words:
        ET.SubElement(effectlayer, "Effect", attrib=word.dict())

    tree = ET(root)

    # Write the ET object to a file.
    xml_file = Path(f"{job_name}.xtiming")
    with open(xml_file, "wb") as of:
        tree.write(of, xml_declaration=True)


def createXMLOutput(jobName):
    element = ET.Element("Element")
    element.set("type", "timing")
    element.set("name", "TranscribedLyrics")
    layer = ET.SubElement(element, "EffectLayer")

    transcribeOut = None

    with open(f"{jobName}.output.json", "r") as data:
        transcribeOut = json.load(data)

    for item in transcribeOut["results"]["items"]:
        print(item)
        if item["type"] == "pronunciation":
            effect = ET.SubElement(layer, "Effect")
            effect.set("label", item["alternatives"][0]["content"])
            effect.set("startTime", "{:.0f}".format(float(item["start_time"]) * 1000))
            effect.set("endTime", "{:.0f}".format(float(item["end_time"]) * 1000))
    data = ET.tostring(element)
    print(data)


@click.command()
@click.option("--song", type=click.File("rb"), help="Song name")
def main(song):
    jobName = getTranscriptionResults(song.name)
    createXMLOutput(jobName)


if __name__ == "__main__":
    main()
