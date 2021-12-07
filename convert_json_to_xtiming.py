import json
from pathlib import Path
from pydantic import BaseModel, validator

datafile = Path("merry20211207103305.output.json")

# Read JSON file
with open(datafile, "r") as f:
    data = json.load(f)


class Effect(BaseModel):
    start_time: int
    end_time: int
    content: str

    @validator("start_time", "end_time", pre=True)
    def check_time(cls, v):
        return float(v) * 1000


class Effects(BaseModel):
    effects: list[Effect]


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
    elif words[-1].end_time != i["start_time"]:
        this_word = Effect(
            content="",
            start_time=words[-1].end_time,
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

print(len(words))
print(words[-1])
