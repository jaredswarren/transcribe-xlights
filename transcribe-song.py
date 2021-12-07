import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import boto3
import click
from pydantic import BaseModel, Field, validator

TEMP_S3_BUCKET_NAME = os.environ["S3_BUCKET"]
JOB_SYMBOL = os.environ["JOB_SYMBOL"]

s3client = boto3.client("s3")
transcribeclient = boto3.client("transcribe")


class Effect(BaseModel):
    starttime: str = Field(alias="start_time")
    endtime: str = Field(alias="end_time")
    label: str = Field(alias="content")

    @validator("starttime", "endtime", pre=True)
    def check_time(cls, v):
        return str(int(float(v) * 1000))


class Effects(BaseModel):
    effects: list[Effect]


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

        if len(words) == 0:
            this_word = Effect(
                content="",
                start_time=0,
                end_time=i["start_time"],
            )
            words.append(this_word)
        elif words[-1].endtime != i["start_time"]:
            this_word = Effect(
                content="",
                start_time=int(words[-1].endtime) / 1000,
                end_time=i["start_time"],
            )
            words.append(this_word)

        this_word = Effect(
            content=i["alternatives"][0]["content"],
            start_time=i["start_time"],
            end_time=i["end_time"],
        )

        # print(this_word)
        # effect = Effect(**this_word)
        words.append(this_word)

    effects = Effects(effects=words)

    # ET object is created here
    root = ET.Element("timings")
    timing = ET.SubElement(
        root, "timing", attrib={"name": "New Timing", "SourceVersion": "2018.4"}
    )
    effectlayer = ET.SubElement(timing, "EffectLayer")
    for word in words:
        ET.SubElement(effectlayer, "Effect", attrib=word.dict())

    # Write the ET object to a file.
    tree = ET.ElementTree(root)
    ET.indent(tree)
    xml_file = Path(f"{job_name}.xtiming")
    tree.write(xml_file, xml_declaration=True, encoding="UTF-8")


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
    generate_xtiming(jobName)


if __name__ == "__main__":
    main()
